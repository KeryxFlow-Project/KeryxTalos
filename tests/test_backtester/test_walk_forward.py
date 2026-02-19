"""Tests for walk-forward analysis engine."""

from datetime import datetime, timedelta

import pandas as pd
import pytest

from keryxflow.backtester.walk_forward import (
    WalkForwardConfig,
    WalkForwardEngine,
    WalkForwardResult,
)


def _make_ohlcv_df(num_candles: int = 500, start_price: float = 50000.0) -> pd.DataFrame:
    """Create synthetic OHLCV data for testing."""
    import numpy as np

    rng = np.random.default_rng(42)
    base_time = datetime(2024, 1, 1)

    data = []
    price = start_price
    for i in range(num_candles):
        change = rng.normal(0, 100)
        open_price = price
        close_price = price + change
        high_price = max(open_price, close_price) + abs(rng.normal(0, 50))
        low_price = min(open_price, close_price) - abs(rng.normal(0, 50))
        volume = rng.uniform(100, 1000)

        data.append(
            {
                "datetime": base_time + timedelta(hours=i),
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": volume,
            }
        )
        price = close_price

    return pd.DataFrame(data)


class TestWalkForwardConfig:
    """Tests for WalkForwardConfig defaults."""

    def test_defaults(self):
        """Test default configuration values."""
        config = WalkForwardConfig()
        assert config.num_windows == 5
        assert config.oos_pct == 0.3
        assert config.optimization_metric == "sharpe_ratio"
        assert config.initial_balance == 10000.0

    def test_custom_config(self):
        """Test custom configuration."""
        config = WalkForwardConfig(num_windows=3, oos_pct=0.2)
        assert config.num_windows == 3
        assert config.oos_pct == 0.2


class TestWalkForwardWindowSplitting:
    """Tests for data window splitting logic."""

    def test_split_windows_count(self):
        """Test that correct number of windows are created."""
        config = WalkForwardConfig(num_windows=5, oos_pct=0.3)
        engine = WalkForwardEngine(config=config)

        timestamps = [datetime(2024, 1, 1) + timedelta(hours=i) for i in range(500)]
        windows = engine._split_windows(timestamps)

        assert len(windows) == 5

    def test_split_windows_no_overlap(self):
        """Test that OOS periods don't overlap between windows."""
        config = WalkForwardConfig(num_windows=3, oos_pct=0.3)
        engine = WalkForwardEngine(config=config)

        timestamps = [datetime(2024, 1, 1) + timedelta(hours=i) for i in range(300)]
        windows = engine._split_windows(timestamps)

        for i in range(len(windows) - 1):
            _, _, _, oos_end = windows[i]
            is_start, _, _, _ = windows[i + 1]
            # Each window's OOS end should be before or equal to next window's IS start
            assert oos_end <= is_start

    def test_split_windows_is_before_oos(self):
        """Test that IS period comes before OOS in each window."""
        config = WalkForwardConfig(num_windows=4, oos_pct=0.3)
        engine = WalkForwardEngine(config=config)

        timestamps = [datetime(2024, 1, 1) + timedelta(hours=i) for i in range(400)]
        windows = engine._split_windows(timestamps)

        for is_start, is_end, oos_start, oos_end in windows:
            assert is_start < is_end
            assert is_end < oos_start
            assert oos_start <= oos_end

    def test_slice_data(self):
        """Test data slicing by time range."""
        engine = WalkForwardEngine()
        df = _make_ohlcv_df(100)

        start = df["datetime"].iloc[10]
        end = df["datetime"].iloc[50]
        sliced = engine._slice_data({"BTC/USDT": df}, start, end)

        assert "BTC/USDT" in sliced
        assert len(sliced["BTC/USDT"]) == 41  # inclusive range

    def test_insufficient_data_raises(self):
        """Test that insufficient data raises ValueError."""
        config = WalkForwardConfig(num_windows=10)
        engine = WalkForwardEngine(config=config)

        df = pd.DataFrame(
            {
                "datetime": [datetime(2024, 1, 1) + timedelta(hours=i) for i in range(5)],
                "open": [100] * 5,
                "high": [101] * 5,
                "low": [99] * 5,
                "close": [100] * 5,
                "volume": [1000] * 5,
            }
        )

        with pytest.raises(ValueError, match="Insufficient data"):
            import asyncio

            asyncio.get_event_loop().run_until_complete(
                engine.run(
                    data={"BTC/USDT": df},
                    grid=None,  # Won't reach grid usage
                )
            )


class TestWalkForwardResult:
    """Tests for WalkForwardResult."""

    def test_empty_result(self):
        """Test empty walk-forward result."""
        engine = WalkForwardEngine()
        result = engine._compute_aggregates([])

        assert result.num_windows == 0
        assert result.aggregate_oos_return == 0.0
        assert result.aggregate_oos_trades == 0

    def test_to_dict(self):
        """Test WalkForwardResult to_dict."""
        result = WalkForwardResult(
            num_windows=3,
            oos_pct=0.3,
            aggregate_oos_return=0.05,
            aggregate_oos_trades=15,
            aggregate_oos_win_rate=0.6,
            avg_degradation_ratio=0.8,
        )

        d = result.to_dict()
        assert d["num_windows"] == 3
        assert d["oos_pct"] == 0.3
        assert "aggregate" in d
        assert d["aggregate"]["oos_return"] == 0.05
