"""Risk manager for order approval and validation."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

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

    Enforces:
    - Position size limits
    - Maximum open positions
    - Daily drawdown limits
    - Minimum risk/reward ratio
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

    def _check_daily_reset(self) -> None:
        """Check if we need to reset daily tracking."""
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        if self._last_reset_date != today:
            self._daily_starting_balance = self._current_balance
            self._daily_pnl = 0.0
            self._last_reset_date = today
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

        Args:
            order: The order request to evaluate
            current_balance: Current account balance (optional, uses tracked)

        Returns:
            ApprovalResult with approval status and details
        """
        self._check_daily_reset()

        balance = current_balance or self._current_balance

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
            except ValueError:
                pass  # Skip R:R check if calculation fails

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
