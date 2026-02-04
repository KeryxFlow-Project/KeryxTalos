"""Tests for immutable trading guardrails and portfolio state."""

from decimal import Decimal

import pytest

from keryxflow.aegis.guardrails import (
    GuardrailEnforcer,
    GuardrailViolation,
    TradingGuardrails,
    get_guardrail_enforcer,
    get_guardrails,
)
from keryxflow.aegis.portfolio import (
    PositionState,
    create_portfolio_state,
)

# =============================================================================
# TradingGuardrails Tests
# =============================================================================


class TestTradingGuardrails:
    """Tests for immutable guardrails."""

    def test_guardrails_have_default_values(self):
        """Guardrails should have sensible default values."""
        g = TradingGuardrails()

        assert Decimal("0.10") == g.MAX_POSITION_SIZE_PCT
        assert Decimal("0.50") == g.MAX_TOTAL_EXPOSURE_PCT
        assert Decimal("0.20") == g.MIN_CASH_RESERVE_PCT
        assert Decimal("0.02") == g.MAX_LOSS_PER_TRADE_PCT
        assert Decimal("0.05") == g.MAX_DAILY_LOSS_PCT
        assert Decimal("0.10") == g.MAX_WEEKLY_LOSS_PCT
        assert g.CONSECUTIVE_LOSSES_HALT == 5
        assert g.MAX_TRADES_PER_DAY == 50
        assert g.MAX_TRADES_PER_HOUR == 10

    def test_guardrails_are_immutable(self):
        """Guardrails should be immutable (frozen dataclass)."""
        g = TradingGuardrails()

        with pytest.raises(AttributeError):
            g.MAX_POSITION_SIZE_PCT = Decimal("0.50")

        with pytest.raises(AttributeError):
            g.MAX_DAILY_LOSS_PCT = Decimal("0.20")

        with pytest.raises(AttributeError):
            g.CONSECUTIVE_LOSSES_HALT = 100

    def test_get_guardrails_returns_singleton(self):
        """get_guardrails should return the same instance."""
        g1 = get_guardrails()
        g2 = get_guardrails()
        assert g1 is g2

    def test_allowed_symbols_default(self):
        """Default allowed symbols should be set."""
        g = TradingGuardrails()
        assert "BTC/USDT" in g.ALLOWED_SYMBOLS
        assert "ETH/USDT" in g.ALLOWED_SYMBOLS


# =============================================================================
# PositionState Tests
# =============================================================================


class TestPositionState:
    """Tests for position state tracking."""

    def test_position_value_calculation(self):
        """Position value should be quantity * current price."""
        pos = PositionState(
            symbol="BTC/USDT",
            side="long",
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000"),
            current_price=Decimal("51000"),
        )

        assert pos.position_value == Decimal("5100")
        assert pos.entry_value == Decimal("5000")

    def test_unrealized_pnl_long(self):
        """Unrealized P&L for long position."""
        pos = PositionState(
            symbol="BTC/USDT",
            side="long",
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000"),
            current_price=Decimal("51000"),
        )

        # (51000 - 50000) * 0.1 = 100
        assert pos.unrealized_pnl == Decimal("100")

    def test_unrealized_pnl_short(self):
        """Unrealized P&L for short position."""
        pos = PositionState(
            symbol="BTC/USDT",
            side="short",
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000"),
            current_price=Decimal("49000"),
        )

        # (50000 - 49000) * 0.1 = 100
        assert pos.unrealized_pnl == Decimal("100")

    def test_risk_to_stop_with_stop_loss(self):
        """Risk to stop should be calculated from stop loss."""
        pos = PositionState(
            symbol="BTC/USDT",
            side="long",
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000"),
            current_price=Decimal("51000"),
            stop_loss=Decimal("49000"),
        )

        # (50000 - 49000) * 0.1 = 100
        assert pos.risk_to_stop == Decimal("100")

    def test_risk_to_stop_without_stop_loss(self):
        """Without stop loss, full position value is at risk."""
        pos = PositionState(
            symbol="BTC/USDT",
            side="long",
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000"),
            current_price=Decimal("51000"),
            stop_loss=None,
        )

        assert pos.risk_to_stop == Decimal("5100")  # Full position value

    def test_risk_reward_ratio(self):
        """Risk/reward ratio calculation."""
        pos = PositionState(
            symbol="BTC/USDT",
            side="long",
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000"),
            current_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("52000"),
        )

        # Risk: (50000 - 49000) * 0.1 = 100
        # Reward: (52000 - 50000) * 0.1 = 200
        # Ratio: 200 / 100 = 2.0
        assert pos.risk_reward_ratio == Decimal("2")


# =============================================================================
# PortfolioState Tests
# =============================================================================


class TestPortfolioState:
    """Tests for portfolio state tracking."""

    def test_create_portfolio_state(self):
        """Create portfolio with initial balance."""
        portfolio = create_portfolio_state(10000.0)

        assert portfolio.total_value == Decimal("10000")
        assert portfolio.cash_available == Decimal("10000")
        assert portfolio.total_exposure == Decimal("0")
        assert portfolio.position_count == 0

    def test_add_position(self):
        """Adding a position should update portfolio state."""
        portfolio = create_portfolio_state(10000.0)

        position = PositionState(
            symbol="BTC/USDT",
            side="long",
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000"),
            current_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
        )

        portfolio.add_position(position)

        assert portfolio.position_count == 1
        assert portfolio.cash_available == Decimal("5000")  # 10000 - 5000
        assert portfolio.total_exposure == Decimal("5000")
        assert portfolio.trades_today == 1

    def test_total_risk_at_stop(self):
        """Total risk at stop should sum all position risks."""
        portfolio = create_portfolio_state(10000.0)

        # Add two positions, each with 200 risk
        pos1 = PositionState(
            symbol="BTC/USDT",
            side="long",
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000"),
            current_price=Decimal("50000"),
            stop_loss=Decimal("48000"),  # 2000 * 0.1 = 200 risk
        )
        pos2 = PositionState(
            symbol="ETH/USDT",
            side="long",
            quantity=Decimal("1"),
            entry_price=Decimal("3000"),
            current_price=Decimal("3000"),
            stop_loss=Decimal("2800"),  # 200 * 1 = 200 risk
        )

        portfolio.add_position(pos1)
        portfolio.add_position(pos2)

        assert portfolio.total_risk_at_stop == Decimal("400")
        assert portfolio.risk_at_stop_pct == Decimal("400") / portfolio.total_value

    def test_close_position_profit(self):
        """Closing a position with profit should update P&L."""
        portfolio = create_portfolio_state(10000.0)

        position = PositionState(
            symbol="BTC/USDT",
            side="long",
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000"),
            current_price=Decimal("50000"),
        )
        portfolio.add_position(position)

        # Close at profit
        realized_pnl = portfolio.close_position("BTC/USDT", 51000)

        assert realized_pnl == Decimal("100")
        assert portfolio.daily_pnl == Decimal("100")
        assert portfolio.consecutive_losses == 0
        assert portfolio.position_count == 0

    def test_close_position_loss(self):
        """Closing a position with loss should increment consecutive losses."""
        portfolio = create_portfolio_state(10000.0)

        position = PositionState(
            symbol="BTC/USDT",
            side="long",
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000"),
            current_price=Decimal("50000"),
        )
        portfolio.add_position(position)

        # Close at loss
        realized_pnl = portfolio.close_position("BTC/USDT", 49000)

        assert realized_pnl == Decimal("-100")
        assert portfolio.daily_pnl == Decimal("-100")
        assert portfolio.consecutive_losses == 1

    def test_drawdown_calculation(self):
        """Drawdown should be calculated from peak value."""
        portfolio = create_portfolio_state(10000.0)

        # Simulate loss
        portfolio.total_value = Decimal("9000")

        assert portfolio.drawdown_pct == Decimal("0.1")  # 10% drawdown


# =============================================================================
# GuardrailEnforcer Tests
# =============================================================================


class TestGuardrailEnforcer:
    """Tests for guardrail enforcement."""

    @pytest.fixture
    def enforcer(self):
        """Create enforcer with default guardrails."""
        return GuardrailEnforcer()

    @pytest.fixture
    def portfolio(self):
        """Create a standard portfolio for testing."""
        return create_portfolio_state(10000.0)

    def test_valid_order_approved(self, enforcer, portfolio):
        """A valid order should be approved."""
        result = enforcer.validate_order(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.01,
            entry_price=50000,
            stop_loss=49000,
            portfolio=portfolio,
        )

        assert result.allowed
        assert result.violation is None

    def test_symbol_not_allowed(self, enforcer, portfolio):
        """Order for non-allowed symbol should be rejected."""
        result = enforcer.validate_order(
            symbol="SHIB/USDT",  # Not in allowed list (not in settings.toml)
            side="buy",
            quantity=0.01,
            entry_price=50000,
            stop_loss=49000,
            portfolio=portfolio,
        )

        assert not result.allowed
        assert result.violation == GuardrailViolation.SYMBOL_NOT_ALLOWED

    def test_position_too_large(self, enforcer, portfolio):
        """Position exceeding 10% of portfolio should be rejected."""
        # 10000 * 10% = 1000 max position value
        # 0.03 * 50000 = 1500 > 1000
        result = enforcer.validate_order(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.03,
            entry_price=50000,
            stop_loss=49000,
            portfolio=portfolio,
        )

        assert not result.allowed
        assert result.violation == GuardrailViolation.POSITION_TOO_LARGE

    def test_total_exposure_exceeded(self, enforcer, portfolio):
        """Total exposure exceeding 50% should be rejected."""
        # Add positions to bring exposure to exactly 50% (the limit)
        # Each position is 0.02 BTC @ 50000 = 1000 = 10%
        for _ in range(5):
            pos = PositionState(
                symbol="BTC/USDT",
                side="long",
                quantity=Decimal("0.02"),  # 1000 each = 10%
                entry_price=Decimal("50000"),
                current_price=Decimal("50000"),
                stop_loss=Decimal("49500"),
            )
            portfolio.add_position(pos)

        # Now at 50% exposure (5000/10000), try to add 6th position
        # Any additional position will exceed the 50% limit
        result = enforcer.validate_order(
            symbol="ETH/USDT",
            side="buy",
            quantity=0.33,  # 990 ~ 10%, would bring total to ~60%
            entry_price=3000,
            stop_loss=2900,
            portfolio=portfolio,
        )

        assert not result.allowed
        assert result.violation == GuardrailViolation.TOTAL_EXPOSURE_EXCEEDED

    def test_insufficient_reserve(self, enforcer, portfolio):
        """Order that would reduce cash below 20% should be rejected."""
        # Try to use 85% of cash (would leave only 15% reserve)
        result = enforcer.validate_order(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.17,  # 0.17 * 50000 = 8500 = 85%
            entry_price=50000,
            stop_loss=49000,
            portfolio=portfolio,
        )

        assert not result.allowed
        # Could be position too large or insufficient reserve depending on order of checks
        assert result.violation in [
            GuardrailViolation.POSITION_TOO_LARGE,
            GuardrailViolation.INSUFFICIENT_RESERVE,
        ]

    def test_trade_risk_exceeded(self, enforcer, portfolio):
        """Trade with risk > 2% should be rejected."""
        # Risk = (50000 - 40000) * 0.03 = 300 = 3% of 10000
        result = enforcer.validate_order(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.03,
            entry_price=50000,
            stop_loss=40000,  # Very wide stop = high risk
            portfolio=portfolio,
        )

        assert not result.allowed
        # Could be position too large or daily loss exceeded
        assert result.violation in [
            GuardrailViolation.POSITION_TOO_LARGE,
            GuardrailViolation.DAILY_LOSS_EXCEEDED,
        ]

    def test_consecutive_losses_halt(self, enforcer, portfolio):
        """Trading should halt after 5 consecutive losses."""
        portfolio.consecutive_losses = 5

        result = enforcer.validate_order(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.01,
            entry_price=50000,
            stop_loss=49000,
            portfolio=portfolio,
        )

        assert not result.allowed
        assert result.violation == GuardrailViolation.CONSECUTIVE_LOSSES_HALT

    def test_daily_trade_limit(self, enforcer, portfolio):
        """Trading should halt after 50 trades per day."""
        portfolio.trades_today = 50

        result = enforcer.validate_order(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.01,
            entry_price=50000,
            stop_loss=49000,
            portfolio=portfolio,
        )

        assert not result.allowed
        assert result.violation == GuardrailViolation.TRADE_RATE_EXCEEDED

    def test_hourly_trade_limit(self, enforcer, portfolio):
        """Trading should halt after 10 trades per hour."""
        portfolio.trades_this_hour = 10

        result = enforcer.validate_order(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.01,
            entry_price=50000,
            stop_loss=49000,
            portfolio=portfolio,
        )

        assert not result.allowed
        assert result.violation == GuardrailViolation.TRADE_RATE_EXCEEDED

    def test_daily_loss_limit_reached(self, enforcer, portfolio):
        """Trading should halt when daily loss exceeds 5%."""
        portfolio.daily_pnl = Decimal("-500")  # 5% of 10000

        result = enforcer.validate_order(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.01,
            entry_price=50000,
            stop_loss=49000,
            portfolio=portfolio,
        )

        assert not result.allowed
        assert result.violation == GuardrailViolation.DAILY_LOSS_EXCEEDED


# =============================================================================
# Issue #9 Scenario Tests - Aggregate Risk
# =============================================================================


class TestIssue9AggregateRisk:
    """
    Tests for Issue #9: Position sizing allows excessive drawdown.

    The bug: 3 positions at 2% risk each = 6% aggregate risk, but system
    allowed all three because it only checked individual trade risk.

    The fix: Check aggregate risk (total_risk_at_stop) against daily limit.
    """

    @pytest.fixture
    def enforcer(self):
        """Create enforcer with default guardrails."""
        return GuardrailEnforcer()

    @pytest.fixture
    def portfolio(self):
        """Create a standard portfolio for testing."""
        return create_portfolio_state(10000.0)

    def test_issue_9_scenario_single_position_allowed(self, enforcer, portfolio):
        """Single position with 2% risk should be allowed."""
        # 2% risk = 200 on 10000
        # Position: 0.02 BTC @ 50000 = 1000 value (10% - at limit)
        # Stop at 40000 = 10000 risk per unit * 0.02 = 200 risk (2%)
        result = enforcer.validate_order(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.02,
            entry_price=50000,
            stop_loss=40000,
            portfolio=portfolio,
        )

        assert result.allowed

    def test_issue_9_scenario_second_position_allowed(self, enforcer, portfolio):
        """Second position bringing total to 4% should be allowed."""
        # Add first position with 2% risk
        # Position: 0.02 BTC @ 50000 = 1000 value (10%)
        # Stop at 40000 = 200 risk (2%)
        pos1 = PositionState(
            symbol="BTC/USDT",
            side="long",
            quantity=Decimal("0.02"),
            entry_price=Decimal("50000"),
            current_price=Decimal("50000"),
            stop_loss=Decimal("40000"),  # 200 risk = 2%
        )
        portfolio.add_position(pos1)

        # Second position also 2% risk = 4% total
        # Position: 0.33 ETH @ 3000 = 990 value (~10%)
        # Stop at 2400 = 600 risk per unit * 0.33 = 198 risk (~2%)
        result = enforcer.validate_order(
            symbol="ETH/USDT",
            side="buy",
            quantity=0.33,
            entry_price=3000,
            stop_loss=2400,  # 198 risk = 2%
            portfolio=portfolio,
        )

        assert result.allowed

    def test_issue_9_scenario_third_position_rejected(self, enforcer, portfolio):
        """
        Third position that would bring aggregate risk to 6% should be REJECTED.

        This is the core Issue #9 fix.
        """
        # Add first position with 2% risk
        # Position: 0.02 BTC @ 50000 = 1000 value (10%)
        # Stop at 40000 = 200 risk (2%)
        pos1 = PositionState(
            symbol="BTC/USDT",
            side="long",
            quantity=Decimal("0.02"),
            entry_price=Decimal("50000"),
            current_price=Decimal("50000"),
            stop_loss=Decimal("40000"),  # 200 risk = 2%
        )
        portfolio.add_position(pos1)

        # Add second position with 2% risk
        # Position: 0.33 ETH @ 3000 = 990 value (~10%)
        # Stop at 2400 = 198 risk (~2%)
        pos2 = PositionState(
            symbol="ETH/USDT",
            side="long",
            quantity=Decimal("0.33"),
            entry_price=Decimal("3000"),
            current_price=Decimal("3000"),
            stop_loss=Decimal("2400"),  # 198 risk = 2%
        )
        portfolio.add_position(pos2)

        # Current aggregate risk: ~4% (398 on 10000)
        assert portfolio.total_risk_at_stop == Decimal("398")
        assert float(portfolio.risk_at_stop_pct) == pytest.approx(0.0398, rel=0.01)

        # Third position would add another 2% = ~6% total > 5% limit
        # Position: 10 SOL @ 100 = 1000 value (10%)
        # Stop at 80 = 200 risk (2%)
        result = enforcer.validate_order(
            symbol="SOL/USDT",
            side="buy",
            quantity=10,
            entry_price=100,
            stop_loss=80,  # 20 * 10 = 200 risk = 2%
            portfolio=portfolio,
        )

        # THIS IS THE KEY ASSERTION - the third position should be REJECTED
        assert not result.allowed
        assert result.violation == GuardrailViolation.DAILY_LOSS_EXCEEDED
        assert "Aggregate risk" in result.message
        assert result.details["total_risk_pct"] > 0.05  # Would exceed 5%

    def test_issue_9_smaller_third_position_allowed(self, enforcer, portfolio):
        """Third position with smaller risk keeping total under 5% should be allowed."""
        # Add first position with 2% risk
        # Position: 0.02 BTC @ 50000 = 1000 value (10%)
        # Stop at 40000 = 200 risk (2%)
        pos1 = PositionState(
            symbol="BTC/USDT",
            side="long",
            quantity=Decimal("0.02"),
            entry_price=Decimal("50000"),
            current_price=Decimal("50000"),
            stop_loss=Decimal("40000"),  # 200 risk = 2%
        )
        portfolio.add_position(pos1)

        # Add second position with 2% risk
        # Position: 0.33 ETH @ 3000 = 990 value (~10%)
        # Stop at 2400 = 198 risk (~2%)
        pos2 = PositionState(
            symbol="ETH/USDT",
            side="long",
            quantity=Decimal("0.33"),
            entry_price=Decimal("3000"),
            current_price=Decimal("3000"),
            stop_loss=Decimal("2400"),  # 198 risk = 2%
        )
        portfolio.add_position(pos2)

        # Third position with only 0.5% risk = ~4.5% total < 5% limit
        # Position: 5 SOL @ 100 = 500 value (5%)
        # Stop at 90 = 50 risk (0.5%)
        result = enforcer.validate_order(
            symbol="SOL/USDT",
            side="buy",
            quantity=5,
            entry_price=100,
            stop_loss=90,  # 10 * 5 = 50 risk = 0.5%
            portfolio=portfolio,
        )

        # This should be allowed
        assert result.allowed

    def test_aggregate_risk_tracking_accuracy(self, portfolio):
        """Verify aggregate risk is calculated correctly."""
        # Add multiple positions and verify math
        positions = [
            PositionState(
                symbol="BTC/USDT",
                side="long",
                quantity=Decimal("0.05"),
                entry_price=Decimal("50000"),
                current_price=Decimal("50000"),
                stop_loss=Decimal("49000"),  # 1000 * 0.05 = 50 risk
            ),
            PositionState(
                symbol="ETH/USDT",
                side="long",
                quantity=Decimal("0.5"),
                entry_price=Decimal("3000"),
                current_price=Decimal("3000"),
                stop_loss=Decimal("2900"),  # 100 * 0.5 = 50 risk
            ),
            PositionState(
                symbol="SOL/USDT",
                side="long",
                quantity=Decimal("10"),
                entry_price=Decimal("100"),
                current_price=Decimal("100"),
                stop_loss=Decimal("95"),  # 5 * 10 = 50 risk
            ),
        ]

        for pos in positions:
            portfolio.add_position(pos)

        # Total risk should be 50 + 50 + 50 = 150
        assert portfolio.total_risk_at_stop == Decimal("150")

        # On reduced portfolio value (after adding positions)
        expected_risk_pct = Decimal("150") / portfolio.total_value
        assert portfolio.risk_at_stop_pct == expected_risk_pct


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSingletons:
    """Tests for singleton instances."""

    def test_get_guardrail_enforcer_returns_singleton(self):
        """get_guardrail_enforcer should return same instance."""
        e1 = get_guardrail_enforcer()
        e2 = get_guardrail_enforcer()
        assert e1 is e2

    def test_enforcer_uses_default_guardrails(self):
        """Enforcer should use global guardrails by default."""
        enforcer = get_guardrail_enforcer()
        assert enforcer.guardrails is get_guardrails()
