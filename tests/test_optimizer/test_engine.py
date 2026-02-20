"""Tests for the optimization engine module."""

from datetime import UTC, datetime

import pandas as pd
import pytest

from keryxflow.optimizer.engine import (
    OptimizationConfig,
    OptimizationEngine,
    OptimizationResult,
)
from keryxflow.optimizer.grid import ParameterGrid, ParameterRange


def generate_sample_data(
    start: datetime,
    periods: int = 200,
    base_price: float = 50000.0,
) -> pd.DataFrame:
    """Generate sample OHLCV data for testing."""
    import numpy as np

    np.random.seed(42)

    dates = pd.date_range(start=start, periods=periods, freq="h", tz=UTC)

    # Generate trending price data with some volatility
    returns = np.random.normal(0.0001, 0.01, periods)
    prices = base_price * np.cumprod(1 + returns)

    # Generate OHLCV
    data = {
        "datetime": dates,
        "open": prices * (1 + np.random.uniform(-0.002, 0.002, periods)),
        "high": prices * (1 + np.abs(np.random.uniform(0, 0.01, periods))),
        "low": prices * (1 - np.abs(np.random.uniform(0, 0.01, periods))),
        "close": prices,
        "volume": np.random.uniform(100, 1000, periods),
    }

    return pd.DataFrame(data)


class TestOptimizationConfig:
    """Tests for OptimizationConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = OptimizationConfig()

        assert config.initial_balance == 10000.0
        assert config.slippage == 0.001
        assert config.commission == 0.001

    def test_custom_config(self):
        """Test custom configuration values."""
        config = OptimizationConfig(
            initial_balance=50000.0,
            slippage=0.002,
            commission=0.0005,
        )

        assert config.initial_balance == 50000.0
        assert config.slippage == 0.002
        assert config.commission == 0.0005


class TestOptimizationResult:
    """Tests for OptimizationResult dataclass."""

    def test_get_metric(self):
        """Test getting metric values."""
        from keryxflow.backtester.report import BacktestResult

        metrics = BacktestResult(
            initial_balance=10000.0,
            final_balance=11000.0,
            total_return=0.1,
            total_trades=10,
            winning_trades=6,
            losing_trades=4,
            win_rate=0.6,
            avg_win=100.0,
            avg_loss=50.0,
            expectancy=40.0,
            profit_factor=2.0,
            max_drawdown=0.05,
            max_drawdown_duration=5,
            sharpe_ratio=1.5,
            trades=[],
            equity_curve=[10000.0],
        )

        result = OptimizationResult(
            parameters={"oracle": {"rsi_period": 14}, "risk": {}},
            metrics=metrics,
            run_time=1.0,
        )

        assert result.get_metric("sharpe_ratio") == 1.5
        assert result.get_metric("total_return") == 0.1
        assert result.get_metric("nonexistent") == 0.0

    def test_flat_parameters(self):
        """Test flattening parameters."""
        from keryxflow.backtester.report import BacktestResult

        metrics = BacktestResult(
            initial_balance=10000.0,
            final_balance=10000.0,
            total_return=0.0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            expectancy=0.0,
            profit_factor=0.0,
            max_drawdown=0.0,
            max_drawdown_duration=0,
            sharpe_ratio=0.0,
            trades=[],
            equity_curve=[10000.0],
        )

        result = OptimizationResult(
            parameters={
                "oracle": {"rsi_period": 14, "macd_fast": 12},
                "risk": {"risk_per_trade": 0.01},
            },
            metrics=metrics,
            run_time=1.0,
        )

        flat = result.flat_parameters()

        assert flat == {
            "rsi_period": 14,
            "macd_fast": 12,
            "risk_per_trade": 0.01,
        }


class TestOptimizationEngine:
    """Tests for OptimizationEngine class."""

    @pytest.mark.asyncio
    async def test_optimize_single_combination(self):
        """Test optimization with a single parameter combination."""
        start = datetime(2024, 1, 1, tzinfo=UTC)
        data = {"BTC/USDT": generate_sample_data(start)}

        grid = ParameterGrid([
            ParameterRange("rsi_period", [14], "oracle"),
        ])

        engine = OptimizationEngine()
        results = await engine.optimize(data, grid)

        assert len(results) == 1
        assert results[0].parameters["oracle"]["rsi_period"] == 14

    @pytest.mark.asyncio
    async def test_optimize_multiple_combinations(self):
        """Test optimization with multiple combinations."""
        start = datetime(2024, 1, 1, tzinfo=UTC)
        data = {"BTC/USDT": generate_sample_data(start)}

        grid = ParameterGrid([
            ParameterRange("rsi_period", [7, 14], "oracle"),
        ])

        engine = OptimizationEngine()
        results = await engine.optimize(data, grid)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_results_sorted_by_metric(self):
        """Test that results are sorted by metric."""
        start = datetime(2024, 1, 1, tzinfo=UTC)
        data = {"BTC/USDT": generate_sample_data(start, periods=300)}

        grid = ParameterGrid([
            ParameterRange("rsi_period", [7, 14, 21], "oracle"),
        ])

        engine = OptimizationEngine()
        results = await engine.optimize(data, grid, metric="sharpe_ratio")

        # Results should be sorted by sharpe_ratio descending
        sharpes = [r.metrics.sharpe_ratio for r in results]
        assert sharpes == sorted(sharpes, reverse=True)

    @pytest.mark.asyncio
    async def test_progress_callback(self):
        """Test progress callback is called."""
        start = datetime(2024, 1, 1, tzinfo=UTC)
        data = {"BTC/USDT": generate_sample_data(start)}

        grid = ParameterGrid([
            ParameterRange("rsi_period", [7, 14], "oracle"),
        ])

        progress_calls = []

        def callback(current, total, _params):
            progress_calls.append((current, total))

        engine = OptimizationEngine()
        await engine.optimize(data, grid, progress_callback=callback)

        assert len(progress_calls) == 2
        assert progress_calls[0] == (1, 2)
        assert progress_calls[1] == (2, 2)

    @pytest.mark.asyncio
    async def test_settings_restored_after_optimization(self):
        """Test that original settings are restored after optimization."""
        from keryxflow.config import get_settings

        start = datetime(2024, 1, 1, tzinfo=UTC)
        data = {"BTC/USDT": generate_sample_data(start)}

        # Get original settings
        settings = get_settings()
        original_rsi = settings.oracle.rsi_period

        grid = ParameterGrid([
            ParameterRange("rsi_period", [7], "oracle"),  # Different from default
        ])

        engine = OptimizationEngine()
        await engine.optimize(data, grid)

        # Settings should be restored
        assert settings.oracle.rsi_period == original_rsi

    @pytest.mark.asyncio
    async def test_custom_config(self):
        """Test optimization with custom config."""
        start = datetime(2024, 1, 1, tzinfo=UTC)
        data = {"BTC/USDT": generate_sample_data(start)}

        grid = ParameterGrid([
            ParameterRange("rsi_period", [14], "oracle"),
        ])

        config = OptimizationConfig(
            initial_balance=50000.0,
            slippage=0.002,
        )

        engine = OptimizationEngine(config)
        results = await engine.optimize(data, grid)

        assert len(results) == 1
        assert results[0].metrics.initial_balance == 50000.0
