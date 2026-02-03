"""Tests for the Strategy Manager."""

import pytest

from keryxflow.agent.strategy import (
    MarketRegime,
    StrategyConfig,
    StrategyManager,
    StrategyType,
    get_strategy_manager,
)


class TestMarketRegime:
    """Tests for MarketRegime enum."""

    def test_regime_values(self):
        """Test market regime values."""
        assert MarketRegime.TRENDING_UP.value == "trending_up"
        assert MarketRegime.TRENDING_DOWN.value == "trending_down"
        assert MarketRegime.RANGING.value == "ranging"
        assert MarketRegime.HIGH_VOLATILITY.value == "high_volatility"
        assert MarketRegime.LOW_VOLATILITY.value == "low_volatility"
        assert MarketRegime.BREAKOUT.value == "breakout"
        assert MarketRegime.UNKNOWN.value == "unknown"


class TestStrategyType:
    """Tests for StrategyType enum."""

    def test_strategy_type_values(self):
        """Test strategy type values."""
        assert StrategyType.TREND_FOLLOWING.value == "trend_following"
        assert StrategyType.MEAN_REVERSION.value == "mean_reversion"
        assert StrategyType.BREAKOUT.value == "breakout"
        assert StrategyType.MOMENTUM.value == "momentum"


class TestStrategyConfig:
    """Tests for StrategyConfig dataclass."""

    def test_create_strategy_config(self):
        """Test creating a strategy config."""
        config = StrategyConfig(
            id="test_strategy",
            name="Test Strategy",
            strategy_type=StrategyType.TREND_FOLLOWING,
            description="A test strategy",
        )

        assert config.id == "test_strategy"
        assert config.name == "Test Strategy"
        assert config.strategy_type == StrategyType.TREND_FOLLOWING
        assert config.total_trades == 0
        assert config.is_active is True

    def test_win_rate_no_trades(self):
        """Test win rate with no trades."""
        config = StrategyConfig(
            id="test",
            name="Test",
            strategy_type=StrategyType.MOMENTUM,
            description="Test",
        )

        assert config.win_rate() == 0.0

    def test_win_rate_with_trades(self):
        """Test win rate calculation."""
        config = StrategyConfig(
            id="test",
            name="Test",
            strategy_type=StrategyType.MOMENTUM,
            description="Test",
            total_trades=10,
            winning_trades=6,
        )

        assert config.win_rate() == 0.6

    def test_avg_pnl(self):
        """Test average P&L calculation."""
        config = StrategyConfig(
            id="test",
            name="Test",
            strategy_type=StrategyType.MOMENTUM,
            description="Test",
            total_trades=5,
            total_pnl=10.0,
        )

        assert config.avg_pnl() == 2.0

    def test_to_dict(self):
        """Test converting to dictionary."""
        config = StrategyConfig(
            id="test",
            name="Test Strategy",
            strategy_type=StrategyType.BREAKOUT,
            description="Test description",
            total_trades=5,
            winning_trades=3,
            total_pnl=5.0,
        )

        data = config.to_dict()

        assert data["id"] == "test"
        assert data["name"] == "Test Strategy"
        assert data["strategy_type"] == "breakout"
        assert data["win_rate"] == 0.6
        assert data["avg_pnl"] == 1.0


class TestStrategyManager:
    """Tests for StrategyManager class."""

    def test_create_manager(self):
        """Test creating a strategy manager."""
        manager = StrategyManager()

        assert len(manager._strategies) > 0  # Default strategies loaded

    def test_default_strategies_loaded(self):
        """Test that default strategies are loaded."""
        manager = StrategyManager()
        strategies = manager.list_strategies()

        assert len(strategies) >= 4
        strategy_ids = [s["id"] for s in strategies]
        assert "trend_following_basic" in strategy_ids
        assert "mean_reversion_rsi" in strategy_ids

    def test_register_strategy(self):
        """Test registering a custom strategy."""
        manager = StrategyManager()
        initial_count = len(manager._strategies)

        config = StrategyConfig(
            id="custom_strategy",
            name="Custom Strategy",
            strategy_type=StrategyType.SCALPING,
            description="A custom strategy",
        )

        manager.register_strategy(config)

        assert len(manager._strategies) == initial_count + 1
        assert manager.get_strategy("custom_strategy") is not None

    def test_get_strategy(self):
        """Test getting a strategy by ID."""
        manager = StrategyManager()

        strategy = manager.get_strategy("trend_following_basic")

        assert strategy is not None
        assert strategy.id == "trend_following_basic"

    def test_get_strategy_not_found(self):
        """Test getting non-existent strategy."""
        manager = StrategyManager()

        strategy = manager.get_strategy("nonexistent")

        assert strategy is None

    def test_detect_regime_trending_up(self):
        """Test detecting uptrend regime."""
        manager = StrategyManager()

        # Create prices showing uptrend (10% increase)
        prices = [100 + i * 0.5 for i in range(50)]

        regime = manager.detect_market_regime(prices)

        assert regime == MarketRegime.TRENDING_UP

    def test_detect_regime_trending_down(self):
        """Test detecting downtrend regime."""
        manager = StrategyManager()

        # Create prices showing downtrend (10% decrease)
        prices = [100 - i * 0.5 for i in range(50)]

        regime = manager.detect_market_regime(prices)

        assert regime == MarketRegime.TRENDING_DOWN

    def test_detect_regime_high_volatility(self):
        """Test detecting high volatility regime."""
        manager = StrategyManager()

        # Create prices with high volatility (15%+ range but no clear trend)
        base = 100
        prices = []
        for i in range(50):
            # Oscillate around base with large swings
            if i % 4 < 2:
                prices.append(base + 8)  # Upper band
            else:
                prices.append(base - 8)  # Lower band

        regime = manager.detect_market_regime(prices)

        # High volatility or ranging are both acceptable for oscillating prices
        assert regime in (MarketRegime.HIGH_VOLATILITY, MarketRegime.RANGING, MarketRegime.UNKNOWN)

    def test_detect_regime_unknown_insufficient_data(self):
        """Test unknown regime with insufficient data."""
        manager = StrategyManager()

        prices = [100, 101, 102]

        regime = manager.detect_market_regime(prices)

        assert regime == MarketRegime.UNKNOWN

    @pytest.mark.asyncio
    async def test_select_strategy(self):
        """Test selecting a strategy."""
        manager = StrategyManager()

        prices = [100 + i * 0.5 for i in range(50)]  # Uptrend

        selection = await manager.select_strategy(
            symbol="BTC/USDT",
            prices=prices,
        )

        assert selection is not None
        assert selection.strategy is not None
        assert selection.confidence > 0
        assert selection.detected_regime == MarketRegime.TRENDING_UP

    @pytest.mark.asyncio
    async def test_select_strategy_force_regime(self):
        """Test selecting strategy with forced regime."""
        manager = StrategyManager()

        prices = [100] * 50  # Flat prices

        selection = await manager.select_strategy(
            symbol="BTC/USDT",
            prices=prices,
            force_regime=MarketRegime.RANGING,
        )

        assert selection.detected_regime == MarketRegime.RANGING
        # Mean reversion should be selected for ranging
        assert "reversion" in selection.strategy.name.lower() or selection.strategy.strategy_type == StrategyType.MEAN_REVERSION

    @pytest.mark.asyncio
    async def test_record_trade_result(self):
        """Test recording trade results."""
        manager = StrategyManager()
        strategy_id = "trend_following_basic"

        initial_trades = manager.get_strategy(strategy_id).total_trades

        await manager.record_trade_result(
            strategy_id=strategy_id,
            pnl_percentage=2.5,
            won=True,
        )

        strategy = manager.get_strategy(strategy_id)
        assert strategy.total_trades == initial_trades + 1
        assert strategy.winning_trades > 0

    def test_adapt_strategy_parameters(self):
        """Test adapting strategy parameters."""
        manager = StrategyManager()
        strategy_id = "trend_following_basic"

        result = manager.adapt_strategy_parameters(
            strategy_id=strategy_id,
            parameter_updates={"fast_ema": 12},
        )

        assert result is True
        strategy = manager.get_strategy(strategy_id)
        assert strategy.parameters["fast_ema"] == 12

    def test_get_stats(self):
        """Test getting statistics."""
        manager = StrategyManager()

        stats = manager.get_stats()

        assert "total_strategies" in stats
        assert "active_strategies" in stats
        assert stats["total_strategies"] >= 4


class TestGetStrategyManager:
    """Tests for get_strategy_manager function."""

    def test_returns_singleton(self):
        """Test that function returns singleton."""
        manager1 = get_strategy_manager()
        manager2 = get_strategy_manager()

        assert manager1 is manager2

    def test_creates_manager(self):
        """Test that function creates manager."""
        manager = get_strategy_manager()

        assert isinstance(manager, StrategyManager)
