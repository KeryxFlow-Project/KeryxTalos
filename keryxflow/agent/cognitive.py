"""Cognitive Agent for AI-first autonomous trading.

The CognitiveAgent implements the cognitive trading loop:
    Perceive → Remember → Analyze → Decide → Validate → Execute → Learn

This agent uses Claude's Tool Use API to make trading decisions autonomously
while respecting immutable guardrails.
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from keryxflow.agent.executor import ToolExecutor, get_tool_executor
from keryxflow.agent.tools import (
    ToolCategory,
    ToolResult,
    TradingToolkit,
    get_trading_toolkit,
    register_all_tools,
)
from keryxflow.config import AgentSettings, get_settings
from keryxflow.core.events import Event, EventType, get_event_bus
from keryxflow.core.logging import get_logger
from keryxflow.memory.manager import MemoryManager, get_memory_manager

logger = get_logger(__name__)


class CycleStatus(str, Enum):
    """Status of an agent cycle."""

    SUCCESS = "success"
    NO_ACTION = "no_action"
    FALLBACK = "fallback"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"


class DecisionType(str, Enum):
    """Type of trading decision."""

    HOLD = "hold"
    ENTRY_LONG = "entry_long"
    ENTRY_SHORT = "entry_short"
    EXIT = "exit"
    ADJUST_STOP = "adjust_stop"
    ADJUST_TARGET = "adjust_target"


@dataclass
class ToolCall:
    """Represents a tool call from Claude."""

    id: str
    name: str
    input: dict[str, Any]


@dataclass
class AgentDecision:
    """Represents an agent's trading decision."""

    decision_type: DecisionType
    symbol: str | None = None
    reasoning: str = ""
    confidence: float = 0.0
    tool_calls: list[ToolCall] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CycleResult:
    """Result of a single agent cycle."""

    status: CycleStatus
    decision: AgentDecision | None = None
    tool_results: list[ToolResult] = field(default_factory=list)
    error: str | None = None
    duration_ms: float = 0.0
    tokens_used: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "decision": {
                "type": self.decision.decision_type.value,
                "symbol": self.decision.symbol,
                "reasoning": self.decision.reasoning,
                "confidence": self.decision.confidence,
            }
            if self.decision
            else None,
            "tool_results_count": len(self.tool_results),
            "error": self.error,
            "duration_ms": self.duration_ms,
            "tokens_used": self.tokens_used,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class AgentStats:
    """Statistics for the cognitive agent."""

    total_cycles: int = 0
    successful_cycles: int = 0
    fallback_cycles: int = 0
    error_cycles: int = 0
    total_tool_calls: int = 0
    total_tokens_used: int = 0
    decisions_by_type: dict[str, int] = field(default_factory=dict)
    last_cycle_time: datetime | None = None
    consecutive_errors: int = 0


class CognitiveAgent:
    """AI-first cognitive trading agent.

    The agent operates in a continuous cycle:
    1. **Perceive**: Gather market data using perception tools
    2. **Remember**: Retrieve relevant context from memory
    3. **Analyze**: Process data with analysis tools
    4. **Decide**: Claude determines the best action
    5. **Validate**: Guardrails check the proposed action
    6. **Execute**: Execute approved actions
    7. **Learn**: Record outcomes in memory

    Example:
        agent = CognitiveAgent()
        await agent.initialize()

        # Run a single cycle
        result = await agent.run_cycle()

        # Or run continuously
        await agent.run_loop()
    """

    SYSTEM_PROMPT = """You are KeryxFlow's trading agent, responsible for making autonomous trading decisions in cryptocurrency markets.

## Your Role
- Analyze market conditions using available tools
- Make trading decisions based on technical analysis and memory context
- Execute trades within the guardrails (safety limits that cannot be bypassed)

## Decision Framework
1. First, gather market data (price, OHLCV, indicators)
2. Check memory for similar situations and applicable rules
3. Analyze risk/reward for potential trades
4. Make a decision: HOLD, ENTER (long/short), EXIT, or ADJUST

## Safety Guidelines
- NEVER bypass guardrails - they exist to protect the portfolio
- Always calculate position size using the calculate_position_size tool
- Always set stop losses for new positions
- Respect the maximum position size and exposure limits

## Output Format
After analyzing the market, explain your reasoning and use the appropriate execution tool if action is needed. If no action is needed, explain why you're choosing to HOLD.

Current UTC time: {current_time}
Active symbols: {symbols}
"""

    def __init__(
        self,
        toolkit: TradingToolkit | None = None,
        executor: ToolExecutor | None = None,
        memory: MemoryManager | None = None,
        settings: AgentSettings | None = None,
    ):
        """Initialize the cognitive agent.

        Args:
            toolkit: Trading toolkit with tools. Uses global if None.
            executor: Tool executor. Uses global if None.
            memory: Memory manager. Uses global if None.
            settings: Agent settings. Uses global if None.
        """
        self.settings = settings or get_settings().agent
        self.toolkit = toolkit or get_trading_toolkit()
        self.executor = executor or get_tool_executor()
        self.memory = memory or get_memory_manager()
        self._event_bus = get_event_bus()

        self._initialized = False
        self._running = False
        self._stats = AgentStats()
        self._cycle_history: list[CycleResult] = []
        self._client: Any = None  # Anthropic client

    async def initialize(self) -> None:
        """Initialize the agent and register all tools."""
        if self._initialized:
            return

        # Register all tools
        register_all_tools(self.toolkit)

        # Initialize Anthropic client
        try:
            import anthropic

            settings = get_settings()
            api_key = settings.anthropic_api_key.get_secret_value()

            if not api_key:
                logger.warning("anthropic_api_key_not_configured")
                self._client = None
            else:
                self._client = anthropic.Anthropic(api_key=api_key)
                logger.info("anthropic_client_initialized")

        except ImportError:
            logger.error("anthropic_package_not_installed")
            self._client = None

        self._initialized = True
        logger.info(
            "cognitive_agent_initialized",
            tools_count=self.toolkit.tool_count,
            model=self.settings.model,
        )

    async def run_cycle(self, symbols: list[str] | None = None) -> CycleResult:
        """Run a single cognitive cycle.

        Args:
            symbols: Symbols to analyze. Uses configured symbols if None.

        Returns:
            CycleResult with the outcome of the cycle
        """
        if not self._initialized:
            await self.initialize()

        started_at = datetime.now(UTC)
        symbols = symbols or get_settings().system.symbols

        # Check if we should fall back to technical signals
        if self._client is None:
            if self.settings.fallback_to_technical:
                return await self._run_fallback_cycle(symbols, started_at)
            return CycleResult(
                status=CycleStatus.ERROR,
                error="Anthropic client not available and fallback disabled",
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )

        try:
            # 1. Build context (Perceive + Remember)
            context = await self._build_context(symbols)

            # 2. Get decision from Claude (Analyze + Decide)
            decision, tool_results, tokens = await self._get_decision(context, symbols)

            # 3. Record cycle
            completed_at = datetime.now(UTC)
            duration_ms = (completed_at - started_at).total_seconds() * 1000

            result = CycleResult(
                status=CycleStatus.SUCCESS if decision else CycleStatus.NO_ACTION,
                decision=decision,
                tool_results=tool_results,
                duration_ms=duration_ms,
                tokens_used=tokens,
                started_at=started_at,
                completed_at=completed_at,
            )

            # 4. Update stats
            self._update_stats(result)

            # 5. Publish event
            await self._publish_cycle_event(result)

            # Reset error counter on success
            self._stats.consecutive_errors = 0

            logger.info(
                "agent_cycle_completed",
                status=result.status.value,
                decision_type=decision.decision_type.value if decision else None,
                tool_calls=len(tool_results),
                duration_ms=duration_ms,
            )

            return result

        except Exception as e:
            self._stats.consecutive_errors += 1
            logger.error("agent_cycle_failed", error=str(e))

            # Check if we should fall back
            if (
                self.settings.fallback_to_technical
                and self._stats.consecutive_errors >= self.settings.max_consecutive_errors
            ):
                logger.warning(
                    "falling_back_to_technical",
                    consecutive_errors=self._stats.consecutive_errors,
                )
                return await self._run_fallback_cycle(symbols, started_at)

            return CycleResult(
                status=CycleStatus.ERROR,
                error=str(e),
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )

    async def _build_context(self, symbols: list[str]) -> dict[str, Any]:
        """Build context for the agent by gathering market data and memory.

        Args:
            symbols: Symbols to gather context for

        Returns:
            Context dictionary with market data and memory context
        """
        context: dict[str, Any] = {
            "symbols": symbols,
            "timestamp": datetime.now(UTC).isoformat(),
            "market_data": {},
            "memory_context": {},
        }

        # Gather market data for each symbol
        for symbol in symbols:
            try:
                # Get current price
                price_result = await self.executor.execute("get_current_price", symbol=symbol)
                if price_result.success:
                    context["market_data"][symbol] = {"price": price_result.data}

                # Get memory context
                memory_context = await self.memory.build_context_for_decision(
                    symbol=symbol,
                    technical_context={},
                )
                context["memory_context"][symbol] = memory_context

            except Exception as e:
                logger.warning("context_build_error", symbol=symbol, error=str(e))

        return context

    async def _get_decision(
        self, context: dict[str, Any], symbols: list[str]
    ) -> tuple[AgentDecision | None, list[ToolResult], int]:
        """Get trading decision from Claude using tool use.

        Args:
            context: Context built from _build_context
            symbols: Active symbols

        Returns:
            Tuple of (decision, tool_results, tokens_used)
        """
        # Build system prompt
        system_prompt = self.SYSTEM_PROMPT.format(
            current_time=datetime.now(UTC).isoformat(),
            symbols=", ".join(symbols),
        )

        # Build initial user message with context
        user_message = self._build_user_message(context)

        # Get tool schemas based on settings
        tools = self._get_enabled_tools()

        # Conversation loop with tool use
        messages = [{"role": "user", "content": user_message}]
        tool_results: list[ToolResult] = []
        total_tokens = 0
        max_iterations = self.settings.max_tool_calls_per_cycle

        for iteration in range(max_iterations):
            # Call Claude
            response = self._client.messages.create(
                model=self.settings.model,
                max_tokens=self.settings.max_tokens,
                temperature=self.settings.temperature,
                system=system_prompt,
                tools=tools,
                messages=messages,
            )

            # Track tokens
            total_tokens += response.usage.input_tokens + response.usage.output_tokens

            # Check for tool use
            tool_use_blocks = [block for block in response.content if block.type == "tool_use"]

            if not tool_use_blocks:
                # No more tool calls - extract decision from text
                text_blocks = [block for block in response.content if block.type == "text"]
                reasoning = " ".join(block.text for block in text_blocks)

                decision = self._parse_decision(reasoning, tool_results)
                return decision, tool_results, total_tokens

            # Execute tool calls
            tool_call_results = []
            for tool_block in tool_use_blocks:
                # Execute the tool
                result = await self.executor.execute(tool_block.name, **tool_block.input)
                tool_results.append(result)
                self._stats.total_tool_calls += 1

                tool_call_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_block.id,
                        "content": json.dumps(result.to_dict()),
                    }
                )

                logger.debug(
                    "tool_executed_in_cycle",
                    tool=tool_block.name,
                    success=result.success,
                    iteration=iteration,
                )

            # Add assistant message and tool results to conversation
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_call_results})

            # Check stop reason
            if response.stop_reason == "end_turn":
                break

        # Max iterations reached
        logger.warning("max_tool_iterations_reached", iterations=max_iterations)
        return None, tool_results, total_tokens

    def _build_user_message(self, context: dict[str, Any]) -> str:
        """Build the initial user message with context.

        Args:
            context: Context dictionary

        Returns:
            Formatted user message
        """
        parts = ["Analyze the current market conditions and decide on the best action.\n"]

        # Add market data summary
        if context.get("market_data"):
            parts.append("## Current Market Data")
            for symbol, data in context["market_data"].items():
                if data.get("price"):
                    parts.append(f"- {symbol}: ${data['price'].get('price', 'N/A')}")
            parts.append("")

        # Add memory context summary
        if context.get("memory_context"):
            parts.append("## Memory Context")
            for symbol, mem in context["memory_context"].items():
                if mem:
                    similar_count = len(mem.get("similar_trades", []))
                    rules_count = len(mem.get("applicable_rules", []))
                    parts.append(f"- {symbol}: {similar_count} similar trades, {rules_count} rules")
            parts.append("")

        parts.append(
            "Use the available tools to gather more data if needed, then make a trading decision."
        )

        return "\n".join(parts)

    def _get_enabled_tools(self) -> list[dict[str, Any]]:
        """Get tool schemas for enabled categories.

        Returns:
            List of tool schemas in Anthropic format
        """
        categories = []

        if self.settings.enable_perception:
            categories.append(ToolCategory.PERCEPTION)
        if self.settings.enable_analysis:
            categories.append(ToolCategory.ANALYSIS)
        if self.settings.enable_introspection:
            categories.append(ToolCategory.INTROSPECTION)
        if self.settings.enable_execution:
            categories.append(ToolCategory.EXECUTION)

        return self.toolkit.get_anthropic_tools_schema(categories)

    def _parse_decision(
        self, reasoning: str, tool_results: list[ToolResult]
    ) -> AgentDecision | None:
        """Parse the agent's decision from its reasoning.

        Args:
            reasoning: Text reasoning from Claude
            tool_results: Results from tool executions

        Returns:
            Parsed AgentDecision or None
        """
        reasoning_lower = reasoning.lower()

        # Check for execution tool results to determine decision type
        executed_order = False
        executed_close = False
        symbol = None

        for result in tool_results:
            if result.success and result.data:
                data = result.data
                if isinstance(data, dict):
                    if "order_id" in data:
                        executed_order = True
                        symbol = data.get("symbol")
                    elif "closed" in data:
                        executed_close = True
                        symbol = data.get("symbol")

        # Determine decision type
        if executed_order:
            if "long" in reasoning_lower or "buy" in reasoning_lower:
                decision_type = DecisionType.ENTRY_LONG
            elif "short" in reasoning_lower or "sell" in reasoning_lower:
                decision_type = DecisionType.ENTRY_SHORT
            else:
                decision_type = DecisionType.ENTRY_LONG
        elif executed_close:
            decision_type = DecisionType.EXIT
        elif "hold" in reasoning_lower or "wait" in reasoning_lower or "no action" in reasoning_lower:
            decision_type = DecisionType.HOLD
        else:
            decision_type = DecisionType.HOLD

        # Extract confidence (simple heuristic)
        confidence = 0.5
        if "high confidence" in reasoning_lower or "strong" in reasoning_lower:
            confidence = 0.8
        elif "low confidence" in reasoning_lower or "weak" in reasoning_lower:
            confidence = 0.3

        return AgentDecision(
            decision_type=decision_type,
            symbol=symbol,
            reasoning=reasoning[:500],  # Truncate for storage
            confidence=confidence,
        )

    async def _run_fallback_cycle(
        self, symbols: list[str], started_at: datetime
    ) -> CycleResult:
        """Run a fallback cycle using technical signals.

        Args:
            symbols: Symbols to analyze
            started_at: Cycle start time

        Returns:
            CycleResult from fallback
        """
        try:
            from keryxflow.oracle.signals import get_signal_generator

            signal_generator = get_signal_generator()
            tool_results: list[ToolResult] = []

            for symbol in symbols:
                # Get OHLCV data
                ohlcv_result = await self.executor.execute(
                    "get_ohlcv", symbol=symbol, timeframe="1h", limit=100
                )

                if ohlcv_result.success and ohlcv_result.data:
                    # Convert to DataFrame and generate signal
                    import pandas as pd

                    ohlcv_data = ohlcv_result.data.get("ohlcv", [])
                    if ohlcv_data:
                        df = pd.DataFrame(
                            ohlcv_data,
                            columns=["datetime", "open", "high", "low", "close", "volume"],
                        )
                        current_price = df["close"].iloc[-1]

                        signal = await signal_generator.generate_signal(
                            symbol=symbol,
                            ohlcv=df,
                            current_price=current_price,
                            include_llm=False,
                        )

                        tool_results.append(
                            ToolResult(
                                success=True,
                                data={
                                    "symbol": symbol,
                                    "signal": signal.signal_type.value,
                                    "confidence": signal.confidence,
                                },
                            )
                        )

            completed_at = datetime.now(UTC)
            duration_ms = (completed_at - started_at).total_seconds() * 1000

            result = CycleResult(
                status=CycleStatus.FALLBACK,
                decision=AgentDecision(
                    decision_type=DecisionType.HOLD,
                    reasoning="Fallback to technical signals",
                    confidence=0.5,
                ),
                tool_results=tool_results,
                duration_ms=duration_ms,
                started_at=started_at,
                completed_at=completed_at,
            )

            self._stats.fallback_cycles += 1
            self._update_stats(result)

            logger.info("fallback_cycle_completed", symbols=symbols)
            return result

        except Exception as e:
            logger.error("fallback_cycle_failed", error=str(e))
            return CycleResult(
                status=CycleStatus.ERROR,
                error=f"Fallback failed: {str(e)}",
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )

    def _update_stats(self, result: CycleResult) -> None:
        """Update agent statistics.

        Args:
            result: Cycle result to record
        """
        self._stats.total_cycles += 1
        self._stats.last_cycle_time = result.completed_at or datetime.now(UTC)
        self._stats.total_tokens_used += result.tokens_used

        if result.status == CycleStatus.SUCCESS:
            self._stats.successful_cycles += 1
        elif result.status == CycleStatus.FALLBACK:
            self._stats.fallback_cycles += 1
        elif result.status == CycleStatus.ERROR:
            self._stats.error_cycles += 1

        if result.decision:
            dt = result.decision.decision_type.value
            self._stats.decisions_by_type[dt] = self._stats.decisions_by_type.get(dt, 0) + 1

        # Keep history (last 100 cycles)
        self._cycle_history.append(result)
        if len(self._cycle_history) > 100:
            self._cycle_history = self._cycle_history[-100:]

    async def _publish_cycle_event(self, result: CycleResult) -> None:
        """Publish an event for the cycle completion.

        Args:
            result: Cycle result
        """
        await self._event_bus.publish(
            Event(
                type=EventType.SIGNAL_GENERATED,
                data={
                    "source": "cognitive_agent",
                    "cycle_result": result.to_dict(),
                },
            )
        )

    async def run_loop(self, max_cycles: int | None = None) -> None:
        """Run the agent in a continuous loop.

        Args:
            max_cycles: Maximum cycles to run. None for infinite.
        """
        import asyncio

        if not self._initialized:
            await self.initialize()

        self._running = True
        cycle_count = 0

        logger.info("agent_loop_started", max_cycles=max_cycles)

        try:
            while self._running:
                if max_cycles and cycle_count >= max_cycles:
                    break

                await self.run_cycle()
                cycle_count += 1

                # Wait for next cycle
                await asyncio.sleep(self.settings.cycle_interval)

        except Exception as e:
            logger.error("agent_loop_error", error=str(e))
        finally:
            self._running = False
            logger.info("agent_loop_stopped", total_cycles=cycle_count)

    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False

    def get_stats(self) -> dict[str, Any]:
        """Get agent statistics.

        Returns:
            Dictionary with agent statistics
        """
        return {
            "total_cycles": self._stats.total_cycles,
            "successful_cycles": self._stats.successful_cycles,
            "fallback_cycles": self._stats.fallback_cycles,
            "error_cycles": self._stats.error_cycles,
            "total_tool_calls": self._stats.total_tool_calls,
            "total_tokens_used": self._stats.total_tokens_used,
            "decisions_by_type": self._stats.decisions_by_type,
            "consecutive_errors": self._stats.consecutive_errors,
            "last_cycle_time": (
                self._stats.last_cycle_time.isoformat() if self._stats.last_cycle_time else None
            ),
            "success_rate": (
                self._stats.successful_cycles / self._stats.total_cycles
                if self._stats.total_cycles > 0
                else 0
            ),
        }

    def get_recent_cycles(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent cycle results.

        Args:
            limit: Maximum number of cycles to return

        Returns:
            List of recent cycle results
        """
        return [r.to_dict() for r in self._cycle_history[-limit:]]


# Global agent instance
_agent: CognitiveAgent | None = None


def get_cognitive_agent() -> CognitiveAgent:
    """Get the global cognitive agent instance."""
    global _agent
    if _agent is None:
        _agent = CognitiveAgent()
    return _agent
