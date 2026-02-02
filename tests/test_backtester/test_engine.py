"""Tests for backtester engine."""

from datetime import UTC, datetime

import pandas as pd
import pytest

from keryxflow.backtester.engine import (
    BacktestEngine,
    BacktestPosition,
    BacktestTrade,
)
from keryxflow.core.models import RiskProfile


class TestBacktestTrade:
    """Tests for BacktestTrade dataclass."""

    def test_is_closed_false(self):
        """Test trade is not closed without exit price."""
        trade = BacktestTrade(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.1,
            entry_price=50000.0,
            entry_time=datetime.now(UTC),
        )

        assert trade.is_closed is False

    def test_is_closed_true(self):
        """Test trade is closed with exit price."""
        trade = BacktestTrade(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.1,
            entry_price=50000.0,
            entry_time=datetime.now(UTC),
            exit_price=51000.0,
            exit_time=datetime.now(UTC),
        )

        assert trade.is_closed is True

    def test_is_winner_true(self):
        """Test winning trade."""
        trade = BacktestTrade(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.1,
            entry_price=50000.0,
            entry_time=datetime.now(UTC),
            exit_price=51000.0,
            pnl=100.0,
        )

        assert trade.is_winner is True

    def test_is_winner_false(self):
        """Test losing trade."""
        trade = BacktestTrade(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.1,
            entry_price=50000.0,
            entry_time=datetime.now(UTC),
            exit_price=49000.0,
            pnl=-100.0,
        )

        assert trade.is_winner is False


class TestBacktestPosition:
    """Tests for BacktestPosition dataclass."""

    def test_unrealized_pnl_long_profit(self):
        """Test unrealized PnL for profitable long."""
        position = BacktestPosition(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.1,
            entry_price=50000.0,
            entry_time=datetime.now(UTC),
            current_price=51000.0,
        )

        assert position.unrealized_pnl == 100.0  # (51000 - 50000) * 0.1

    def test_unrealized_pnl_long_loss(self):
        """Test unrealized PnL for losing long."""
        position = BacktestPosition(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.1,
            entry_price=50000.0,
            entry_time=datetime.now(UTC),
            current_price=49000.0,
        )

        assert position.unrealized_pnl == -100.0

    def test_unrealized_pnl_short_profit(self):
        """Test unrealized PnL for profitable short."""
        position = BacktestPosition(
            symbol="BTC/USDT",
            side="sell",
            quantity=0.1,
            entry_price=50000.0,
            entry_time=datetime.now(UTC),
            current_price=49000.0,
        )

        assert position.unrealized_pnl == 100.0  # (50000 - 49000) * 0.1

    def test_unrealized_pnl_short_loss(self):
        """Test unrealized PnL for losing short."""
        position = BacktestPosition(
            symbol="BTC/USDT",
            side="sell",
            quantity=0.1,
            entry_price=50000.0,
            entry_time=datetime.now(UTC),
            current_price=51000.0,
        )

        assert position.unrealized_pnl == -100.0

    def test_unrealized_pnl_percentage(self):
        """Test unrealized PnL percentage."""
        position = BacktestPosition(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.1,
            entry_price=50000.0,
            entry_time=datetime.now(UTC),
            current_price=55000.0,
        )

        assert position.unrealized_pnl_percentage == 10.0  # 10% gain


class TestBacktestEngineInit:
    """Tests for BacktestEngine initialization."""

    def test_default_init(self):
        """Test default initialization."""
        engine = BacktestEngine()

        assert engine.initial_balance == 10000.0
        assert engine.risk_profile == RiskProfile.BALANCED
        assert engine.slippage == 0.001
        assert engine.commission == 0.001
        assert engine.min_candles == 50
        assert engine.balance == 10000.0
        assert engine.positions == {}
        assert engine.trades == []

    def test_custom_init(self):
        """Test custom initialization."""
        engine = BacktestEngine(
            initial_balance=50000.0,
            risk_profile=RiskProfile.AGGRESSIVE,
            slippage=0.002,
            commission=0.0005,
        )

        assert engine.initial_balance == 50000.0
        assert engine.risk_profile == RiskProfile.AGGRESSIVE
        assert engine.slippage == 0.002
        assert engine.commission == 0.0005

    def test_components_initialized(self):
        """Test that components are initialized."""
        engine = BacktestEngine()

        assert engine.signal_gen is not None
        assert engine.risk_manager is not None
        assert engine.quant is not None


class TestBacktestEngineStops:
    """Tests for stop loss/take profit checking."""

    def test_check_stops_no_position(self):
        """Test check_stops with no position."""
        engine = BacktestEngine()
        engine._check_stops("BTC/USDT", 51000.0, 49000.0)

        # Should not raise, just return
        assert "BTC/USDT" not in engine.positions

    def test_check_stops_long_stop_hit(self):
        """Test stop loss hit on long position."""
        engine = BacktestEngine()
        engine._current_time = datetime.now(UTC)

        # Add position
        engine.positions["BTC/USDT"] = BacktestPosition(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.1,
            entry_price=50000.0,
            entry_time=datetime.now(UTC),
            stop_loss=49000.0,
            current_price=50000.0,
        )

        # Check stops with low below stop
        engine._check_stops("BTC/USDT", 50500.0, 48500.0)

        # Position should be closed
        assert "BTC/USDT" not in engine.positions
        assert len(engine.trades) == 1
        assert engine.trades[0].exit_reason == "stop_loss"

    def test_check_stops_long_take_profit_hit(self):
        """Test take profit hit on long position."""
        engine = BacktestEngine()
        engine._current_time = datetime.now(UTC)

        # Add position
        engine.positions["BTC/USDT"] = BacktestPosition(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.1,
            entry_price=50000.0,
            entry_time=datetime.now(UTC),
            take_profit=52000.0,
            current_price=50000.0,
        )

        # Check stops with high above take profit
        engine._check_stops("BTC/USDT", 52500.0, 50000.0)

        # Position should be closed
        assert "BTC/USDT" not in engine.positions
        assert len(engine.trades) == 1
        assert engine.trades[0].exit_reason == "take_profit"

    def test_check_stops_short_stop_hit(self):
        """Test stop loss hit on short position."""
        engine = BacktestEngine()
        engine._current_time = datetime.now(UTC)

        # Add short position
        engine.positions["BTC/USDT"] = BacktestPosition(
            symbol="BTC/USDT",
            side="sell",
            quantity=0.1,
            entry_price=50000.0,
            entry_time=datetime.now(UTC),
            stop_loss=51000.0,
            current_price=50000.0,
        )

        # Check stops with high above stop
        engine._check_stops("BTC/USDT", 51500.0, 49500.0)

        # Position should be closed
        assert "BTC/USDT" not in engine.positions
        assert len(engine.trades) == 1
        assert engine.trades[0].exit_reason == "stop_loss"


class TestBacktestEngineExecution:
    """Tests for order execution."""

    def test_calculate_equity_no_positions(self):
        """Test equity calculation with no positions."""
        engine = BacktestEngine(initial_balance=10000.0)

        assert engine._calculate_equity() == 10000.0

    def test_calculate_equity_with_position(self):
        """Test equity calculation with open position."""
        engine = BacktestEngine(initial_balance=10000.0)
        engine.balance = 5000.0  # Used 5000 for position

        engine.positions["BTC/USDT"] = BacktestPosition(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.1,
            entry_price=50000.0,
            entry_time=datetime.now(UTC),
            current_price=51000.0,  # 100 unrealized profit
        )

        equity = engine._calculate_equity()
        assert equity == 5100.0  # 5000 + 100 unrealized


class TestBacktestEngineRun:
    """Integration tests for backtest run."""

    @pytest.fixture
    def sample_data(self):
        """Create sample OHLCV data."""
        # Create 100 candles of synthetic data
        dates = pd.date_range("2024-01-01", periods=100, freq="h", tz=UTC)

        # Simple trending data
        base_price = 50000.0
        prices = [base_price + (i * 50) for i in range(100)]

        return {
            "BTC/USDT": pd.DataFrame(
                {
                    "datetime": dates,
                    "open": [p - 10 for p in prices],
                    "high": [p + 50 for p in prices],
                    "low": [p - 100 for p in prices],
                    "close": prices,
                    "volume": [1000.0] * 100,
                }
            )
        }

    @pytest.mark.asyncio
    async def test_run_no_data_raises(self):
        """Test run with no data raises error."""
        engine = BacktestEngine()

        with pytest.raises(ValueError):
            await engine.run({})

    @pytest.mark.asyncio
    async def test_run_returns_result(self, sample_data):
        """Test run returns BacktestResult."""
        engine = BacktestEngine(initial_balance=10000.0, min_candles=20)

        result = await engine.run(sample_data)

        assert result is not None
        assert result.initial_balance == 10000.0
        assert result.final_balance >= 0
        assert len(result.equity_curve) > 0

    @pytest.mark.asyncio
    async def test_run_equity_curve_starts_with_initial(self, sample_data):
        """Test equity curve starts with initial balance."""
        engine = BacktestEngine(initial_balance=10000.0, min_candles=20)

        result = await engine.run(sample_data)

        assert result.equity_curve[0] == 10000.0

    @pytest.mark.asyncio
    async def test_run_with_date_range(self, sample_data):
        """Test run with date range filter."""
        engine = BacktestEngine(initial_balance=10000.0, min_candles=20)

        start = datetime(2024, 1, 2, tzinfo=UTC)
        end = datetime(2024, 1, 3, tzinfo=UTC)

        result = await engine.run(sample_data, start=start, end=end)

        assert result is not None


class TestBacktestResult:
    """Tests for BacktestResult."""

    def test_to_dict(self):
        """Test to_dict conversion."""
        from keryxflow.backtester.report import BacktestResult

        result = BacktestResult(
            initial_balance=10000.0,
            final_balance=12000.0,
            total_return=0.20,
            total_trades=10,
            winning_trades=6,
            losing_trades=4,
            win_rate=0.6,
            avg_win=500.0,
            avg_loss=200.0,
            expectancy=220.0,
            profit_factor=3.75,
            max_drawdown=0.05,
            max_drawdown_duration=10,
            sharpe_ratio=1.5,
            trades=[],
            equity_curve=[10000.0, 12000.0],
        )

        d = result.to_dict()

        assert d["performance"]["initial_balance"] == 10000.0
        assert d["performance"]["final_balance"] == 12000.0
        assert d["trades"]["total"] == 10
        assert d["trades"]["win_rate"] == 0.6
        assert d["risk"]["sharpe_ratio"] == 1.5
