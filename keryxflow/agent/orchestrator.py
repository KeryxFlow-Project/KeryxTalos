"""Agent Orchestrator for multi-agent trading pipeline.

Coordinates the Analyst → Risk → Executor pipeline, returning
CycleResult for drop-in compatibility with TradingEngine.
"""

from datetime import UTC, datetime
from typing import Any

from keryxflow.agent.analyst_agent import AnalystAgent
from keryxflow.agent.cognitive import (
    AgentDecision,
    AgentStats,
    CycleResult,
    CycleStatus,
    DecisionType,
)
from keryxflow.agent.executor import ToolExecutor, get_tool_executor
from keryxflow.agent.executor_agent import ExecutorAgent
from keryxflow.agent.risk_agent import RiskAgent
from keryxflow.agent.tools import (
    TradingToolkit,
    get_trading_toolkit,
    register_all_tools,
)
from keryxflow.config import AgentSettings, get_settings
from keryxflow.core.events import Event, EventType, get_event_bus
from keryxflow.core.logging import get_logger
from keryxflow.memory.manager import MemoryManager, get_memory_manager

logger = get_logger(__name__)


class AgentOrchestrator:
    """Orchestrates the multi-agent trading pipeline.

    Pipeline: AnalystAgent → RiskAgent → ExecutorAgent

    The orchestrator manages the sequential pipeline with early exit:
    1. AnalystAgent analyzes market → MarketAnalysis
    2. If signal is "hold", pipeline stops (no action)
    3. RiskAgent evaluates the proposed trade → RiskAssessment
    4. If not approved, pipeline stops (rejected)
    5. ExecutorAgent executes the trade → ExecutionResult

    Returns CycleResult for compatibility with TradingEngine.
    """

    def __init__(
        self,
        toolkit: TradingToolkit | None = None,
        executor: ToolExecutor | None = None,
        memory: MemoryManager | None = None,
        settings: AgentSettings | None = None,
    ):
        self.settings = settings or get_settings().agent
        self.toolkit = toolkit or get_trading_toolkit()
        self.executor = executor or get_tool_executor()
        self.memory = memory or get_memory_manager()
        self._event_bus = get_event_bus()

        # Create specialized agents sharing the same toolkit and executor
        self.analyst = AnalystAgent(
            toolkit=self.toolkit,
            executor=self.executor,
            settings=self.settings,
        )
        self.risk_agent = RiskAgent(
            toolkit=self.toolkit,
            executor=self.executor,
            settings=self.settings,
        )
        self.executor_agent = ExecutorAgent(
            toolkit=self.toolkit,
            executor=self.executor,
            settings=self.settings,
        )

        self._initialized = False
        self._stats = AgentStats()
        self._cycle_history: list[CycleResult] = []

    async def initialize(self) -> None:
        """Initialize all agents."""
        if self._initialized:
            return

        # Ensure tools are registered
        if self.toolkit.tool_count == 0:
            register_all_tools(self.toolkit)

        await self.analyst.initialize()
        await self.risk_agent.initialize()
        await self.executor_agent.initialize()

        self._initialized = True
        logger.info("agent_orchestrator_initialized")

    async def run_cycle(self, symbols: list[str] | None = None) -> CycleResult:
        """Run a full multi-agent cycle.

        Args:
            symbols: Symbols to analyze. Uses configured symbols if None.

        Returns:
            CycleResult compatible with TradingEngine
        """
        if not self._initialized:
            await self.initialize()

        started_at = datetime.now(UTC)
        symbols = symbols or get_settings().system.symbols
        total_tokens = 0

        try:
            # Build context for all symbols
            context = await self._build_context(symbols)

            # Run pipeline for each symbol
            for symbol in symbols:
                result = await self._run_pipeline(symbol, context, started_at, total_tokens)
                if result is not None:
                    self._update_stats(result)
                    self._stats.consecutive_errors = 0
                    await self._publish_cycle_event(result)
                    return result

            # No actionable signal for any symbol
            completed_at = datetime.now(UTC)
            duration_ms = (completed_at - started_at).total_seconds() * 1000

            result = CycleResult(
                status=CycleStatus.NO_ACTION,
                decision=AgentDecision(
                    decision_type=DecisionType.HOLD,
                    reasoning="No actionable signal found by analyst",
                ),
                duration_ms=duration_ms,
                tokens_used=total_tokens,
                started_at=started_at,
                completed_at=completed_at,
            )

            self._update_stats(result)
            self._stats.consecutive_errors = 0
            await self._publish_cycle_event(result)
            return result

        except Exception as e:
            self._stats.consecutive_errors += 1
            logger.exception("orchestrator_cycle_failed")

            completed_at = datetime.now(UTC)
            result = CycleResult(
                status=CycleStatus.ERROR,
                error=str(e),
                started_at=started_at,
                completed_at=completed_at,
            )
            self._update_stats(result)
            return result

    async def _run_pipeline(
        self,
        symbol: str,
        context: dict[str, Any],
        started_at: datetime,
        total_tokens: int,
    ) -> CycleResult | None:
        """Run the Analyst → Risk → Executor pipeline for a symbol.

        Returns CycleResult if a decision was made, None to continue to next symbol.
        """
        # Stage 1: Analyst
        logger.info("orchestrator_analyst_start", symbol=symbol)
        analysis = await self.analyst.analyze(symbol, context)
        total_tokens += analysis.tokens_used

        await self._event_bus.publish(
            Event(
                type=EventType.AGENT_ANALYSIS_COMPLETED,
                data={
                    "symbol": symbol,
                    "signal": analysis.signal,
                    "confidence": analysis.confidence,
                    "source": "analyst_agent",
                },
            )
        )

        # If hold, skip to next symbol
        if analysis.signal == "hold" or analysis.confidence < 0.3:
            logger.info(
                "orchestrator_hold",
                symbol=symbol,
                signal=analysis.signal,
                confidence=analysis.confidence,
            )
            return None

        # Stage 2: Risk Assessment
        logger.info("orchestrator_risk_start", symbol=symbol, signal=analysis.signal)
        assessment = await self.risk_agent.assess(analysis, context)
        total_tokens += assessment.tokens_used

        await self._event_bus.publish(
            Event(
                type=EventType.AGENT_RISK_ASSESSED,
                data={
                    "symbol": symbol,
                    "approved": assessment.approved,
                    "position_size": assessment.position_size,
                    "risk_score": assessment.risk_score,
                    "source": "risk_agent",
                },
            )
        )

        if not assessment.approved:
            logger.info(
                "orchestrator_risk_rejected",
                symbol=symbol,
                reasoning=assessment.reasoning[:100],
            )
            completed_at = datetime.now(UTC)
            duration_ms = (completed_at - started_at).total_seconds() * 1000

            return CycleResult(
                status=CycleStatus.NO_ACTION,
                decision=AgentDecision(
                    decision_type=DecisionType.HOLD,
                    symbol=symbol,
                    reasoning=f"Risk rejected: {assessment.reasoning}",
                    confidence=analysis.confidence,
                ),
                tool_results=analysis.tool_results + assessment.tool_results,
                duration_ms=duration_ms,
                tokens_used=total_tokens,
                started_at=started_at,
                completed_at=completed_at,
            )

        # Stage 3: Execution
        logger.info(
            "orchestrator_executor_start",
            symbol=symbol,
            quantity=assessment.position_size,
        )
        execution = await self.executor_agent.execute_trade(analysis, assessment, context)
        total_tokens += execution.tokens_used

        await self._event_bus.publish(
            Event(
                type=EventType.AGENT_EXECUTION_COMPLETED,
                data={
                    "symbol": symbol,
                    "executed": execution.executed,
                    "order_id": execution.order_id,
                    "source": "executor_agent",
                },
            )
        )

        completed_at = datetime.now(UTC)
        duration_ms = (completed_at - started_at).total_seconds() * 1000

        # Determine decision type
        if execution.executed:
            if analysis.signal == "long":
                decision_type = DecisionType.ENTRY_LONG
            else:
                decision_type = DecisionType.ENTRY_SHORT
        else:
            decision_type = DecisionType.HOLD

        status = CycleStatus.SUCCESS if execution.executed else CycleStatus.NO_ACTION

        all_tool_results = analysis.tool_results + assessment.tool_results + execution.tool_results

        return CycleResult(
            status=status,
            decision=AgentDecision(
                decision_type=decision_type,
                symbol=symbol,
                reasoning=execution.reasoning,
                confidence=analysis.confidence,
            ),
            tool_results=all_tool_results,
            duration_ms=duration_ms,
            tokens_used=total_tokens,
            started_at=started_at,
            completed_at=completed_at,
        )

    async def _build_context(self, symbols: list[str]) -> dict[str, Any]:
        """Build context for the pipeline (same pattern as CognitiveAgent)."""
        context: dict[str, Any] = {
            "symbols": symbols,
            "timestamp": datetime.now(UTC).isoformat(),
            "market_data": {},
            "memory_context": {},
        }

        for symbol in symbols:
            try:
                price_result = await self.executor.execute("get_current_price", symbol=symbol)
                if price_result.success:
                    context["market_data"][symbol] = {"price": price_result.data}

                memory_context = await self.memory.build_context_for_decision(
                    symbol=symbol,
                    technical_context={},
                )
                context["memory_context"][symbol] = memory_context.to_dict()
            except Exception:
                logger.warning("orchestrator_context_error", symbol=symbol, exc_info=True)

        return context

    def _update_stats(self, result: CycleResult) -> None:
        """Update orchestrator statistics."""
        self._stats.total_cycles += 1
        self._stats.last_cycle_time = result.completed_at or datetime.now(UTC)
        self._stats.total_tokens_used += result.tokens_used

        if result.status == CycleStatus.SUCCESS:
            self._stats.successful_cycles += 1
        elif result.status == CycleStatus.ERROR:
            self._stats.error_cycles += 1

        if result.decision:
            dt = result.decision.decision_type.value
            self._stats.decisions_by_type[dt] = self._stats.decisions_by_type.get(dt, 0) + 1

        self._stats.total_tool_calls += len(result.tool_results)

        self._cycle_history.append(result)
        if len(self._cycle_history) > 100:
            self._cycle_history = self._cycle_history[-100:]

    async def _publish_cycle_event(self, result: CycleResult) -> None:
        """Publish a cycle completion event."""
        await self._event_bus.publish(
            Event(
                type=EventType.AGENT_CYCLE_COMPLETED,
                data={
                    "source": "agent_orchestrator",
                    "cycle_result": result.to_dict(),
                },
            )
        )

    def get_stats(self) -> dict[str, Any]:
        """Get orchestrator statistics (same interface as CognitiveAgent)."""
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
            "multi_agent": True,
        }

    def get_recent_cycles(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent cycle results."""
        return [r.to_dict() for r in self._cycle_history[-limit:]]


# Global orchestrator instance
_orchestrator: AgentOrchestrator | None = None


def get_agent_orchestrator() -> AgentOrchestrator:
    """Get the global agent orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator
