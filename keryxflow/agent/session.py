"""Trading session management for AI-first autonomous trading.

This module provides session management for the Cognitive Agent,
allowing control over trading sessions with start, pause, resume, and stop operations.
"""

import asyncio
import contextlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from keryxflow.config import get_settings
from keryxflow.core.events import Event, EventType, get_event_bus
from keryxflow.core.logging import get_logger

if TYPE_CHECKING:
    from keryxflow.agent.cognitive import CognitiveAgent
    from keryxflow.core.engine import TradingEngine

logger = get_logger(__name__)


class SessionState(str, Enum):
    """State of a trading session."""

    IDLE = "idle"  # Not started
    STARTING = "starting"  # Initializing
    RUNNING = "running"  # Active trading
    PAUSED = "paused"  # Temporarily stopped
    STOPPING = "stopping"  # Shutting down
    STOPPED = "stopped"  # Cleanly stopped
    ERROR = "error"  # Stopped due to error


@dataclass
class SessionStats:
    """Statistics for a trading session."""

    started_at: datetime | None = None
    stopped_at: datetime | None = None
    paused_at: datetime | None = None
    total_paused_time_seconds: float = 0.0

    cycles_completed: int = 0
    cycles_successful: int = 0
    cycles_failed: int = 0
    cycles_fallback: int = 0

    trades_executed: int = 0
    trades_won: int = 0
    trades_lost: int = 0
    total_pnl: float = 0.0

    tool_calls: int = 0
    tokens_used: int = 0

    errors: list[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        """Get session duration in seconds (excluding paused time)."""
        if self.started_at is None:
            return 0.0

        end_time = self.stopped_at or datetime.now(UTC)
        total = (end_time - self.started_at).total_seconds()
        return total - self.total_paused_time_seconds

    @property
    def win_rate(self) -> float:
        """Get win rate as percentage."""
        total = self.trades_won + self.trades_lost
        if total == 0:
            return 0.0
        return (self.trades_won / total) * 100

    @property
    def cycles_per_minute(self) -> float:
        """Get average cycles per minute."""
        duration_minutes = self.duration_seconds / 60
        if duration_minutes == 0:
            return 0.0
        return self.cycles_completed / duration_minutes

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
            "duration_seconds": self.duration_seconds,
            "total_paused_time_seconds": self.total_paused_time_seconds,
            "cycles_completed": self.cycles_completed,
            "cycles_successful": self.cycles_successful,
            "cycles_failed": self.cycles_failed,
            "cycles_fallback": self.cycles_fallback,
            "trades_executed": self.trades_executed,
            "trades_won": self.trades_won,
            "trades_lost": self.trades_lost,
            "total_pnl": self.total_pnl,
            "win_rate": self.win_rate,
            "cycles_per_minute": self.cycles_per_minute,
            "tool_calls": self.tool_calls,
            "tokens_used": self.tokens_used,
            "errors_count": len(self.errors),
        }


class TradingSession:
    """Manages a trading session with the Cognitive Agent.

    The TradingSession provides control over autonomous trading:
    - Start/stop trading sessions
    - Pause/resume trading
    - Monitor session statistics
    - Handle graceful shutdown

    Example:
        session = TradingSession()
        await session.start()

        # Trading runs autonomously...

        await session.pause()  # Temporarily pause
        await session.resume()  # Resume trading

        await session.stop()  # Stop session
    """

    def __init__(
        self,
        engine: "TradingEngine | None" = None,
        agent: "CognitiveAgent | None" = None,
        symbols: list[str] | None = None,
    ):
        """Initialize the trading session.

        Args:
            engine: Trading engine instance. Created if None.
            agent: Cognitive agent instance. Created if None.
            symbols: Symbols to trade. Uses settings if None.
        """
        self._engine = engine
        self._agent = agent
        self._symbols = symbols or get_settings().system.symbols
        self._event_bus = get_event_bus()
        self._settings = get_settings()

        self._state = SessionState.IDLE
        self._stats = SessionStats()
        self._session_id = self._generate_session_id()

        # Background task for agent loop
        self._agent_task: asyncio.Task | None = None
        self._shutdown_event = asyncio.Event()

    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        return f"session_{timestamp}"

    @property
    def state(self) -> SessionState:
        """Get current session state."""
        return self._state

    @property
    def stats(self) -> SessionStats:
        """Get session statistics."""
        return self._stats

    @property
    def session_id(self) -> str:
        """Get session ID."""
        return self._session_id

    @property
    def is_running(self) -> bool:
        """Check if session is running."""
        return self._state == SessionState.RUNNING

    @property
    def is_paused(self) -> bool:
        """Check if session is paused."""
        return self._state == SessionState.PAUSED

    async def start(self) -> bool:
        """Start the trading session.

        Returns:
            True if started successfully, False otherwise
        """
        if self._state not in (SessionState.IDLE, SessionState.STOPPED):
            logger.warning(
                "session_start_invalid_state",
                current_state=self._state.value,
            )
            return False

        old_state = self._state
        self._state = SessionState.STARTING
        self._stats = SessionStats()  # Reset stats
        self._stats.started_at = datetime.now(UTC)
        self._shutdown_event.clear()

        try:
            # Initialize agent if needed
            if self._agent is None:
                from keryxflow.agent.cognitive import get_cognitive_agent

                self._agent = get_cognitive_agent()

            await self._agent.initialize()

            # Initialize engine if needed
            if self._engine is None:
                from keryxflow.core.engine import TradingEngine
                from keryxflow.exchange import get_exchange_adapter
                from keryxflow.exchange.paper import get_paper_engine

                exchange = get_exchange_adapter()
                paper = get_paper_engine()
                self._engine = TradingEngine(
                    exchange_client=exchange,
                    paper_engine=paper,
                    cognitive_agent=self._agent,
                )
                # Start the engine only if we created it
                await self._engine.start()
            elif not self._engine._running:
                # Start the engine if it's not running
                await self._engine.start()

            # Start agent loop as background task
            self._agent_task = asyncio.create_task(self._run_agent_loop())

            self._state = SessionState.RUNNING

            # Publish event
            await self._publish_state_event(old_state)

            logger.info(
                "trading_session_started",
                session_id=self._session_id,
                symbols=self._symbols,
            )

            return True

        except Exception as e:
            import traceback

            self._state = SessionState.ERROR
            error_msg = f"{type(e).__name__}: {str(e)}"
            self._stats.errors.append(error_msg)
            logger.error("session_start_failed", error=error_msg, tb=traceback.format_exc())
            return False

    async def stop(self) -> bool:
        """Stop the trading session.

        Returns:
            True if stopped successfully, False otherwise
        """
        if self._state not in (SessionState.RUNNING, SessionState.PAUSED, SessionState.ERROR):
            logger.warning(
                "session_stop_invalid_state",
                current_state=self._state.value,
            )
            return False

        old_state = self._state
        self._state = SessionState.STOPPING

        try:
            # Signal shutdown
            self._shutdown_event.set()

            # Cancel agent task
            if self._agent_task and not self._agent_task.done():
                self._agent_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._agent_task

            # Stop engine
            if self._engine:
                await self._engine.stop()

            self._stats.stopped_at = datetime.now(UTC)
            self._state = SessionState.STOPPED

            # Publish event
            await self._publish_state_event(old_state)

            logger.info(
                "trading_session_stopped",
                session_id=self._session_id,
                duration_seconds=self._stats.duration_seconds,
                cycles=self._stats.cycles_completed,
            )

            return True

        except Exception as e:
            self._state = SessionState.ERROR
            self._stats.errors.append(str(e))
            logger.error("session_stop_failed", error=str(e))
            return False

    async def pause(self) -> bool:
        """Pause the trading session.

        Returns:
            True if paused successfully, False otherwise
        """
        if self._state != SessionState.RUNNING:
            logger.warning(
                "session_pause_invalid_state",
                current_state=self._state.value,
            )
            return False

        old_state = self._state
        self._state = SessionState.PAUSED
        self._stats.paused_at = datetime.now(UTC)

        # Publish pause event to engine
        await self._event_bus.publish(
            Event(type=EventType.SYSTEM_PAUSED, data={"session_id": self._session_id})
        )

        # Publish state event
        await self._publish_state_event(old_state)

        logger.info("trading_session_paused", session_id=self._session_id)
        return True

    async def resume(self) -> bool:
        """Resume the trading session.

        Returns:
            True if resumed successfully, False otherwise
        """
        if self._state != SessionState.PAUSED:
            logger.warning(
                "session_resume_invalid_state",
                current_state=self._state.value,
            )
            return False

        old_state = self._state

        # Calculate paused time
        if self._stats.paused_at:
            paused_duration = (datetime.now(UTC) - self._stats.paused_at).total_seconds()
            self._stats.total_paused_time_seconds += paused_duration
            self._stats.paused_at = None

        self._state = SessionState.RUNNING

        # Publish resume event to engine
        await self._event_bus.publish(
            Event(type=EventType.SYSTEM_RESUMED, data={"session_id": self._session_id})
        )

        # Publish state event
        await self._publish_state_event(old_state)

        logger.info("trading_session_resumed", session_id=self._session_id)
        return True

    async def _run_agent_loop(self) -> None:
        """Run the agent loop in the background."""
        cycle_interval = self._settings.agent.cycle_interval

        while not self._shutdown_event.is_set():
            if self._state == SessionState.RUNNING and self._agent is not None:
                try:
                    # Run agent cycle
                    result = await self._agent.run_cycle(self._symbols)

                    # Update stats
                    self._stats.cycles_completed += 1

                    if result.status.value == "success":
                        self._stats.cycles_successful += 1
                    elif result.status.value == "fallback":
                        self._stats.cycles_fallback += 1
                    elif result.status.value == "error":
                        self._stats.cycles_failed += 1
                        if result.error:
                            self._stats.errors.append(result.error)

                    self._stats.tool_calls += len(result.tool_results)
                    self._stats.tokens_used += result.tokens_used

                except Exception as e:
                    self._stats.cycles_failed += 1
                    self._stats.errors.append(str(e))
                    logger.error("agent_loop_error", error=str(e))

            # Wait for next cycle
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=cycle_interval,
                )
                break  # Shutdown requested
            except TimeoutError:
                pass  # Continue loop

    async def _publish_state_event(self, old_state: SessionState | None = None) -> None:
        """Publish session state change event."""
        await self._event_bus.publish(
            Event(
                type=EventType.SESSION_STATE_CHANGED,
                data={
                    "session_id": self._session_id,
                    "new_state": self._state.value,
                    "old_state": old_state.value if old_state else "unknown",
                    "stats": self._stats.to_dict(),
                },
            )
        )

    def get_status(self) -> dict[str, Any]:
        """Get current session status.

        Returns:
            Dictionary with session status
        """
        agent_stats = None
        if self._agent:
            agent_stats = {
                "total_cycles": self._agent._stats.total_cycles,
                "successful_cycles": self._agent._stats.successful_cycles,
                "consecutive_errors": self._agent._stats.consecutive_errors,
            }

        return {
            "session_id": self._session_id,
            "state": self._state.value,
            "symbols": self._symbols,
            "stats": self._stats.to_dict(),
            "agent_stats": agent_stats,
            "engine_running": self._engine._running if self._engine else False,
        }

    def record_trade(self, won: bool, pnl: float) -> None:
        """Record a completed trade.

        Args:
            won: Whether the trade was profitable
            pnl: Profit/loss amount
        """
        self._stats.trades_executed += 1
        self._stats.total_pnl += pnl

        if won:
            self._stats.trades_won += 1
        else:
            self._stats.trades_lost += 1


# Global singleton
_session: TradingSession | None = None


def get_trading_session() -> TradingSession:
    """Get the global TradingSession singleton.

    Returns:
        TradingSession instance
    """
    global _session
    if _session is None:
        _session = TradingSession()
    return _session
