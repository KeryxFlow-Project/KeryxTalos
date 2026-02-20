"""Safe tool executor with guardrail integration.

The ToolExecutor provides a safe wrapper around tool execution that:
- Validates guarded tools against guardrails before execution
- Logs all tool executions for auditing
- Publishes events for tool execution lifecycle
- Handles errors gracefully
- Enforces rate limits
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from keryxflow.agent.tools import (
    BaseTool,
    ToolCategory,
    ToolResult,
    TradingToolkit,
    get_trading_toolkit,
)
from keryxflow.core.events import Event, EventType, get_event_bus
from keryxflow.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ExecutionRecord:
    """Record of a tool execution."""

    tool_name: str
    category: ToolCategory
    parameters: dict[str, Any]
    result: ToolResult
    started_at: datetime
    completed_at: datetime
    duration_ms: float
    was_guarded: bool
    guardrail_passed: bool | None = None


@dataclass
class ExecutorStats:
    """Statistics for tool executor."""

    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    blocked_by_guardrails: int = 0
    executions_by_category: dict[str, int] = field(default_factory=dict)
    last_execution_time: datetime | None = None


class ToolExecutor:
    """Safe executor for agent tools with guardrail integration.

    The executor wraps tool execution to ensure:
    1. Guarded tools (execution) are validated before running
    2. All executions are logged and can be audited
    3. Events are published for tool lifecycle
    4. Errors are handled gracefully
    5. Rate limits are enforced

    Example:
        executor = ToolExecutor()

        # Execute a tool
        result = await executor.execute("get_current_price", symbol="BTC/USDT")

        # Execute with explicit guardrail check
        result = await executor.execute_guarded(
            "place_order",
            symbol="BTC/USDT",
            side="buy",
            quantity=0.1
        )
    """

    def __init__(
        self,
        toolkit: TradingToolkit | None = None,
        max_executions_per_minute: int = 30,
    ):
        """Initialize the tool executor.

        Args:
            toolkit: Trading toolkit with registered tools. Uses global if None.
            max_executions_per_minute: Rate limit for tool executions.
        """
        self.toolkit = toolkit or get_trading_toolkit()
        self.max_executions_per_minute = max_executions_per_minute
        self._event_bus = get_event_bus()
        self._stats = ExecutorStats()
        self._execution_history: list[ExecutionRecord] = []
        self._recent_executions: list[datetime] = []

    async def execute(
        self,
        tool_name: str,
        skip_guardrails: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute a tool by name with automatic guardrail checking.

        For guarded tools (execution category), this will:
        1. Validate parameters
        2. Check guardrails before execution
        3. Execute the tool
        4. Log and publish events

        Args:
            tool_name: Name of the tool to execute
            skip_guardrails: Skip guardrail check (DANGEROUS - use with caution)
            **kwargs: Parameters to pass to the tool

        Returns:
            ToolResult from the tool execution
        """
        # Check rate limit
        if not self._check_rate_limit():
            return ToolResult(
                success=False,
                error="Rate limit exceeded. Too many tool executions.",
                metadata={"rate_limit": self.max_executions_per_minute},
            )

        # Get the tool
        tool = self.toolkit.get_tool(tool_name)
        if tool is None:
            return ToolResult(
                success=False,
                error=f"Tool '{tool_name}' not found",
            )

        # Record start time
        started_at = datetime.now(UTC)
        guardrail_passed = None

        try:
            # Validate parameters
            is_valid, error = tool.validate_parameters(**kwargs)
            if not is_valid:
                return ToolResult(success=False, error=error)

            # Check guardrails for execution tools
            if tool.is_guarded and not skip_guardrails:
                guardrail_result = await self._check_guardrails(tool, kwargs)
                guardrail_passed = guardrail_result.success

                if not guardrail_result.success:
                    self._stats.blocked_by_guardrails += 1
                    await self._publish_event(
                        "tool.blocked",
                        tool_name=tool_name,
                        reason=guardrail_result.error,
                    )
                    return guardrail_result

            # Publish execution started event
            await self._publish_event(
                "tool.started",
                tool_name=tool_name,
                category=tool.category.value,
                parameters=self._sanitize_params(kwargs),
            )

            # Execute the tool
            result = await tool.execute(**kwargs)

            # Record completion
            completed_at = datetime.now(UTC)
            duration_ms = (completed_at - started_at).total_seconds() * 1000

            # Update stats
            self._update_stats(tool, result)
            self._recent_executions.append(completed_at)

            # Record execution
            record = ExecutionRecord(
                tool_name=tool_name,
                category=tool.category,
                parameters=self._sanitize_params(kwargs),
                result=result,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=duration_ms,
                was_guarded=tool.is_guarded,
                guardrail_passed=guardrail_passed,
            )
            self._execution_history.append(record)

            # Trim history to last 1000 records
            if len(self._execution_history) > 1000:
                self._execution_history = self._execution_history[-1000:]

            # Publish completion event
            await self._publish_event(
                "tool.completed",
                tool_name=tool_name,
                success=result.success,
                duration_ms=duration_ms,
            )

            logger.info(
                "tool_executed",
                tool=tool_name,
                category=tool.category.value,
                success=result.success,
                duration_ms=duration_ms,
                guarded=tool.is_guarded,
            )

            return result

        except Exception as e:
            self._stats.total_executions += 1
            self._stats.failed_executions += 1

            await self._publish_event(
                "tool.failed",
                tool_name=tool_name,
                error=str(e),
            )

            logger.exception("tool_execution_error", tool=tool_name)

            return ToolResult(
                success=False,
                error=f"Tool execution failed: {str(e)}",
            )

    async def execute_guarded(
        self,
        tool_name: str,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute a guarded tool with explicit guardrail checking.

        This method is specifically for execution tools and will always
        check guardrails regardless of the skip_guardrails flag.

        Args:
            tool_name: Name of the tool to execute
            **kwargs: Parameters to pass to the tool

        Returns:
            ToolResult from the tool execution
        """
        tool = self.toolkit.get_tool(tool_name)
        if tool is None:
            return ToolResult(success=False, error=f"Tool '{tool_name}' not found")

        if not tool.is_guarded:
            logger.warning(
                "execute_guarded_on_unguarded_tool",
                tool=tool_name,
                category=tool.category.value,
            )

        return await self.execute(tool_name, skip_guardrails=False, **kwargs)

    async def _check_guardrails(
        self,
        tool: BaseTool,
        params: dict[str, Any],
    ) -> ToolResult:
        """Check guardrails before executing a guarded tool.

        Args:
            tool: The tool being executed
            params: Tool parameters

        Returns:
            ToolResult indicating whether guardrails passed
        """
        # Only check for order placement tool
        if tool.name == "place_order":
            from keryxflow.aegis.guardrails import get_guardrail_enforcer
            from keryxflow.aegis.risk import get_risk_manager

            symbol = params.get("symbol")
            side = params.get("side")
            quantity = params.get("quantity")
            stop_loss = params.get("stop_loss")

            if not all([symbol, side, quantity]):
                return ToolResult(
                    success=False,
                    error="Missing required parameters for guardrail check",
                )

            # Get current price for validation
            price = params.get("price")
            if price is None:
                from keryxflow.exchange.paper import get_paper_engine

                engine = get_paper_engine()
                price = engine.get_price(symbol)

            if price is None:
                # Can't validate without price, let the tool handle it
                return ToolResult(success=True)

            risk_manager = get_risk_manager()
            enforcer = get_guardrail_enforcer()

            result = enforcer.validate_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                entry_price=price,
                stop_loss=stop_loss,
                portfolio=risk_manager.portfolio_state,
            )

            if not result.allowed:
                return ToolResult(
                    success=False,
                    error=f"Guardrail violation: {result.message}",
                    metadata={
                        "violation": result.violation.value if result.violation else None,
                        "details": result.details,
                    },
                )

        # For other execution tools, allow by default
        # (they have their own internal validation)
        return ToolResult(success=True)

    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits.

        Returns:
            True if within limits, False if exceeded
        """
        now = datetime.now(UTC)

        # Remove entries older than 1 minute
        self._recent_executions = [
            t for t in self._recent_executions if (now - t).total_seconds() < 60
        ]

        return len(self._recent_executions) < self.max_executions_per_minute

    def _update_stats(self, tool: BaseTool, result: ToolResult) -> None:
        """Update execution statistics.

        Args:
            tool: The executed tool
            result: The execution result
        """
        self._stats.total_executions += 1
        self._stats.last_execution_time = datetime.now(UTC)

        if result.success:
            self._stats.successful_executions += 1
        else:
            self._stats.failed_executions += 1

        category = tool.category.value
        if category not in self._stats.executions_by_category:
            self._stats.executions_by_category[category] = 0
        self._stats.executions_by_category[category] += 1

    async def _publish_event(self, event_type: str, **data: Any) -> None:
        """Publish a tool execution event.

        Args:
            event_type: Type of event (e.g., "tool.started")
            **data: Event data
        """
        event = Event(
            type=EventType.SYSTEM_STARTED,  # Using as generic event
            data={"event_type": event_type, **data},
        )
        await self._event_bus.publish(event)

    def _sanitize_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Sanitize parameters for logging (remove sensitive data).

        Args:
            params: Original parameters

        Returns:
            Sanitized parameters safe for logging
        """
        sanitized = {}
        sensitive_keys = {"api_key", "secret", "password", "token"}

        for key, value in params.items():
            if key.lower() in sensitive_keys:
                sanitized[key] = "***"
            else:
                sanitized[key] = value

        return sanitized

    def get_stats(self) -> dict[str, Any]:
        """Get executor statistics.

        Returns:
            Dictionary with execution statistics
        """
        return {
            "total_executions": self._stats.total_executions,
            "successful_executions": self._stats.successful_executions,
            "failed_executions": self._stats.failed_executions,
            "blocked_by_guardrails": self._stats.blocked_by_guardrails,
            "executions_by_category": self._stats.executions_by_category,
            "success_rate": (
                self._stats.successful_executions / self._stats.total_executions
                if self._stats.total_executions > 0
                else 0
            ),
            "last_execution_time": (
                self._stats.last_execution_time.isoformat()
                if self._stats.last_execution_time
                else None
            ),
        }

    def get_recent_executions(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent tool executions.

        Args:
            limit: Maximum number of executions to return

        Returns:
            List of recent execution records
        """
        records = self._execution_history[-limit:]
        return [
            {
                "tool_name": r.tool_name,
                "category": r.category.value,
                "success": r.result.success,
                "error": r.result.error if not r.result.success else None,
                "duration_ms": r.duration_ms,
                "was_guarded": r.was_guarded,
                "guardrail_passed": r.guardrail_passed,
                "started_at": r.started_at.isoformat(),
            }
            for r in reversed(records)
        ]

    def clear_stats(self) -> None:
        """Clear execution statistics."""
        self._stats = ExecutorStats()
        self._execution_history = []
        self._recent_executions = []


# Global executor instance
_executor: ToolExecutor | None = None


def get_tool_executor() -> ToolExecutor:
    """Get the global tool executor instance."""
    global _executor
    if _executor is None:
        _executor = ToolExecutor()
    return _executor
