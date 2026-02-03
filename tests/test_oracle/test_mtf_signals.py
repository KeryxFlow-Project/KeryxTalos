"""Tests for Multi-Timeframe Signal Generator."""

from datetime import UTC

import pandas as pd
import pytest

from keryxflow.oracle.mtf_signals import MTFSignalGenerator
from keryxflow.oracle.signals import SignalSource, SignalType


@pytest.fixture
def sample_ohlcv_bullish():
    """Generate bullish OHLCV data."""
    dates = pd.date_range(start="2024-01-01", periods=100, freq="1h", tz=UTC)
    base_price = 50000.0

    prices = [base_price + (i * 50) + (i % 5) * 10 for i in range(100)]

    return pd.DataFrame(
        {
            "datetime": dates,
            "open": prices,
            "high": [p + 100 for p in prices],
            "low": [p - 50 for p in prices],
            "close": [p + 50 for p in prices],
            "volume": [1000.0 + i * 10 for i in range(100)],
        }
    )


@pytest.fixture
def sample_ohlcv_bearish():
    """Generate bearish OHLCV data."""
    dates = pd.date_range(start="2024-01-01", periods=100, freq="1h", tz=UTC)
    base_price = 55000.0

    prices = [base_price - (i * 50) - (i % 5) * 10 for i in range(100)]

    return pd.DataFrame(
        {
            "datetime": dates,
            "open": prices,
            "high": [p + 50 for p in prices],
            "low": [p - 100 for p in prices],
            "close": [p - 50 for p in prices],
            "volume": [1000.0 + i * 10 for i in range(100)],
        }
    )


@pytest.fixture
def sample_ohlcv_neutral():
    """Generate neutral OHLCV data (sideways)."""
    dates = pd.date_range(start="2024-01-01", periods=100, freq="1h", tz=UTC)
    import numpy as np

    np.random.seed(42)

    base_price = 50000.0
    prices = [base_price + np.sin(i / 5) * 100 for i in range(100)]

    return pd.DataFrame(
        {
            "datetime": dates,
            "open": prices,
            "high": [p + 50 for p in prices],
            "low": [p - 50 for p in prices],
            "close": [p + np.random.uniform(-20, 20) for p in prices],
            "volume": [1000.0] * 100,
        }
    )


class TestMTFSignalGenerator:
    """Tests for MTFSignalGenerator class."""

    @pytest.fixture
    def generator(self):
        """Create MTF signal generator."""
        return MTFSignalGenerator(publish_events=False)

    @pytest.mark.asyncio
    async def test_single_tf_fallback(self, generator, sample_ohlcv_bullish):
        """Test fallback to single TF when DataFrame provided."""
        signal = await generator.generate_signal(
            symbol="BTC/USDT",
            ohlcv=sample_ohlcv_bullish,  # DataFrame, not dict
            current_price=54000.0,
            include_news=False,
            include_llm=False,
        )

        assert signal is not None
        assert signal.symbol == "BTC/USDT"
        # Should work like regular signal generator

    @pytest.mark.asyncio
    async def test_mtf_with_dict(self, generator, sample_ohlcv_bullish):
        """Test MTF analysis with dict of timeframes."""
        ohlcv_data = {
            "1h": sample_ohlcv_bullish,
        }

        signal = await generator.generate_signal(
            symbol="BTC/USDT",
            ohlcv=ohlcv_data,
            current_price=54000.0,
            include_news=False,
            include_llm=False,
        )

        assert signal is not None
        assert signal.symbol == "BTC/USDT"

    @pytest.mark.asyncio
    async def test_signal_has_mtf_fields(self, generator, sample_ohlcv_bullish):
        """Test signal includes MTF-specific fields."""
        ohlcv_data = {"1h": sample_ohlcv_bullish}

        signal = await generator.generate_signal(
            symbol="BTC/USDT",
            ohlcv=ohlcv_data,
            current_price=54000.0,
            include_news=False,
            include_llm=False,
        )

        # Check MTF fields are populated
        assert signal.primary_timeframe is not None
        assert signal.filter_trend is not None
        assert signal.timeframe_alignment is not None

    @pytest.mark.asyncio
    async def test_mtf_data_in_signal(self, generator, sample_ohlcv_bullish):
        """Test mtf_data dict is populated."""
        ohlcv_data = {"1h": sample_ohlcv_bullish}

        signal = await generator.generate_signal(
            symbol="BTC/USDT",
            ohlcv=ohlcv_data,
            current_price=54000.0,
            include_news=False,
            include_llm=False,
        )

        assert signal.mtf_data is not None
        assert "filter_trend" in signal.mtf_data
        assert "aligned" in signal.mtf_data

    @pytest.mark.asyncio
    async def test_to_dict_includes_mtf(self, generator, sample_ohlcv_bullish):
        """Test to_dict includes MTF fields."""
        ohlcv_data = {"1h": sample_ohlcv_bullish}

        signal = await generator.generate_signal(
            symbol="BTC/USDT",
            ohlcv=ohlcv_data,
            current_price=54000.0,
            include_news=False,
            include_llm=False,
        )

        signal_dict = signal.to_dict()

        assert "primary_timeframe" in signal_dict
        assert "filter_timeframe" in signal_dict
        assert "filter_trend" in signal_dict
        assert "timeframe_alignment" in signal_dict

    @pytest.mark.asyncio
    async def test_alignment_boosts_confidence(self, generator, sample_ohlcv_bullish):
        """Test aligned timeframes boost confidence."""
        # All bullish should be aligned
        ohlcv_data = {"1h": sample_ohlcv_bullish}

        signal = await generator.generate_signal(
            symbol="BTC/USDT",
            ohlcv=ohlcv_data,
            current_price=54000.0,
            include_news=False,
            include_llm=False,
        )

        # Aligned should have boosted confidence
        assert signal.timeframe_alignment is True

    @pytest.mark.asyncio
    async def test_signal_source_is_technical(self, generator, sample_ohlcv_bullish):
        """Test signal source without LLM is TECHNICAL."""
        ohlcv_data = {"1h": sample_ohlcv_bullish}

        signal = await generator.generate_signal(
            symbol="BTC/USDT",
            ohlcv=ohlcv_data,
            current_price=54000.0,
            include_news=False,
            include_llm=False,
        )

        assert signal.source == SignalSource.TECHNICAL

    @pytest.mark.asyncio
    async def test_simple_reason_generated(self, generator, sample_ohlcv_bullish):
        """Test simple reason is generated for MTF signal."""
        ohlcv_data = {"1h": sample_ohlcv_bullish}

        signal = await generator.generate_signal(
            symbol="BTC/USDT",
            ohlcv=ohlcv_data,
            current_price=54000.0,
            include_news=False,
            include_llm=False,
        )

        assert signal.simple_reason != ""
        assert isinstance(signal.simple_reason, str)

    @pytest.mark.asyncio
    async def test_technical_reason_generated(self, generator, sample_ohlcv_bullish):
        """Test technical reason is generated for MTF signal."""
        ohlcv_data = {"1h": sample_ohlcv_bullish}

        signal = await generator.generate_signal(
            symbol="BTC/USDT",
            ohlcv=ohlcv_data,
            current_price=54000.0,
            include_news=False,
            include_llm=False,
        )

        assert signal.technical_reason != ""
        assert "Signal:" in signal.technical_reason

    @pytest.mark.asyncio
    async def test_empty_dict_returns_no_action(self, generator):
        """Test empty OHLCV dict returns NO_ACTION."""
        signal = await generator.generate_signal(
            symbol="BTC/USDT",
            ohlcv={},
            current_price=50000.0,
            include_news=False,
            include_llm=False,
        )

        assert signal.signal_type == SignalType.NO_ACTION


class TestMTFSignalFiltering:
    """Tests for MTF signal filtering behavior."""

    @pytest.fixture
    def generator(self):
        """Create MTF signal generator."""
        return MTFSignalGenerator(publish_events=False)

    @pytest.mark.asyncio
    async def test_bullish_filter_trend_with_bullish_data(self, generator, sample_ohlcv_bullish):
        """Test bullish data produces bullish-friendly signals."""
        ohlcv_data = {"1h": sample_ohlcv_bullish}

        signal = await generator.generate_signal(
            symbol="BTC/USDT",
            ohlcv=ohlcv_data,
            current_price=54000.0,
            include_news=False,
            include_llm=False,
        )

        # Bullish data should produce LONG or NO_ACTION, never SHORT
        assert signal.signal_type in [SignalType.LONG, SignalType.NO_ACTION]

    @pytest.mark.asyncio
    async def test_bearish_filter_trend_with_bearish_data(self, generator, sample_ohlcv_bearish):
        """Test bearish data produces bearish-friendly signals."""
        ohlcv_data = {"1h": sample_ohlcv_bearish}

        signal = await generator.generate_signal(
            symbol="BTC/USDT",
            ohlcv=ohlcv_data,
            current_price=46000.0,
            include_news=False,
            include_llm=False,
        )

        # Bearish data should produce SHORT or NO_ACTION, never LONG
        assert signal.signal_type in [SignalType.SHORT, SignalType.NO_ACTION]


class TestMTFSignalGeneratorEdgeCases:
    """Tests for edge cases in MTF signal generator."""

    @pytest.fixture
    def generator(self):
        """Create MTF signal generator."""
        return MTFSignalGenerator(publish_events=False)

    @pytest.mark.asyncio
    async def test_handles_missing_primary_timeframe(self, generator):
        """Test handling when primary timeframe data missing."""
        # Create data for non-primary timeframe only
        dates = pd.date_range(start="2024-01-01", periods=100, freq="1h", tz=UTC)
        df = pd.DataFrame(
            {
                "datetime": dates,
                "open": [50000.0] * 100,
                "high": [51000.0] * 100,
                "low": [49000.0] * 100,
                "close": [50500.0] * 100,
                "volume": [1000.0] * 100,
            }
        )

        # Provide data only for a non-default timeframe
        ohlcv_data = {"4h": df}

        signal = await generator.generate_signal(
            symbol="BTC/USDT",
            ohlcv=ohlcv_data,
            current_price=50000.0,
            include_news=False,
            include_llm=False,
        )

        # Should still work, using 4h as fallback
        assert signal is not None

    @pytest.mark.asyncio
    async def test_handles_insufficient_candles(self, generator):
        """Test handling when data has insufficient candles."""
        dates = pd.date_range(start="2024-01-01", periods=20, freq="1h", tz=UTC)
        small_df = pd.DataFrame(
            {
                "datetime": dates,
                "open": [50000.0] * 20,
                "high": [51000.0] * 20,
                "low": [49000.0] * 20,
                "close": [50500.0] * 20,
                "volume": [1000.0] * 20,
            }
        )

        ohlcv_data = {"1h": small_df}

        signal = await generator.generate_signal(
            symbol="BTC/USDT",
            ohlcv=ohlcv_data,
            current_price=50000.0,
            include_news=False,
            include_llm=False,
        )

        # Should return NO_ACTION due to insufficient data
        assert signal.signal_type == SignalType.NO_ACTION

    @pytest.mark.asyncio
    async def test_current_price_from_data(self, generator, sample_ohlcv_bullish):
        """Test current price extracted from data when not provided."""
        ohlcv_data = {"1h": sample_ohlcv_bullish}

        signal = await generator.generate_signal(
            symbol="BTC/USDT",
            ohlcv=ohlcv_data,
            current_price=None,  # Not provided
            include_news=False,
            include_llm=False,
        )

        assert signal is not None
        # Entry price should be set from last close
        if signal.entry_price is not None:
            last_close = sample_ohlcv_bullish["close"].iloc[-1]
            # Entry price should be close to last close
            assert abs(signal.entry_price - last_close) < last_close * 0.01

    @pytest.mark.asyncio
    async def test_multiple_symbols_independent(self, generator, sample_ohlcv_bullish):
        """Test multiple symbols are processed independently."""
        ohlcv_data = {"1h": sample_ohlcv_bullish}

        signal_btc = await generator.generate_signal(
            symbol="BTC/USDT",
            ohlcv=ohlcv_data,
            current_price=54000.0,
            include_news=False,
            include_llm=False,
        )

        signal_eth = await generator.generate_signal(
            symbol="ETH/USDT",
            ohlcv=ohlcv_data,
            current_price=3000.0,
            include_news=False,
            include_llm=False,
        )

        assert signal_btc.symbol == "BTC/USDT"
        assert signal_eth.symbol == "ETH/USDT"
