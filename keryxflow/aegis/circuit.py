"""Circuit breaker for automatic trading shutdown."""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from keryxflow.core.events import EventType, get_event_bus, system_event
from keryxflow.core.logging import get_logger

logger = get_logger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, trading allowed
    OPEN = "open"  # Tripped, trading blocked
    HALF_OPEN = "half_open"  # Testing if safe to resume


class TripReason(str, Enum):
    """Reasons for circuit breaker trip."""

    DAILY_DRAWDOWN = "daily_drawdown"
    CONSECUTIVE_LOSSES = "consecutive_losses"
    RAPID_LOSSES = "rapid_losses"
    MANUAL = "manual"
    EXCHANGE_ERROR = "exchange_error"
    SYSTEM_ERROR = "system_error"


@dataclass
class TripEvent:
    """Record of a circuit breaker trip."""

    timestamp: datetime
    reason: TripReason
    details: str
    balance_at_trip: float
    drawdown_at_trip: float


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    # Drawdown triggers
    max_daily_drawdown: float = 0.05  # 5%
    max_total_drawdown: float = 0.15  # 15%

    # Loss triggers
    max_consecutive_losses: int = 5
    rapid_loss_threshold: float = 0.03  # 3% in short period
    rapid_loss_window_minutes: int = 30

    # Recovery
    cooldown_minutes: int = 60
    require_manual_reset: bool = True

    # Alerts
    warning_drawdown: float = 0.03  # Warn at 3%


@dataclass
class CircuitBreaker:
    """
    Circuit breaker that halts trading under adverse conditions.

    Monitors:
    - Daily drawdown
    - Consecutive losses
    - Rapid losses in short time window
    - System errors

    When tripped, blocks all new trades until manually reset
    or cooldown period expires.
    """

    config: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)

    # State
    state: CircuitState = CircuitState.CLOSED
    trip_reason: TripReason | None = None
    trip_time: datetime | None = None
    trip_events: list[TripEvent] = field(default_factory=list)

    # Tracking
    consecutive_losses: int = 0
    recent_losses: list[tuple[datetime, float]] = field(default_factory=list)
    peak_balance: float = 0.0
    current_balance: float = 0.0
    daily_starting_balance: float = 0.0
    last_reset_date: str = ""

    def __post_init__(self):
        """Initialize event bus."""
        self.event_bus = get_event_bus()

    @property
    def is_tripped(self) -> bool:
        """Check if circuit breaker is tripped (trading blocked)."""
        return self.state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (trading allowed)."""
        return self.state == CircuitState.CLOSED

    @property
    def daily_drawdown(self) -> float:
        """Calculate current daily drawdown."""
        if self.daily_starting_balance <= 0:
            return 0.0
        return (self.daily_starting_balance - self.current_balance) / self.daily_starting_balance

    @property
    def total_drawdown(self) -> float:
        """Calculate drawdown from peak."""
        if self.peak_balance <= 0:
            return 0.0
        return (self.peak_balance - self.current_balance) / self.peak_balance

    def update_balance(self, balance: float) -> None:
        """
        Update current balance and check triggers.

        Args:
            balance: New balance value
        """
        self._check_daily_reset()

        old_balance = self.current_balance
        self.current_balance = balance

        # Update peak
        if balance > self.peak_balance:
            self.peak_balance = balance

        # Check if this is a loss
        if balance < old_balance and old_balance > 0:
            loss_amount = old_balance - balance
            loss_pct = loss_amount / old_balance
            self._record_loss(loss_pct)

        # Check triggers
        self._check_drawdown_triggers()
        self._check_rapid_loss_trigger()

    def record_trade_result(self, is_win: bool, pnl: float = 0.0) -> None:  # noqa: ARG002
        """
        Record a trade result.

        Args:
            is_win: Whether the trade was profitable
            pnl: Profit/loss amount
        """
        if is_win:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            self._check_consecutive_losses()

    def _record_loss(self, loss_pct: float) -> None:
        """Record a loss for rapid loss tracking."""
        now = datetime.now(UTC)
        self.recent_losses.append((now, loss_pct))

        # Clean old losses outside window
        cutoff = now - timedelta(minutes=self.config.rapid_loss_window_minutes)
        self.recent_losses = [(t, loss) for t, loss in self.recent_losses if t > cutoff]

    def _check_daily_reset(self) -> None:
        """Check if daily tracking needs reset."""
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        if self.last_reset_date != today:
            self.daily_starting_balance = self.current_balance
            self.last_reset_date = today
            self.consecutive_losses = 0
            self.recent_losses = []
            logger.info("circuit_breaker_daily_reset", date=today)

    def _check_drawdown_triggers(self) -> None:
        """Check drawdown-based triggers."""
        # Warning level
        if self.daily_drawdown >= self.config.warning_drawdown and self.is_closed:
            logger.warning(
                "drawdown_warning",
                daily=f"{self.daily_drawdown:.1%}",
                limit=f"{self.config.max_daily_drawdown:.1%}",
            )

        # Daily drawdown limit
        if self.daily_drawdown >= self.config.max_daily_drawdown:
            self._trip(
                TripReason.DAILY_DRAWDOWN,
                f"Daily drawdown {self.daily_drawdown:.1%} >= limit {self.config.max_daily_drawdown:.1%}",
            )

        # Total drawdown limit
        if self.total_drawdown >= self.config.max_total_drawdown:
            self._trip(
                TripReason.DAILY_DRAWDOWN,
                f"Total drawdown {self.total_drawdown:.1%} >= limit {self.config.max_total_drawdown:.1%}",
            )

    def _check_consecutive_losses(self) -> None:
        """Check consecutive loss trigger."""
        if self.consecutive_losses >= self.config.max_consecutive_losses:
            self._trip(
                TripReason.CONSECUTIVE_LOSSES,
                f"{self.consecutive_losses} consecutive losses",
            )

    def _check_rapid_loss_trigger(self) -> None:
        """Check rapid loss trigger."""
        if not self.recent_losses:
            return

        total_recent_loss = sum(loss for _, loss in self.recent_losses)
        if total_recent_loss >= self.config.rapid_loss_threshold:
            self._trip(
                TripReason.RAPID_LOSSES,
                f"{total_recent_loss:.1%} loss in {self.config.rapid_loss_window_minutes} minutes",
            )

    def _trip(self, reason: TripReason, details: str) -> None:
        """
        Trip the circuit breaker.

        Args:
            reason: Reason for trip
            details: Detailed explanation
        """
        if self.is_tripped:
            return  # Already tripped

        self.state = CircuitState.OPEN
        self.trip_reason = reason
        self.trip_time = datetime.now(UTC)

        event = TripEvent(
            timestamp=self.trip_time,
            reason=reason,
            details=details,
            balance_at_trip=self.current_balance,
            drawdown_at_trip=self.daily_drawdown,
        )
        self.trip_events.append(event)

        logger.warning(
            "circuit_breaker_tripped",
            reason=reason.value,
            details=details,
            balance=self.current_balance,
        )

        # Publish event
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(
                    self.event_bus.publish(
                        system_event(
                            EventType.CIRCUIT_BREAKER_TRIPPED,
                            f"Circuit breaker tripped: {details}",
                        )
                    )
                )
        except RuntimeError:
            pass  # No event loop running

    def trip_manual(self, reason: str = "Manual activation") -> None:
        """
        Manually trip the circuit breaker.

        Args:
            reason: Reason for manual trip
        """
        self._trip(TripReason.MANUAL, reason)

    def trip_on_error(self, error: str) -> None:
        """
        Trip due to system error.

        Args:
            error: Error description
        """
        self._trip(TripReason.SYSTEM_ERROR, error)

    def reset(self, force: bool = False) -> bool:
        """
        Reset the circuit breaker.

        Args:
            force: Force reset even if cooldown not complete

        Returns:
            True if reset successful
        """
        if not self.is_tripped:
            return True

        # Check cooldown
        if not force and self.trip_time:
            cooldown_end = self.trip_time + timedelta(minutes=self.config.cooldown_minutes)
            if datetime.now(UTC) < cooldown_end:
                remaining = (cooldown_end - datetime.now(UTC)).seconds // 60
                logger.warning("circuit_breaker_cooldown", minutes_remaining=remaining)
                return False

        self.state = CircuitState.CLOSED
        self.trip_reason = None
        self.trip_time = None
        self.consecutive_losses = 0
        self.recent_losses = []

        logger.info("circuit_breaker_reset")

        return True

    def can_trade(self) -> tuple[bool, str]:
        """
        Check if trading is allowed.

        Returns:
            Tuple of (can_trade, reason)
        """
        if self.is_tripped:
            return (False, f"Circuit breaker active: {self.trip_reason.value if self.trip_reason else 'unknown'}")

        if self.daily_drawdown >= self.config.warning_drawdown:
            return (True, f"Warning: Daily drawdown at {self.daily_drawdown:.1%}")

        return (True, "Trading allowed")

    def get_status(self) -> dict[str, Any]:
        """Get current circuit breaker status."""
        return {
            "state": self.state.value,
            "is_tripped": self.is_tripped,
            "trip_reason": self.trip_reason.value if self.trip_reason else None,
            "trip_time": self.trip_time.isoformat() if self.trip_time else None,
            "daily_drawdown": self.daily_drawdown,
            "total_drawdown": self.total_drawdown,
            "consecutive_losses": self.consecutive_losses,
            "recent_loss_count": len(self.recent_losses),
            "trip_count": len(self.trip_events),
        }

    def format_status_simple(self) -> str:
        """Format status for simple display."""
        if self.is_tripped:
            reason_text = {
                TripReason.DAILY_DRAWDOWN: "Lost too much today",
                TripReason.CONSECUTIVE_LOSSES: "Too many losing trades in a row",
                TripReason.RAPID_LOSSES: "Losing money too fast",
                TripReason.MANUAL: "Manually paused",
                TripReason.EXCHANGE_ERROR: "Exchange problem",
                TripReason.SYSTEM_ERROR: "System error",
            }.get(self.trip_reason, "Unknown reason")

            return f"🔴 TRADING PAUSED\n   Reason: {reason_text}\n   Reset required to continue."

        if self.daily_drawdown >= self.config.warning_drawdown:
            return f"🟡 WARNING\n   Daily loss: {self.daily_drawdown:.1%}\n   Limit: {self.config.max_daily_drawdown:.1%}"

        return f"🟢 ACTIVE\n   Daily: {self.daily_drawdown:+.1%}\n   Losses in row: {self.consecutive_losses}"


# Global instance
_circuit_breaker: CircuitBreaker | None = None


def get_circuit_breaker(config: CircuitBreakerConfig | None = None) -> CircuitBreaker:
    """Get the global circuit breaker instance."""
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = CircuitBreaker(config=config or CircuitBreakerConfig())
    return _circuit_breaker
