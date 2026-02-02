"""Tests for quant engine."""

import pytest

from keryxflow.aegis.quant import QuantEngine


@pytest.fixture
def quant():
    """Create a quant engine for testing."""
    return QuantEngine(default_risk_per_trade=0.01)


class TestPositionSizing:
    """Tests for position sizing calculations."""

    def test_basic_position_size(self, quant):
        """Test basic position size calculation."""
        result = quant.position_size(
            balance=10000.0,
            entry_price=50000.0,
            stop_loss=49000.0,  # $1000 stop distance
            risk_per_trade=0.01,  # 1% risk
        )

        # Risk amount = $100 (1% of $10000)
        # Position size = $100 / $1000 = 0.1
        assert result.quantity == pytest.approx(0.1, rel=0.01)
        assert result.risk_amount == pytest.approx(100.0, rel=0.01)
        assert result.stop_distance == pytest.approx(1000.0, rel=0.01)

    def test_smaller_stop_larger_position(self, quant):
        """Tighter stop allows larger position."""
        result = quant.position_size(
            balance=10000.0,
            entry_price=50000.0,
            stop_loss=49500.0,  # $500 stop distance
            risk_per_trade=0.01,
        )

        # Risk amount = $100, stop = $500
        # Position size = 0.2
        assert result.quantity == pytest.approx(0.2, rel=0.01)

    def test_larger_stop_smaller_position(self, quant):
        """Wider stop requires smaller position."""
        result = quant.position_size(
            balance=10000.0,
            entry_price=50000.0,
            stop_loss=48000.0,  # $2000 stop distance
            risk_per_trade=0.01,
        )

        # Risk amount = $100, stop = $2000
        # Position size = 0.05
        assert result.quantity == pytest.approx(0.05, rel=0.01)

    def test_different_risk_percentages(self, quant):
        """Different risk percentages scale position."""
        result_1pct = quant.position_size(10000.0, 50000.0, 49000.0, 0.01)
        result_2pct = quant.position_size(10000.0, 50000.0, 49000.0, 0.02)

        assert result_2pct.quantity == pytest.approx(result_1pct.quantity * 2, rel=0.01)

    def test_zero_stop_distance_raises(self, quant):
        """Stop at entry price should raise error."""
        with pytest.raises(ValueError):
            quant.position_size(10000.0, 50000.0, 50000.0)


class TestKellyCriterion:
    """Tests for Kelly criterion calculation."""

    def test_kelly_positive_edge(self, quant):
        """Test Kelly with positive edge."""
        # 60% win rate, 2:1 R:R
        kelly = quant.kelly_criterion(
            win_rate=0.6,
            avg_win=200.0,
            avg_loss=100.0,
            fraction=1.0,  # Full Kelly
        )

        # Kelly = (0.6 * 2 - 0.4) / 2 = 0.4 (40%)
        assert kelly == pytest.approx(0.25, rel=0.1)  # Capped at 25%

    def test_kelly_half_fraction(self, quant):
        """Half Kelly is safer."""
        full = quant.kelly_criterion(0.6, 200.0, 100.0, fraction=1.0)
        half = quant.kelly_criterion(0.6, 200.0, 100.0, fraction=0.5)

        assert half < full

    def test_kelly_negative_edge(self, quant):
        """Negative edge returns zero."""
        kelly = quant.kelly_criterion(
            win_rate=0.3,  # Only 30% wins
            avg_win=100.0,
            avg_loss=100.0,  # 1:1 R:R
        )

        assert kelly == 0.0

    def test_kelly_invalid_win_rate(self, quant):
        """Invalid win rate raises error."""
        with pytest.raises(ValueError):
            quant.kelly_criterion(1.0, 100.0, 100.0)  # 100% win rate

        with pytest.raises(ValueError):
            quant.kelly_criterion(0.0, 100.0, 100.0)  # 0% win rate


class TestATRStop:
    """Tests for ATR-based stop loss."""

    def test_atr_stop_buy(self, quant):
        """ATR stop for long position."""
        # Simple price data with ATR ~100
        highs = [1100, 1120, 1090, 1110, 1105] * 4
        lows = [1000, 1020, 990, 1010, 1005] * 4
        closes = [1050, 1060, 1040, 1055, 1050] * 4

        stop = quant.atr_stop_loss(
            prices_high=highs,
            prices_low=lows,
            prices_close=closes,
            entry_price=1100.0,
            side="buy",
            multiplier=2.0,
            period=14,
        )

        # Stop should be below entry for buy
        assert stop < 1100.0

    def test_atr_stop_sell(self, quant):
        """ATR stop for short position."""
        highs = [1100, 1120, 1090, 1110, 1105] * 4
        lows = [1000, 1020, 990, 1010, 1005] * 4
        closes = [1050, 1060, 1040, 1055, 1050] * 4

        stop = quant.atr_stop_loss(
            prices_high=highs,
            prices_low=lows,
            prices_close=closes,
            entry_price=1100.0,
            side="sell",
            multiplier=2.0,
            period=14,
        )

        # Stop should be above entry for sell
        assert stop > 1100.0

    def test_atr_insufficient_data(self, quant):
        """Too little data raises error."""
        with pytest.raises(ValueError):
            quant.atr_stop_loss([100, 101], [99, 100], [100, 100], 100, "buy")


class TestRiskReward:
    """Tests for risk/reward calculations."""

    def test_risk_reward_favorable(self, quant):
        """Test favorable risk/reward."""
        result = quant.risk_reward_ratio(
            entry_price=100.0,
            stop_loss=95.0,  # Risk $5
            take_profit=115.0,  # Reward $15
            quantity=10.0,
        )

        # R:R = 15/5 = 3:1
        assert result.ratio == pytest.approx(3.0, rel=0.01)
        assert result.potential_loss == pytest.approx(50.0)  # $5 * 10
        assert result.potential_profit == pytest.approx(150.0)  # $15 * 10
        assert result.is_favorable is True

    def test_risk_reward_unfavorable(self, quant):
        """Test unfavorable risk/reward."""
        result = quant.risk_reward_ratio(
            entry_price=100.0,
            stop_loss=90.0,  # Risk $10
            take_profit=105.0,  # Reward $5
        )

        # R:R = 5/10 = 0.5:1
        assert result.ratio == pytest.approx(0.5, rel=0.01)
        assert result.is_favorable is False

    def test_breakeven_winrate(self, quant):
        """Test breakeven win rate calculation."""
        result = quant.risk_reward_ratio(100.0, 95.0, 110.0)

        # R:R = 2:1, breakeven = 1/(1+2) = 33%
        assert result.breakeven_winrate == pytest.approx(0.333, rel=0.01)


class TestDrawdown:
    """Tests for drawdown calculations."""

    def test_drawdown_from_peak(self, quant):
        """Test drawdown calculation."""
        equity = [100, 110, 105, 115, 100]  # Peak at 115, current at 100

        current_dd, max_dd, duration = quant.calculate_drawdown(equity)

        # Current drawdown from 115 to 100 = 13%
        assert max_dd >= current_dd
        assert current_dd == pytest.approx(0.13, rel=0.02)

    def test_no_drawdown(self, quant):
        """Test with no drawdown (always growing)."""
        equity = [100, 110, 120, 130, 140]

        current_dd, max_dd, _ = quant.calculate_drawdown(equity)

        assert current_dd == 0.0
        assert max_dd == 0.0


class TestExpectancy:
    """Tests for expectancy calculation."""

    def test_positive_expectancy(self, quant):
        """Test positive expectancy."""
        exp = quant.calculate_expectancy(
            win_rate=0.5,
            avg_win=200.0,
            avg_loss=100.0,
        )

        # (0.5 * 200) - (0.5 * 100) = 50
        assert exp == pytest.approx(50.0)

    def test_negative_expectancy(self, quant):
        """Test negative expectancy."""
        exp = quant.calculate_expectancy(
            win_rate=0.4,
            avg_win=100.0,
            avg_loss=100.0,
        )

        # (0.4 * 100) - (0.6 * 100) = -20
        assert exp == pytest.approx(-20.0)


class TestSharpeRatio:
    """Tests for Sharpe ratio calculation."""

    def test_sharpe_positive(self, quant):
        """Test Sharpe with positive returns."""
        returns = [0.01, 0.02, -0.005, 0.015, 0.01]

        sharpe = quant.calculate_sharpe_ratio(returns, periods_per_year=252)

        assert sharpe > 0

    def test_sharpe_insufficient_data(self, quant):
        """Test Sharpe with insufficient data."""
        sharpe = quant.calculate_sharpe_ratio([0.01])

        assert sharpe == 0.0
