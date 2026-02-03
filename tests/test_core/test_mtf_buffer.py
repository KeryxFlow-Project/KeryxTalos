"""Tests for Multi-Timeframe OHLCV Buffer."""

from datetime import UTC, datetime

import pandas as pd
import pytest

from keryxflow.core.mtf_buffer import (
    MultiTimeframeBuffer,
    TimeframeBuffer,
    TimeframeConfig,
    get_candle_time,
    timeframe_to_seconds,
)


class TestTimeframeToSeconds:
    """Tests for timeframe_to_seconds utility."""

    def test_standard_timeframes(self):
        """Test conversion of standard timeframes."""
        assert timeframe_to_seconds("1m") == 60
        assert timeframe_to_seconds("5m") == 300
        assert timeframe_to_seconds("15m") == 900
        assert timeframe_to_seconds("1h") == 3600
        assert timeframe_to_seconds("4h") == 14400
        assert timeframe_to_seconds("1d") == 86400

    def test_custom_timeframes(self):
        """Test conversion of custom timeframes."""
        assert timeframe_to_seconds("2h") == 7200
        assert timeframe_to_seconds("30m") == 1800
        assert timeframe_to_seconds("6h") == 21600

    def test_invalid_timeframe_raises(self):
        """Test invalid timeframe raises error."""
        with pytest.raises(ValueError):
            timeframe_to_seconds("invalid")


class TestGetCandleTime:
    """Tests for get_candle_time utility."""

    def test_1min_candle_time(self):
        """Test 1-minute candle time rounding."""
        dt = datetime(2024, 1, 1, 12, 34, 56, tzinfo=UTC)
        result = get_candle_time(dt, 60)
        assert result.second == 0
        assert result.microsecond == 0
        assert result.minute == 34

    def test_1h_candle_time(self):
        """Test 1-hour candle time rounding."""
        dt = datetime(2024, 1, 1, 12, 34, 56, tzinfo=UTC)
        result = get_candle_time(dt, 3600)
        assert result.minute == 0
        assert result.second == 0
        assert result.hour == 12


class TestTimeframeConfig:
    """Tests for TimeframeConfig dataclass."""

    def test_create_config(self):
        """Test creating timeframe config."""
        config = TimeframeConfig(
            timeframe="1h",
            interval_seconds=3600,
            max_candles=100,
            is_primary=True,
            is_filter=False,
        )

        assert config.timeframe == "1h"
        assert config.interval_seconds == 3600
        assert config.is_primary is True
        assert config.is_filter is False

    def test_default_values(self):
        """Test default values."""
        config = TimeframeConfig(
            timeframe="1h",
            interval_seconds=3600,
        )

        assert config.max_candles == 100
        assert config.is_primary is False
        assert config.is_filter is False


class TestTimeframeBuffer:
    """Tests for single TimeframeBuffer."""

    @pytest.fixture
    def buffer_1h(self):
        """Create 1-hour buffer."""
        config = TimeframeConfig(
            timeframe="1h",
            interval_seconds=3600,
            max_candles=10,
        )
        return TimeframeBuffer(config=config)

    def test_add_price_creates_candle(self, buffer_1h):
        """Test adding price creates candle."""
        buffer_1h.add_price(50000.0, volume=100.0)

        assert buffer_1h.current_candle is not None
        assert buffer_1h.current_candle["open"] == 50000.0
        assert buffer_1h.current_candle["volume"] == 100.0

    def test_add_price_updates_ohlc(self, buffer_1h):
        """Test adding prices updates OHLC correctly."""
        buffer_1h.add_price(50000.0)
        buffer_1h.add_price(51000.0)  # Higher
        buffer_1h.add_price(49000.0)  # Lower
        buffer_1h.add_price(50500.0)  # Close

        assert buffer_1h.current_candle["open"] == 50000.0
        assert buffer_1h.current_candle["high"] == 51000.0
        assert buffer_1h.current_candle["low"] == 49000.0
        assert buffer_1h.current_candle["close"] == 50500.0

    def test_add_candle_directly(self, buffer_1h):
        """Test adding candle directly."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        buffer_1h.add_candle(
            timestamp=timestamp,
            open_price=50000.0,
            high=51000.0,
            low=49000.0,
            close=50500.0,
            volume=1000.0,
        )

        assert buffer_1h.candle_count() == 1
        assert buffer_1h.candles[0]["open"] == 50000.0

    def test_add_candle_from_ms_timestamp(self, buffer_1h):
        """Test adding candle from millisecond timestamp."""
        ms_timestamp = 1704110400000  # 2024-01-01 12:00:00 UTC
        buffer_1h.add_candle(
            timestamp=ms_timestamp,
            open_price=50000.0,
            high=51000.0,
            low=49000.0,
            close=50500.0,
            volume=1000.0,
        )

        assert buffer_1h.candle_count() == 1

    def test_get_dataframe(self, buffer_1h):
        """Test getting DataFrame from buffer."""
        # Add some candles
        for i in range(3):
            buffer_1h.add_candle(
                timestamp=datetime(2024, 1, 1, i, 0, 0, tzinfo=UTC),
                open_price=50000.0 + i * 100,
                high=51000.0,
                low=49000.0,
                close=50500.0,
                volume=1000.0,
            )

        df = buffer_1h.get_dataframe()

        assert df is not None
        assert len(df) == 3
        assert "datetime" in df.columns
        assert "open" in df.columns
        assert "close" in df.columns

    def test_max_candles_limit(self, buffer_1h):
        """Test buffer respects max candles."""
        # Add more than max_candles (10)
        for i in range(15):
            buffer_1h.add_candle(
                timestamp=datetime(2024, 1, 1, i, 0, 0, tzinfo=UTC),
                open_price=50000.0,
                high=51000.0,
                low=49000.0,
                close=50500.0,
                volume=1000.0,
            )

        assert buffer_1h.candle_count() == 10


class TestMultiTimeframeBuffer:
    """Tests for MultiTimeframeBuffer."""

    @pytest.fixture
    def mtf_buffer(self):
        """Create multi-timeframe buffer."""
        configs = [
            TimeframeConfig(
                timeframe="15m",
                interval_seconds=900,
                max_candles=100,
            ),
            TimeframeConfig(
                timeframe="1h",
                interval_seconds=3600,
                max_candles=100,
                is_primary=True,
            ),
            TimeframeConfig(
                timeframe="4h",
                interval_seconds=14400,
                max_candles=100,
                is_filter=True,
            ),
        ]
        return MultiTimeframeBuffer(configs)

    def test_create_buffer(self, mtf_buffer):
        """Test creating MTF buffer."""
        assert len(mtf_buffer.timeframes) == 3
        assert "15m" in mtf_buffer.timeframes
        assert "1h" in mtf_buffer.timeframes
        assert "4h" in mtf_buffer.timeframes

    def test_primary_timeframe(self, mtf_buffer):
        """Test getting primary timeframe."""
        assert mtf_buffer.primary_timeframe == "1h"

    def test_filter_timeframe(self, mtf_buffer):
        """Test getting filter timeframe."""
        assert mtf_buffer.filter_timeframe == "4h"

    def test_add_price_updates_all_timeframes(self, mtf_buffer):
        """Test adding price updates all timeframes."""
        results = mtf_buffer.add_price("BTC/USDT", 50000.0, volume=100.0)

        assert "15m" in results
        assert "1h" in results
        assert "4h" in results

    def test_add_candle_to_specific_timeframe(self, mtf_buffer):
        """Test adding candle to specific timeframe."""
        mtf_buffer.add_candle(
            symbol="BTC/USDT",
            timeframe="1h",
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
            open_price=50000.0,
            high=51000.0,
            low=49000.0,
            close=50500.0,
            volume=1000.0,
        )

        assert mtf_buffer.candle_count("BTC/USDT", "1h") == 1
        assert mtf_buffer.candle_count("BTC/USDT", "15m") == 0
        assert mtf_buffer.candle_count("BTC/USDT", "4h") == 0

    def test_get_ohlcv_single_timeframe(self, mtf_buffer):
        """Test getting OHLCV for single timeframe."""
        # Add candles
        for i in range(5):
            mtf_buffer.add_candle(
                symbol="BTC/USDT",
                timeframe="1h",
                timestamp=datetime(2024, 1, 1, i, 0, 0, tzinfo=UTC),
                open_price=50000.0,
                high=51000.0,
                low=49000.0,
                close=50500.0,
                volume=1000.0,
            )

        df = mtf_buffer.get_ohlcv("BTC/USDT", "1h")

        assert df is not None
        assert len(df) == 5

    def test_get_all_ohlcv(self, mtf_buffer):
        """Test getting OHLCV for all timeframes."""
        # Add candles to different timeframes
        for tf in ["15m", "1h", "4h"]:
            for i in range(3):
                mtf_buffer.add_candle(
                    symbol="BTC/USDT",
                    timeframe=tf,
                    timestamp=datetime(2024, 1, 1, i, 0, 0, tzinfo=UTC),
                    open_price=50000.0,
                    high=51000.0,
                    low=49000.0,
                    close=50500.0,
                    volume=1000.0,
                )

        all_ohlcv = mtf_buffer.get_all_ohlcv("BTC/USDT")

        assert "15m" in all_ohlcv
        assert "1h" in all_ohlcv
        assert "4h" in all_ohlcv
        assert len(all_ohlcv["1h"]) == 3

    def test_has_minimum_candles(self, mtf_buffer):
        """Test checking minimum candles."""
        # Add some candles to 1h only
        for i in range(55):
            mtf_buffer.add_candle(
                symbol="BTC/USDT",
                timeframe="1h",
                timestamp=datetime(2024, 1, 1, i % 24, 0, 0, tzinfo=UTC),
                open_price=50000.0,
                high=51000.0,
                low=49000.0,
                close=50500.0,
                volume=1000.0,
            )

        result = mtf_buffer.has_minimum_candles("BTC/USDT", min_candles=50)

        assert result["1h"] is True
        assert result["15m"] is False
        assert result["4h"] is False

    def test_multiple_symbols(self, mtf_buffer):
        """Test buffer handles multiple symbols."""
        mtf_buffer.add_price("BTC/USDT", 50000.0)
        mtf_buffer.add_price("ETH/USDT", 3000.0)

        btc_df = mtf_buffer.get_ohlcv("BTC/USDT", "1h")
        eth_df = mtf_buffer.get_ohlcv("ETH/USDT", "1h")

        assert btc_df is not None
        assert eth_df is not None

    def test_clear_specific_symbol(self, mtf_buffer):
        """Test clearing specific symbol."""
        mtf_buffer.add_price("BTC/USDT", 50000.0)
        mtf_buffer.add_price("ETH/USDT", 3000.0)

        mtf_buffer.clear("BTC/USDT")

        assert mtf_buffer.get_ohlcv("BTC/USDT", "1h") is None
        # ETH should still exist
        assert mtf_buffer.get_ohlcv("ETH/USDT", "1h") is not None

    def test_clear_all(self, mtf_buffer):
        """Test clearing all symbols."""
        mtf_buffer.add_price("BTC/USDT", 50000.0)
        mtf_buffer.add_price("ETH/USDT", 3000.0)

        mtf_buffer.clear()

        assert mtf_buffer.get_ohlcv("BTC/USDT", "1h") is None
        assert mtf_buffer.get_ohlcv("ETH/USDT", "1h") is None

    def test_invalid_timeframe_raises(self, mtf_buffer):
        """Test adding to invalid timeframe raises error."""
        with pytest.raises(ValueError):
            mtf_buffer.add_candle(
                symbol="BTC/USDT",
                timeframe="5m",  # Not in config
                timestamp=datetime.now(UTC),
                open_price=50000.0,
                high=51000.0,
                low=49000.0,
                close=50500.0,
                volume=1000.0,
            )

    def test_multiple_primary_raises(self):
        """Test multiple primary timeframes raises error."""
        with pytest.raises(ValueError):
            configs = [
                TimeframeConfig(timeframe="1h", interval_seconds=3600, is_primary=True),
                TimeframeConfig(timeframe="4h", interval_seconds=14400, is_primary=True),
            ]
            MultiTimeframeBuffer(configs)

    def test_multiple_filter_raises(self):
        """Test multiple filter timeframes raises error."""
        with pytest.raises(ValueError):
            configs = [
                TimeframeConfig(timeframe="1h", interval_seconds=3600, is_filter=True),
                TimeframeConfig(timeframe="4h", interval_seconds=14400, is_filter=True),
            ]
            MultiTimeframeBuffer(configs)


class TestResampleFromBase:
    """Tests for resampling functionality."""

    @pytest.fixture
    def mtf_buffer(self):
        """Create buffer for resampling tests."""
        configs = [
            TimeframeConfig(timeframe="1m", interval_seconds=60, max_candles=200),
            TimeframeConfig(timeframe="5m", interval_seconds=300, max_candles=100),
            TimeframeConfig(timeframe="15m", interval_seconds=900, max_candles=100),
        ]
        return MultiTimeframeBuffer(configs)

    def test_resample_from_base(self, mtf_buffer):
        """Test resampling from base timeframe."""
        # Create base 1m data
        dates = pd.date_range(start="2024-01-01", periods=30, freq="1min", tz=UTC)
        base_df = pd.DataFrame(
            {
                "datetime": dates,
                "open": [50000.0 + i for i in range(30)],
                "high": [50100.0 + i for i in range(30)],
                "low": [49900.0 + i for i in range(30)],
                "close": [50050.0 + i for i in range(30)],
                "volume": [100.0] * 30,
            }
        )

        mtf_buffer.resample_from_base("BTC/USDT", base_df, base_timeframe="1m")

        # Check 5m has resampled candles (30 1m = 6 5m)
        df_5m = mtf_buffer.get_ohlcv("BTC/USDT", "5m")
        assert df_5m is not None
        assert len(df_5m) == 6

        # Check 15m has resampled candles (30 1m = 2 15m)
        df_15m = mtf_buffer.get_ohlcv("BTC/USDT", "15m")
        assert df_15m is not None
        assert len(df_15m) == 2
