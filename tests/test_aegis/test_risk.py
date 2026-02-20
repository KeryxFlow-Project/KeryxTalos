"""Tests for risk manager."""

import pytest

from keryxflow.aegis.risk import OrderRequest, RejectionReason, RiskManager
from keryxflow.core.models import RiskProfile


@pytest.fixture
def risk_manager():
    """Create a risk manager for testing."""
    return RiskManager(
        risk_profile=RiskProfile.BALANCED,
        initial_balance=10000.0,
    )


class TestOrderApproval:
    """Tests for order approval."""

    def test_approve_valid_order(self, risk_manager):
        """Test approval of valid order."""
        order = OrderRequest(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.01,
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
        )

        result = risk_manager.approve_order(order)

        assert result.approved is True

    def test_reject_no_stop_loss(self, risk_manager):
        """Test rejection when no stop loss."""
        order = OrderRequest(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.01,
            entry_price=50000.0,
            stop_loss=None,
        )

        result = risk_manager.approve_order(order)

        assert result.approved is False
        assert result.reason == RejectionReason.INVALID_ORDER
        assert result.suggested_stop_loss is not None

    def test_reject_risk_too_high(self, risk_manager):
        """Test rejection when quantity too large.

        With the guardrails integration (Phase 1 - Issue #9 fix), large positions
        are now rejected by the immutable guardrails first. The guardrails enforce
        a max 10% position size, which catches this 250% position before the
        RiskManager's own risk calculation runs.

        Note: Guardrail rejections don't include suggested_quantity since they
        represent hard limits, not adjustable thresholds.
        """
        # Position value = 0.5 * 50000 = 25000 = 250% of portfolio
        # This exceeds the 10% max position guardrail
        order = OrderRequest(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.5,  # Way too large (250% of portfolio)
            entry_price=50000.0,
            stop_loss=49000.0,
        )

        result = risk_manager.approve_order(order)

        assert result.approved is False
        assert result.reason == RejectionReason.RISK_TOO_HIGH
        # Guardrail rejections don't include suggestions (hard limits)
        assert "Safety limit" in result.simple_message or "Position size" in result.simple_message

    def test_reject_poor_risk_reward(self, risk_manager):
        """Test rejection for poor risk/reward."""
        # Balanced profile: min R:R = 1.5
        order = OrderRequest(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.01,
            entry_price=50000.0,
            stop_loss=48000.0,  # Risk $2000
            take_profit=51000.0,  # Reward $1000 (0.5:1)
        )

        result = risk_manager.approve_order(order)

        assert result.approved is False
        assert result.reason == RejectionReason.POOR_RISK_REWARD

    def test_reject_max_positions(self, risk_manager):
        """Test rejection when max positions reached."""
        risk_manager.set_open_positions(3)  # Balanced max is 3

        order = OrderRequest(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.01,
            entry_price=50000.0,
            stop_loss=49000.0,
        )

        result = risk_manager.approve_order(order)

        assert result.approved is False
        assert result.reason == RejectionReason.MAX_POSITIONS_REACHED

    def test_reject_symbol_not_allowed(self, risk_manager):
        """Test rejection for non-allowed symbol."""
        order = OrderRequest(
            symbol="SHIB/USDT",  # Not in allowed list (not in settings.toml)
            side="buy",
            quantity=100.0,
            entry_price=0.1,
            stop_loss=0.09,
        )

        result = risk_manager.approve_order(order)

        assert result.approved is False
        assert result.reason == RejectionReason.SYMBOL_NOT_ALLOWED

    def test_reject_insufficient_balance(self, risk_manager):
        """Test rejection for insufficient balance."""
        risk_manager.update_balance(100.0)  # Only $100

        order = OrderRequest(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.01,  # Worth $500 at $50k
            entry_price=50000.0,
            stop_loss=49000.0,
        )

        result = risk_manager.approve_order(order)

        # With small balance, either RISK_TOO_HIGH or INSUFFICIENT_BALANCE
        assert result.approved is False
        assert result.reason in (
            RejectionReason.INSUFFICIENT_BALANCE,
            RejectionReason.RISK_TOO_HIGH,
        )


class TestCircuitBreaker:
    """Tests for circuit breaker integration."""

    def test_reject_when_circuit_breaker_active(self, risk_manager):
        """Test rejection when circuit breaker is active."""
        risk_manager.activate_circuit_breaker("Test")

        order = OrderRequest(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.01,
            entry_price=50000.0,
            stop_loss=49000.0,
        )

        result = risk_manager.approve_order(order)

        assert result.approved is False
        assert result.reason == RejectionReason.CIRCUIT_BREAKER_ACTIVE

    def test_reject_daily_drawdown_exceeded(self, risk_manager):
        """Test rejection when daily drawdown exceeded."""
        # Balanced profile: 5% max daily drawdown
        # Set today's date to prevent reset
        from datetime import UTC, datetime

        risk_manager._last_reset_date = datetime.now(UTC).strftime("%Y-%m-%d")
        risk_manager._daily_starting_balance = 10000.0
        risk_manager._daily_pnl = -600.0  # 6% loss

        order = OrderRequest(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.01,
            entry_price=50000.0,
            stop_loss=49000.0,
        )

        result = risk_manager.approve_order(order)

        assert result.approved is False
        assert result.reason == RejectionReason.DAILY_DRAWDOWN_EXCEEDED


class TestPositionSizeCalculation:
    """Tests for safe position size calculation."""

    def test_calculate_safe_size(self, risk_manager):
        """Test safe position size calculation."""
        size = risk_manager.calculate_safe_position_size(
            symbol="BTC/USDT",
            entry_price=50000.0,
            stop_loss=49000.0,
            balance=10000.0,
        )

        # 1% risk = $100, stop = $1000
        # Size = 0.1
        assert size == pytest.approx(0.1, rel=0.01)


class TestStatus:
    """Tests for status reporting."""

    def test_get_status(self, risk_manager):
        """Test status dictionary."""
        risk_manager.update_balance(9500.0)
        risk_manager.set_open_positions(2)

        status = risk_manager.get_status()

        assert status["profile"] == "Balanced"
        assert status["balance"] == 9500.0
        assert status["open_positions"] == 2
        assert status["max_positions"] == 3

    def test_format_status_simple(self, risk_manager):
        """Test simple status formatting."""
        status = risk_manager.format_status_simple()

        assert "Aegis" in status
        assert "ACTIVE" in status or "PAUSED" in status
