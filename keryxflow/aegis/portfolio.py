"""Portfolio state tracking for aggregate risk management.

This module provides classes to track the current state of the portfolio
including all open positions and their aggregate risk metrics. This is
essential for the guardrails to enforce portfolio-level limits.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from keryxflow.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PositionState:
    """
    State of an individual position.

    Tracks entry details and calculates risk metrics for a single position.
    """

    symbol: str
    side: str  # "long" or "short"
    quantity: Decimal
    entry_price: Decimal
    current_price: Decimal
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    opened_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def position_value(self) -> Decimal:
        """Current value of the position."""
        return self.quantity * self.current_price

    @property
    def entry_value(self) -> Decimal:
        """Value at entry."""
        return self.quantity * self.entry_price

    @property
    def unrealized_pnl(self) -> Decimal:
        """Unrealized profit/loss."""
        if self.side == "long":
            return (self.current_price - self.entry_price) * self.quantity
        else:  # short
            return (self.entry_price - self.current_price) * self.quantity

    @property
    def unrealized_pnl_pct(self) -> Decimal:
        """Unrealized P&L as percentage of entry value."""
        if self.entry_value == 0:
            return Decimal("0")
        return self.unrealized_pnl / self.entry_value

    @property
    def risk_to_stop(self) -> Decimal:
        """
        Risk amount if stop loss is hit.

        If no stop loss is set, assumes 100% of position value is at risk.
        """
        if self.stop_loss is None:
            return self.position_value

        if self.side == "long":
            risk_per_unit = self.entry_price - self.stop_loss
        else:  # short
            risk_per_unit = self.stop_loss - self.entry_price

        # Ensure risk is positive
        risk_per_unit = max(Decimal("0"), risk_per_unit)
        return risk_per_unit * self.quantity

    @property
    def reward_to_target(self) -> Decimal:
        """Potential reward if take profit is hit."""
        if self.take_profit is None:
            return Decimal("0")

        if self.side == "long":
            reward_per_unit = self.take_profit - self.entry_price
        else:  # short
            reward_per_unit = self.entry_price - self.take_profit

        reward_per_unit = max(Decimal("0"), reward_per_unit)
        return reward_per_unit * self.quantity

    @property
    def risk_reward_ratio(self) -> Decimal | None:
        """Risk/reward ratio. None if no take profit set."""
        if self.take_profit is None or self.stop_loss is None:
            return None

        risk = self.risk_to_stop
        reward = self.reward_to_target

        if risk == 0:
            return None

        return reward / risk

    def update_price(self, price: float | Decimal) -> None:
        """Update current price."""
        self.current_price = Decimal(str(price))


@dataclass
class PortfolioState:
    """
    Aggregate portfolio state for risk management.

    Tracks all open positions and calculates portfolio-level risk metrics.
    This is the primary input to the GuardrailEnforcer for validating orders.
    """

    # Core values
    total_value: Decimal = Decimal("10000")
    cash_available: Decimal = Decimal("10000")

    # Peak tracking for drawdown
    peak_value: Decimal = Decimal("10000")

    # Open positions
    positions: list[PositionState] = field(default_factory=list)

    # Daily tracking
    daily_starting_value: Decimal = Decimal("10000")
    daily_pnl: Decimal = Decimal("0")
    trades_today: int = 0

    # Weekly tracking
    weekly_starting_value: Decimal = Decimal("10000")
    weekly_pnl: Decimal = Decimal("0")

    # Hourly rate limiting
    trades_this_hour: int = 0
    hour_start: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Loss tracking
    consecutive_losses: int = 0

    # Timestamps
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))
    daily_reset_date: datetime = field(default_factory=lambda: datetime.now(UTC).date())

    @property
    def total_exposure(self) -> Decimal:
        """Sum of all open position values."""
        return sum((p.position_value for p in self.positions), Decimal("0"))

    @property
    def total_risk_at_stop(self) -> Decimal:
        """
        Sum of all position risks if all stops are hit simultaneously.

        This is the key metric for Issue #9 fix - aggregate portfolio risk.
        """
        return sum((p.risk_to_stop for p in self.positions), Decimal("0"))

    @property
    def exposure_pct(self) -> Decimal:
        """Total exposure as percentage of portfolio value."""
        if self.total_value == 0:
            return Decimal("0")
        return self.total_exposure / self.total_value

    @property
    def risk_at_stop_pct(self) -> Decimal:
        """
        Total portfolio risk as percentage if all stops hit.

        This percentage should not exceed MAX_DAILY_LOSS_PCT from guardrails.
        """
        if self.total_value == 0:
            return Decimal("0")
        return self.total_risk_at_stop / self.total_value

    @property
    def cash_reserve_pct(self) -> Decimal:
        """Cash available as percentage of total value."""
        if self.total_value == 0:
            return Decimal("0")
        return self.cash_available / self.total_value

    @property
    def unrealized_pnl(self) -> Decimal:
        """Total unrealized P&L across all positions."""
        return sum((p.unrealized_pnl for p in self.positions), Decimal("0"))

    @property
    def drawdown_pct(self) -> Decimal:
        """Current drawdown from peak as percentage."""
        if self.peak_value == 0:
            return Decimal("0")
        return (self.peak_value - self.total_value) / self.peak_value

    @property
    def position_count(self) -> int:
        """Number of open positions."""
        return len(self.positions)

    def add_position(self, position: PositionState) -> None:
        """
        Add a new position to the portfolio.

        Args:
            position: Position to add
        """
        self.positions.append(position)
        self.cash_available -= position.entry_value
        self.trades_today += 1
        self.trades_this_hour += 1
        self._update_total_value()
        logger.info(
            "position_added",
            symbol=position.symbol,
            side=position.side,
            quantity=float(position.quantity),
            entry_price=float(position.entry_price),
            positions_count=len(self.positions),
        )

    def close_position(self, symbol: str, exit_price: float | Decimal) -> Decimal | None:
        """
        Close a position and realize P&L.

        Args:
            symbol: Symbol of position to close
            exit_price: Price at which position was closed

        Returns:
            Realized P&L or None if position not found
        """
        exit_price = Decimal(str(exit_price))

        for i, pos in enumerate(self.positions):
            if pos.symbol == symbol:
                # Calculate realized P&L
                pos.current_price = exit_price
                realized_pnl = pos.unrealized_pnl

                # Update cash
                self.cash_available += pos.entry_value + realized_pnl

                # Update P&L tracking
                self.daily_pnl += realized_pnl
                self.weekly_pnl += realized_pnl

                # Update consecutive losses
                if realized_pnl < 0:
                    self.consecutive_losses += 1
                else:
                    self.consecutive_losses = 0

                # Remove position
                self.positions.pop(i)
                self._update_total_value()

                logger.info(
                    "position_closed",
                    symbol=symbol,
                    realized_pnl=float(realized_pnl),
                    daily_pnl=float(self.daily_pnl),
                    consecutive_losses=self.consecutive_losses,
                )

                return realized_pnl

        logger.warning("position_not_found", symbol=symbol)
        return None

    def update_prices(self, prices: dict[str, float | Decimal]) -> None:
        """
        Update current prices for all positions.

        Args:
            prices: Dict mapping symbol to current price
        """
        for pos in self.positions:
            if pos.symbol in prices:
                pos.update_price(prices[pos.symbol])

        self._update_total_value()

    def _update_total_value(self) -> None:
        """Recalculate total portfolio value."""
        self.total_value = self.cash_available + self.total_exposure
        self.last_updated = datetime.now(UTC)

        # Update peak if new high
        if self.total_value > self.peak_value:
            self.peak_value = self.total_value

    def reset_daily(self) -> None:
        """Reset daily tracking metrics."""
        self.daily_starting_value = self.total_value
        self.daily_pnl = Decimal("0")
        self.trades_today = 0
        self.daily_reset_date = datetime.now(UTC).date()
        logger.info("daily_reset", starting_value=float(self.daily_starting_value))

    def reset_weekly(self) -> None:
        """Reset weekly tracking metrics."""
        self.weekly_starting_value = self.total_value
        self.weekly_pnl = Decimal("0")
        logger.info("weekly_reset", starting_value=float(self.weekly_starting_value))

    def reset_hourly(self) -> None:
        """Reset hourly rate limiting."""
        self.trades_this_hour = 0
        self.hour_start = datetime.now(UTC)

    def reset_consecutive_losses(self) -> None:
        """Manually reset consecutive losses counter."""
        self.consecutive_losses = 0
        logger.info("consecutive_losses_reset")

    def get_position(self, symbol: str) -> PositionState | None:
        """Get position by symbol."""
        for pos in self.positions:
            if pos.symbol == symbol:
                return pos
        return None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "total_value": float(self.total_value),
            "cash_available": float(self.cash_available),
            "peak_value": float(self.peak_value),
            "total_exposure": float(self.total_exposure),
            "total_risk_at_stop": float(self.total_risk_at_stop),
            "exposure_pct": float(self.exposure_pct),
            "risk_at_stop_pct": float(self.risk_at_stop_pct),
            "cash_reserve_pct": float(self.cash_reserve_pct),
            "unrealized_pnl": float(self.unrealized_pnl),
            "drawdown_pct": float(self.drawdown_pct),
            "daily_pnl": float(self.daily_pnl),
            "weekly_pnl": float(self.weekly_pnl),
            "trades_today": self.trades_today,
            "consecutive_losses": self.consecutive_losses,
            "position_count": self.position_count,
            "positions": [
                {
                    "symbol": p.symbol,
                    "side": p.side,
                    "quantity": float(p.quantity),
                    "entry_price": float(p.entry_price),
                    "current_price": float(p.current_price),
                    "unrealized_pnl": float(p.unrealized_pnl),
                    "risk_to_stop": float(p.risk_to_stop),
                }
                for p in self.positions
            ],
        }


def create_portfolio_state(
    initial_balance: float = 10000.0,
) -> PortfolioState:
    """
    Create a new portfolio state with initial balance.

    Args:
        initial_balance: Starting balance

    Returns:
        New PortfolioState instance
    """
    balance = Decimal(str(initial_balance))
    return PortfolioState(
        total_value=balance,
        cash_available=balance,
        peak_value=balance,
        daily_starting_value=balance,
        weekly_starting_value=balance,
    )
