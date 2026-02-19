"""Risk manager for order approval and validation."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from keryxflow.aegis.guardrails import (
    GuardrailViolation,
    get_guardrail_enforcer,
)
from keryxflow.aegis.portfolio import PortfolioState, PositionState, create_portfolio_state
from keryxflow.aegis.profiles import get_risk_profile
from keryxflow.aegis.quant import get_quant_engine
from keryxflow.config import get_settings
from keryxflow.core.logging import get_logger
from keryxflow.core.models import RiskProfile

logger = get_logger(__name__)


class RejectionReason(str, Enum):
    """Reasons for order rejection."""

    INSUFFICIENT_BALANCE = "insufficient_balance"
    MAX_POSITIONS_REACHED = "max_positions_reached"
    DAILY_DRAWDOWN_EXCEEDED = "daily_drawdown_exceeded"
    RISK_TOO_HIGH = "risk_too_high"
    POOR_RISK_REWARD = "poor_risk_reward"
    CIRCUIT_BREAKER_ACTIVE = "circuit_breaker_active"
    INVALID_ORDER = "invalid_order"
    SYMBOL_NOT_ALLOWED = "symbol_not_allowed"
    GUARDRAIL_VIOLATION = "guardrail_violation"


# Mapping from GuardrailViolation to RejectionReason
_GUARDRAIL_TO_REJECTION: dict[GuardrailViolation, RejectionReason] = {
    GuardrailViolation.POSITION_TOO_LARGE: RejectionReason.RISK_TOO_HIGH,
    GuardrailViolation.TOTAL_EXPOSURE_EXCEEDED: RejectionReason.RISK_TOO_HIGH,
    GuardrailViolation.INSUFFICIENT_RESERVE: RejectionReason.INSUFFICIENT_BALANCE,
    GuardrailViolation.DAILY_LOSS_EXCEEDED: RejectionReason.DAILY_DRAWDOWN_EXCEEDED,
    GuardrailViolation.WEEKLY_LOSS_EXCEEDED: RejectionReason.DAILY_DRAWDOWN_EXCEEDED,
    GuardrailViolation.TOTAL_DRAWDOWN_EXCEEDED: RejectionReason.DAILY_DRAWDOWN_EXCEEDED,
    GuardrailViolation.CONSECUTIVE_LOSSES_HALT: RejectionReason.CIRCUIT_BREAKER_ACTIVE,
    GuardrailViolation.TRADE_RATE_EXCEEDED: RejectionReason.CIRCUIT_BREAKER_ACTIVE,
    GuardrailViolation.SYMBOL_NOT_ALLOWED: RejectionReason.SYMBOL_NOT_ALLOWED,
    GuardrailViolation.INVALID_ORDER_TYPE: RejectionReason.INVALID_ORDER,
}


@dataclass
class OrderRequest:
    """Request to place an order."""

    symbol: str
    side: str  # "buy" or "sell"
    quantity: float
    entry_price: float
    stop_loss: float | None = None
    take_profit: float | None = None


@dataclass
class ApprovalResult:
    """Result of order approval check."""

    approved: bool
    reason: RejectionReason | None = None

    # Human-readable explanations
    simple_message: str = ""
    technical_message: str = ""

    # Suggested adjustments
    suggested_quantity: float | None = None
    suggested_stop_loss: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "approved": self.approved,
            "reason": self.reason.value if self.reason else None,
            "simple_message": self.simple_message,
            "technical_message": self.technical_message,
            "suggested_quantity": self.suggested_quantity,
            "suggested_stop_loss": self.suggested_stop_loss,
        }


class RiskManager:
    """
    Risk manager that approves or rejects orders.

    Enforces two layers of protection:
    1. Immutable guardrails (GuardrailEnforcer) - cannot be bypassed
    2. Configurable risk profile limits (RiskManager) - can be adjusted

    The guardrails check is ALWAYS performed first, ensuring that
    no order can ever violate the hardcoded safety limits.
    """

    def __init__(
        self,
        risk_profile: RiskProfile = RiskProfile.CONSERVATIVE,
        initial_balance: float = 10000.0,
    ):
        """
        Initialize the risk manager.

        Args:
            risk_profile: Risk profile to use
            initial_balance: Starting balance for drawdown calculation
        """
        self.settings = get_settings()
        self.profile = get_risk_profile(risk_profile)
        self.quant = get_quant_engine(self.profile.risk_per_trade)

        # Immutable guardrails (Phase 1 - Issue #9 fix)
        self._guardrail_enforcer = get_guardrail_enforcer()
        self._portfolio_state = create_portfolio_state(initial_balance)

        # State tracking
        self._initial_balance = initial_balance
        self._current_balance = initial_balance
        self._daily_starting_balance = initial_balance
        self._daily_pnl = 0.0
        self._open_positions = 0
        self._circuit_breaker_active = False
        self._last_reset_date: str | None = None

    def update_balance(self, balance: float) -> None:
        """Update current balance."""
        self._current_balance = balance

    def update_daily_pnl(self, pnl: float) -> None:
        """Update daily PnL."""
        self._daily_pnl = pnl
        self._check_daily_reset()

    def set_open_positions(self, count: int) -> None:
        """Set the number of open positions."""
        self._open_positions = count

    # =========================================================================
    # Portfolio State Management (for guardrails - Issue #9 fix)
    # =========================================================================

    @property
    def portfolio_state(self) -> PortfolioState:
        """Get the current portfolio state for guardrail checks."""
        return self._portfolio_state

    def add_position_to_portfolio(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> None:
        """
        Add a position to the portfolio state for aggregate risk tracking.

        This should be called after an order is filled.

        Args:
            symbol: Trading pair
            side: Position side ("long" or "short")
            quantity: Position quantity
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
        """
        position = PositionState(
            symbol=symbol,
            side=side,
            quantity=Decimal(str(quantity)),
            entry_price=Decimal(str(entry_price)),
            current_price=Decimal(str(entry_price)),
            stop_loss=Decimal(str(stop_loss)) if stop_loss else None,
            take_profit=Decimal(str(take_profit)) if take_profit else None,
        )
        self._portfolio_state.add_position(position)
        self._open_positions = self._portfolio_state.position_count

    def close_position_in_portfolio(self, symbol: str, exit_price: float) -> float | None:
        """
        Close a position in the portfolio state.

        This should be called when a position is closed.

        Args:
            symbol: Symbol to close
            exit_price: Exit price

        Returns:
            Realized P&L or None if position not found
        """
        result = self._portfolio_state.close_position(symbol, exit_price)
        self._open_positions = self._portfolio_state.position_count
        if result is not None:
            self._daily_pnl += float(result)
        return float(result) if result else None

    def update_position_prices(self, prices: dict[str, float]) -> None:
        """
        Update current prices for all positions.

        Args:
            prices: Dict mapping symbol to current price
        """
        self._portfolio_state.update_prices(prices)

    def sync_portfolio_balance(self, balance: float) -> None:
        """
        Sync portfolio state with actual balance.

        Args:
            balance: Current account balance
        """
        self._current_balance = balance
        # Update portfolio total value if no positions
        if self._portfolio_state.position_count == 0:
            self._portfolio_state.total_value = Decimal(str(balance))
            self._portfolio_state.cash_available = Decimal(str(balance))

    def _check_daily_reset(self) -> None:
        """Check if we need to reset daily tracking."""
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        if self._last_reset_date != today:
            self._daily_starting_balance = self._current_balance
            self._daily_pnl = 0.0
            self._last_reset_date = today
            # Also reset portfolio state daily tracking
            self._portfolio_state.reset_daily()
            logger.info("daily_risk_reset", date=today, balance=self._current_balance)

    @property
    def daily_drawdown(self) -> float:
        """Calculate current daily drawdown percentage."""
        if self._daily_starting_balance <= 0:
            return 0.0
        return -self._daily_pnl / self._daily_starting_balance

    @property
    def is_circuit_breaker_active(self) -> bool:
        """Check if circuit breaker is active."""
        return self._circuit_breaker_active

    def activate_circuit_breaker(self, reason: str) -> None:
        """Activate circuit breaker."""
        self._circuit_breaker_active = True
        logger.warning("circuit_breaker_activated", reason=reason)

    def deactivate_circuit_breaker(self) -> None:
        """Deactivate circuit breaker (manual reset)."""
        self._circuit_breaker_active = False
        logger.info("circuit_breaker_deactivated")

    def approve_order(
        self,
        order: OrderRequest,
        current_balance: float | None = None,
    ) -> ApprovalResult:
        """
        Evaluate an order request and approve or reject.

        Two-layer validation:
        1. Immutable guardrails (cannot be bypassed) - checks aggregate risk
        2. Configurable risk profile limits

        Args:
            order: The order request to evaluate
            current_balance: Current account balance (optional, uses tracked)

        Returns:
            ApprovalResult with approval status and details
        """
        self._check_daily_reset()

        balance = current_balance or self._current_balance

        # =================================================================
        # LAYER 1: Immutable Guardrails (Issue #9 fix - aggregate risk)
        # These checks cannot be bypassed under any circumstances
        # =================================================================
        guardrail_result = self._guardrail_enforcer.validate_order(
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            entry_price=order.entry_price,
            stop_loss=order.stop_loss,
            portfolio=self._portfolio_state,
        )

        if not guardrail_result.allowed:
            violation = guardrail_result.violation
            rejection_reason = _GUARDRAIL_TO_REJECTION.get(
                violation, RejectionReason.GUARDRAIL_VIOLATION
            )

            logger.warning(
                "order_rejected_by_guardrail",
                symbol=order.symbol,
                violation=violation.value if violation else "unknown",
                message=guardrail_result.message,
            )

            return ApprovalResult(
                approved=False,
                reason=rejection_reason,
                simple_message=f"Safety limit reached: {guardrail_result.message}",
                technical_message=f"Guardrail violation: {guardrail_result.message}",
            )

        # =================================================================
        # LAYER 2: Configurable Risk Profile Limits
        # These can be adjusted via risk profiles
        # =================================================================

        # Check circuit breaker
        if self._circuit_breaker_active:
            return ApprovalResult(
                approved=False,
                reason=RejectionReason.CIRCUIT_BREAKER_ACTIVE,
                simple_message="Trading is paused for safety. Daily loss limit was reached.",
                technical_message="Circuit breaker active. Manual reset required.",
            )

        # Check daily drawdown
        if self.daily_drawdown >= self.profile.max_daily_drawdown:
            self.activate_circuit_breaker("Daily drawdown limit reached")
            return ApprovalResult(
                approved=False,
                reason=RejectionReason.DAILY_DRAWDOWN_EXCEEDED,
                simple_message=f"Daily loss limit ({self.profile.max_daily_drawdown:.0%}) reached. Trading paused.",
                technical_message=f"Daily drawdown {self.daily_drawdown:.2%} >= limit {self.profile.max_daily_drawdown:.2%}",
            )

        # Check total drawdown from peak
        drawdown_result = self._guardrail_enforcer.check_drawdown(self._portfolio_state)
        if not drawdown_result.allowed:
            self.activate_circuit_breaker("Total drawdown limit reached")
            return ApprovalResult(
                approved=False,
                reason=RejectionReason.DAILY_DRAWDOWN_EXCEEDED,
                simple_message=f"Total drawdown limit reached. {drawdown_result.message}",
                technical_message=f"Guardrail: {drawdown_result.message}",
            )

        # Check max positions
        if self._open_positions >= self.profile.max_open_positions:
            return ApprovalResult(
                approved=False,
                reason=RejectionReason.MAX_POSITIONS_REACHED,
                simple_message=f"Maximum trades ({self.profile.max_open_positions}) already open. Close one first.",
                technical_message=f"Open positions {self._open_positions} >= max {self.profile.max_open_positions}",
            )

        # Check symbol is allowed
        allowed_symbols = self.settings.system.symbols
        if order.symbol not in allowed_symbols:
            return ApprovalResult(
                approved=False,
                reason=RejectionReason.SYMBOL_NOT_ALLOWED,
                simple_message=f"{order.symbol} is not in your allowed symbols list.",
                technical_message=f"Symbol {order.symbol} not in {allowed_symbols}",
            )

        # Validate order has stop loss
        if order.stop_loss is None:
            # Calculate suggested stop loss
            suggested_stop = self.quant.fixed_percentage_stop(
                order.entry_price,
                order.side,
                percentage=0.02,  # Default 2%
            )
            return ApprovalResult(
                approved=False,
                reason=RejectionReason.INVALID_ORDER,
                simple_message="Every trade needs a stop-loss to protect your money.",
                technical_message="Stop loss is required for position sizing",
                suggested_stop_loss=suggested_stop,
            )

        # Calculate position size
        try:
            size_result = self.quant.position_size(
                balance=balance,
                entry_price=order.entry_price,
                stop_loss=order.stop_loss,
                risk_per_trade=self.profile.risk_per_trade,
            )
        except ValueError as e:
            return ApprovalResult(
                approved=False,
                reason=RejectionReason.INVALID_ORDER,
                simple_message=str(e),
                technical_message=f"Position sizing error: {e}",
            )

        # Check if requested quantity exceeds safe size
        if order.quantity > size_result.quantity * 1.1:  # 10% tolerance
            return ApprovalResult(
                approved=False,
                reason=RejectionReason.RISK_TOO_HIGH,
                simple_message=f"Trade size too large. Reduce to {size_result.quantity:.6f} for safe risk.",
                technical_message=f"Requested {order.quantity} > max safe {size_result.quantity:.6f}",
                suggested_quantity=size_result.quantity,
            )

        # Check risk/reward if take profit provided
        if order.take_profit is not None:
            try:
                rr_result = self.quant.risk_reward_ratio(
                    entry_price=order.entry_price,
                    stop_loss=order.stop_loss,
                    take_profit=order.take_profit,
                    quantity=order.quantity,
                )

                if rr_result.ratio < self.profile.min_risk_reward:
                    return ApprovalResult(
                        approved=False,
                        reason=RejectionReason.POOR_RISK_REWARD,
                        simple_message=f"Risk/reward {rr_result.ratio:.1f}:1 is below minimum {self.profile.min_risk_reward:.1f}:1",
                        technical_message=f"R:R ratio {rr_result.ratio:.2f} < min {self.profile.min_risk_reward}",
                    )
            except ValueError as e:
                logger.warning("risk_reward_calculation_failed", error=str(e))

        # Check sufficient balance
        position_value = order.quantity * order.entry_price
        if position_value > balance:
            return ApprovalResult(
                approved=False,
                reason=RejectionReason.INSUFFICIENT_BALANCE,
                simple_message=f"Not enough balance. Need ${position_value:,.2f}, have ${balance:,.2f}",
                technical_message=f"Position value ${position_value:,.2f} > balance ${balance:,.2f}",
            )

        # Order approved
        logger.info(
            "order_approved",
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            risk_amount=size_result.risk_amount,
        )

        return ApprovalResult(
            approved=True,
            simple_message=f"Trade approved. Risking ${size_result.risk_amount:,.2f} ({self.profile.risk_per_trade:.1%})",
            technical_message=f"Order approved: {order.quantity} {order.symbol} @ {order.entry_price}, SL: {order.stop_loss}",
        )

    def calculate_safe_position_size(
        self,
        symbol: str,  # noqa: ARG002
        entry_price: float,
        stop_loss: float,
        balance: float | None = None,
    ) -> float:
        """
        Calculate safe position size for a trade.

        Args:
            symbol: Trading pair
            entry_price: Entry price
            stop_loss: Stop loss price
            balance: Account balance (optional)

        Returns:
            Safe position quantity
        """
        bal = balance or self._current_balance

        result = self.quant.position_size(
            balance=bal,
            entry_price=entry_price,
            stop_loss=stop_loss,
            risk_per_trade=self.profile.risk_per_trade,
        )

        return result.quantity

    def get_status(self) -> dict[str, Any]:
        """Get current risk manager status."""
        portfolio = self._portfolio_state
        return {
            "profile": self.profile.name,
            "balance": self._current_balance,
            "daily_pnl": self._daily_pnl,
            "daily_drawdown": self.daily_drawdown,
            "max_daily_drawdown": self.profile.max_daily_drawdown,
            "open_positions": self._open_positions,
            "max_positions": self.profile.max_open_positions,
            "circuit_breaker_active": self._circuit_breaker_active,
            "risk_per_trade": self.profile.risk_per_trade,
            # Portfolio state (Issue #9 - aggregate risk)
            "aggregate_risk_pct": float(portfolio.risk_at_stop_pct),
            "total_exposure_pct": float(portfolio.exposure_pct),
            "cash_reserve_pct": float(portfolio.cash_reserve_pct),
            "consecutive_losses": portfolio.consecutive_losses,
        }

    def format_status_simple(self) -> str:
        """Format status for simple display."""
        status = self.get_status()
        circuit = "🔴 PAUSED" if status["circuit_breaker_active"] else "🟢 ACTIVE"

        return (
            f"Aegis: {circuit}\n"
            f"Daily PnL: ${status['daily_pnl']:+,.2f} ({-status['daily_drawdown']:+.1%})\n"
            f"Positions: {status['open_positions']}/{status['max_positions']}"
        )


# Global instance
_risk_manager: RiskManager | None = None


def get_risk_manager(
    risk_profile: RiskProfile = RiskProfile.CONSERVATIVE,
    initial_balance: float = 10000.0,
) -> RiskManager:
    """Get the global risk manager instance."""
    global _risk_manager
    if _risk_manager is None:
        _risk_manager = RiskManager(
            risk_profile=risk_profile,
            initial_balance=initial_balance,
        )
    return _risk_manager
