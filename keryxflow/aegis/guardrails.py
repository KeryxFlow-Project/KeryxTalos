"""Immutable trading guardrails - hardcoded safety limits.

These limits are defined in code, not configuration, and cannot be modified
at runtime. They represent absolute safety boundaries that the AI agent
cannot bypass under any circumstances.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from keryxflow.core.logging import get_logger

if TYPE_CHECKING:
    from keryxflow.aegis.portfolio import PortfolioState

logger = get_logger(__name__)


class GuardrailViolation(str, Enum):
    """Types of guardrail violations."""

    POSITION_TOO_LARGE = "position_too_large"
    TOTAL_EXPOSURE_EXCEEDED = "total_exposure_exceeded"
    INSUFFICIENT_RESERVE = "insufficient_reserve"
    DAILY_LOSS_EXCEEDED = "daily_loss_exceeded"
    WEEKLY_LOSS_EXCEEDED = "weekly_loss_exceeded"
    TOTAL_DRAWDOWN_EXCEEDED = "total_drawdown_exceeded"
    CONSECUTIVE_LOSSES_HALT = "consecutive_losses_halt"
    TRADE_RATE_EXCEEDED = "trade_rate_exceeded"
    SYMBOL_NOT_ALLOWED = "symbol_not_allowed"
    INVALID_ORDER_TYPE = "invalid_order_type"


@dataclass(frozen=True)
class TradingGuardrails:
    """
    Immutable trading guardrails.

    These are absolute limits that cannot be changed at runtime.
    They are defined as a frozen dataclass to ensure immutability.

    The values here represent conservative defaults that prioritize
    capital preservation over profit maximization.
    """

    # === Position Limits ===
    # Maximum percentage of portfolio in a single position
    MAX_POSITION_SIZE_PCT: Decimal = Decimal("0.10")  # 10%

    # Maximum total exposure across all positions
    MAX_TOTAL_EXPOSURE_PCT: Decimal = Decimal("0.50")  # 50%

    # Minimum cash reserve that must always be maintained
    MIN_CASH_RESERVE_PCT: Decimal = Decimal("0.20")  # 20%

    # === Loss Limits ===
    # Maximum loss per individual trade
    MAX_LOSS_PER_TRADE_PCT: Decimal = Decimal("0.02")  # 2%

    # Maximum daily loss before trading halt
    MAX_DAILY_LOSS_PCT: Decimal = Decimal("0.05")  # 5%

    # Maximum weekly loss before trading halt
    MAX_WEEKLY_LOSS_PCT: Decimal = Decimal("0.10")  # 10%

    # Maximum total drawdown from peak
    MAX_TOTAL_DRAWDOWN_PCT: Decimal = Decimal("0.20")  # 20%

    # === Rate Limits ===
    # Maximum trades per hour
    MAX_TRADES_PER_HOUR: int = 10

    # Maximum trades per day
    MAX_TRADES_PER_DAY: int = 50

    # === Circuit Breakers ===
    # Halt trading after this many consecutive losses
    CONSECUTIVE_LOSSES_HALT: int = 5

    # === Allowed Symbols ===
    # Only these symbols can be traded
    ALLOWED_SYMBOLS: tuple[str, ...] = ("BTC/USDT", "ETH/USDT", "SOL/USDT")

    # === Allowed Order Types ===
    ALLOWED_ORDER_TYPES: tuple[str, ...] = ("market", "limit")
    ALLOWED_SIDES: tuple[str, ...] = ("buy", "sell")


# Global singleton instance
_guardrails: TradingGuardrails | None = None


def get_guardrails() -> TradingGuardrails:
    """Get the global guardrails instance."""
    global _guardrails
    if _guardrails is None:
        _guardrails = TradingGuardrails()
    return _guardrails


@dataclass
class GuardrailCheckResult:
    """Result of a guardrail check."""

    allowed: bool
    violation: GuardrailViolation | None = None
    message: str = ""
    details: dict | None = None

    @property
    def blocked(self) -> bool:
        """Check if the action was blocked."""
        return not self.allowed


class GuardrailEnforcer:
    """
    Enforces trading guardrails on all actions.

    This class validates orders and actions against the immutable
    guardrails before they can be executed. It cannot be bypassed.
    """

    def __init__(self, guardrails: TradingGuardrails | None = None):
        """
        Initialize the enforcer.

        Args:
            guardrails: Guardrails to enforce. Uses global instance if None.
        """
        self.guardrails = guardrails or get_guardrails()

    def validate_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        stop_loss: float | None,
        portfolio: "PortfolioState",
    ) -> GuardrailCheckResult:
        """
        Validate an order against all guardrails.

        Args:
            symbol: Trading pair
            side: Order side (buy/sell)
            quantity: Order quantity
            entry_price: Entry price
            stop_loss: Stop loss price
            portfolio: Current portfolio state

        Returns:
            GuardrailCheckResult with allowed status and any violation details
        """
        g = self.guardrails

        # Check symbol allowed
        if symbol not in g.ALLOWED_SYMBOLS:
            return GuardrailCheckResult(
                allowed=False,
                violation=GuardrailViolation.SYMBOL_NOT_ALLOWED,
                message=f"Symbol '{symbol}' not in allowed list: {g.ALLOWED_SYMBOLS}",
            )

        # Check side allowed
        if side not in g.ALLOWED_SIDES:
            return GuardrailCheckResult(
                allowed=False,
                violation=GuardrailViolation.INVALID_ORDER_TYPE,
                message=f"Side '{side}' not allowed. Must be one of: {g.ALLOWED_SIDES}",
            )

        # Calculate position value
        position_value = Decimal(str(quantity)) * Decimal(str(entry_price))
        total_value = portfolio.total_value

        if total_value <= 0:
            return GuardrailCheckResult(
                allowed=False,
                violation=GuardrailViolation.INSUFFICIENT_RESERVE,
                message="Portfolio value is zero or negative",
            )

        # Check position size limit
        position_pct = position_value / total_value
        if position_pct > g.MAX_POSITION_SIZE_PCT:
            return GuardrailCheckResult(
                allowed=False,
                violation=GuardrailViolation.POSITION_TOO_LARGE,
                message=f"Position size {position_pct:.1%} exceeds max {g.MAX_POSITION_SIZE_PCT:.1%}",
                details={
                    "position_pct": float(position_pct),
                    "max_pct": float(g.MAX_POSITION_SIZE_PCT),
                    "max_value": float(total_value * g.MAX_POSITION_SIZE_PCT),
                },
            )

        # Check total exposure
        new_exposure = portfolio.total_exposure + position_value
        exposure_pct = new_exposure / total_value
        if exposure_pct > g.MAX_TOTAL_EXPOSURE_PCT:
            return GuardrailCheckResult(
                allowed=False,
                violation=GuardrailViolation.TOTAL_EXPOSURE_EXCEEDED,
                message=f"Total exposure {exposure_pct:.1%} would exceed max {g.MAX_TOTAL_EXPOSURE_PCT:.1%}",
                details={
                    "current_exposure": float(portfolio.total_exposure),
                    "new_exposure": float(new_exposure),
                    "exposure_pct": float(exposure_pct),
                    "max_pct": float(g.MAX_TOTAL_EXPOSURE_PCT),
                },
            )

        # Check cash reserve
        remaining_cash = portfolio.cash_available - position_value
        reserve_pct = remaining_cash / total_value
        if reserve_pct < g.MIN_CASH_RESERVE_PCT:
            return GuardrailCheckResult(
                allowed=False,
                violation=GuardrailViolation.INSUFFICIENT_RESERVE,
                message=f"Cash reserve would drop to {reserve_pct:.1%}, below min {g.MIN_CASH_RESERVE_PCT:.1%}",
                details={
                    "remaining_cash": float(remaining_cash),
                    "reserve_pct": float(reserve_pct),
                    "min_pct": float(g.MIN_CASH_RESERVE_PCT),
                },
            )

        # Check risk per trade (if stop loss provided)
        if stop_loss is not None:
            risk_per_unit = abs(Decimal(str(entry_price)) - Decimal(str(stop_loss)))
            trade_risk = risk_per_unit * Decimal(str(quantity))
            trade_risk_pct = trade_risk / total_value

            if trade_risk_pct > g.MAX_LOSS_PER_TRADE_PCT:
                return GuardrailCheckResult(
                    allowed=False,
                    violation=GuardrailViolation.DAILY_LOSS_EXCEEDED,
                    message=f"Trade risk {trade_risk_pct:.1%} exceeds max {g.MAX_LOSS_PER_TRADE_PCT:.1%}",
                    details={
                        "trade_risk": float(trade_risk),
                        "trade_risk_pct": float(trade_risk_pct),
                        "max_pct": float(g.MAX_LOSS_PER_TRADE_PCT),
                    },
                )

            # Check aggregate risk (Issue #9 fix)
            new_total_risk = portfolio.total_risk_at_stop + trade_risk
            new_total_risk_pct = new_total_risk / total_value

            if new_total_risk_pct > g.MAX_DAILY_LOSS_PCT:
                return GuardrailCheckResult(
                    allowed=False,
                    violation=GuardrailViolation.DAILY_LOSS_EXCEEDED,
                    message=f"Aggregate risk {new_total_risk_pct:.1%} would exceed daily limit {g.MAX_DAILY_LOSS_PCT:.1%}",
                    details={
                        "current_risk": float(portfolio.total_risk_at_stop),
                        "new_trade_risk": float(trade_risk),
                        "total_risk": float(new_total_risk),
                        "total_risk_pct": float(new_total_risk_pct),
                        "max_pct": float(g.MAX_DAILY_LOSS_PCT),
                    },
                )

        # Check daily loss
        if portfolio.daily_pnl < 0:
            daily_loss_pct = abs(portfolio.daily_pnl) / portfolio.daily_starting_value
            if Decimal(str(daily_loss_pct)) >= g.MAX_DAILY_LOSS_PCT:
                return GuardrailCheckResult(
                    allowed=False,
                    violation=GuardrailViolation.DAILY_LOSS_EXCEEDED,
                    message=f"Daily loss {daily_loss_pct:.1%} has reached limit {g.MAX_DAILY_LOSS_PCT:.1%}",
                    details={
                        "daily_pnl": float(portfolio.daily_pnl),
                        "daily_loss_pct": float(daily_loss_pct),
                        "max_pct": float(g.MAX_DAILY_LOSS_PCT),
                    },
                )

        # Check weekly loss
        if portfolio.weekly_pnl < 0:
            weekly_loss_pct = abs(portfolio.weekly_pnl) / portfolio.weekly_starting_value
            if Decimal(str(weekly_loss_pct)) >= g.MAX_WEEKLY_LOSS_PCT:
                return GuardrailCheckResult(
                    allowed=False,
                    violation=GuardrailViolation.WEEKLY_LOSS_EXCEEDED,
                    message=f"Weekly loss {weekly_loss_pct:.1%} has reached limit {g.MAX_WEEKLY_LOSS_PCT:.1%}",
                    details={
                        "weekly_pnl": float(portfolio.weekly_pnl),
                        "weekly_loss_pct": float(weekly_loss_pct),
                        "max_pct": float(g.MAX_WEEKLY_LOSS_PCT),
                    },
                )

        # Check consecutive losses
        if portfolio.consecutive_losses >= g.CONSECUTIVE_LOSSES_HALT:
            return GuardrailCheckResult(
                allowed=False,
                violation=GuardrailViolation.CONSECUTIVE_LOSSES_HALT,
                message=f"Trading halted after {portfolio.consecutive_losses} consecutive losses",
                details={
                    "consecutive_losses": portfolio.consecutive_losses,
                    "limit": g.CONSECUTIVE_LOSSES_HALT,
                },
            )

        # Check trade rate limits
        if portfolio.trades_today >= g.MAX_TRADES_PER_DAY:
            return GuardrailCheckResult(
                allowed=False,
                violation=GuardrailViolation.TRADE_RATE_EXCEEDED,
                message=f"Daily trade limit reached: {portfolio.trades_today}/{g.MAX_TRADES_PER_DAY}",
                details={
                    "trades_today": portfolio.trades_today,
                    "max_trades": g.MAX_TRADES_PER_DAY,
                },
            )

        if portfolio.trades_this_hour >= g.MAX_TRADES_PER_HOUR:
            return GuardrailCheckResult(
                allowed=False,
                violation=GuardrailViolation.TRADE_RATE_EXCEEDED,
                message=f"Hourly trade limit reached: {portfolio.trades_this_hour}/{g.MAX_TRADES_PER_HOUR}",
                details={
                    "trades_this_hour": portfolio.trades_this_hour,
                    "max_trades": g.MAX_TRADES_PER_HOUR,
                },
            )

        # All checks passed
        logger.debug(
            "guardrail_check_passed",
            symbol=symbol,
            side=side,
            quantity=quantity,
            position_pct=float(position_pct),
            exposure_pct=float(exposure_pct),
        )

        return GuardrailCheckResult(
            allowed=True,
            message="Order approved by guardrails",
        )

    def check_drawdown(self, portfolio: "PortfolioState") -> GuardrailCheckResult:
        """
        Check if total drawdown exceeds limit.

        Args:
            portfolio: Current portfolio state

        Returns:
            GuardrailCheckResult
        """
        g = self.guardrails

        if portfolio.peak_value > 0:
            drawdown = (portfolio.peak_value - portfolio.total_value) / portfolio.peak_value
            if Decimal(str(drawdown)) >= g.MAX_TOTAL_DRAWDOWN_PCT:
                return GuardrailCheckResult(
                    allowed=False,
                    violation=GuardrailViolation.TOTAL_DRAWDOWN_EXCEEDED,
                    message=f"Total drawdown {drawdown:.1%} exceeds max {g.MAX_TOTAL_DRAWDOWN_PCT:.1%}",
                    details={
                        "peak_value": float(portfolio.peak_value),
                        "current_value": float(portfolio.total_value),
                        "drawdown_pct": float(drawdown),
                        "max_pct": float(g.MAX_TOTAL_DRAWDOWN_PCT),
                    },
                )

        return GuardrailCheckResult(allowed=True, message="Drawdown within limits")


# Global singleton instance
_enforcer: GuardrailEnforcer | None = None


def get_guardrail_enforcer() -> GuardrailEnforcer:
    """Get the global guardrail enforcer instance."""
    global _enforcer
    if _enforcer is None:
        _enforcer = GuardrailEnforcer()
    return _enforcer
