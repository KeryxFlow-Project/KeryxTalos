"""Tests for Multi-Timeframe Analyzer."""

from datetime import UTC, datetime

import pandas as pd
import pytest

from keryxflow.oracle.mtf_analyzer import (
    MTFAnalyzer,
    MultiTimeframeAnalysis,
    apply_trend_filter,
)
from keryxflow.oracle.signals import SignalType
from keryxflow.oracle.technical import (
    TrendDirection,
)


@pytest.fixture
def sample_ohlcv_bullish():
    """Generate bullish OHLCV data (uptrending)."""
    dates = pd.date_range(start="2024-01-01", periods=100, freq="1h", tz=UTC)
    base_price = 50000.0

    # Create uptrending data
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
    """Generate bearish OHLCV data (downtrending)."""
    dates = pd.date_range(start="2024-01-01", periods=100, freq="1h", tz=UTC)
    base_price = 55000.0

    # Create downtrending data
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
    # Create sideways data with small oscillations
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


class TestMTFAnalyzer:
    """Tests for MTFAnalyzer class."""

    @pytest.fixture
    def analyzer(self):
        """Create MTF analyzer."""
        return MTFAnalyzer(
            primary_timeframe="1h",
            filter_timeframe="4h",
            min_candles=50,
        )

    def test_create_analyzer(self, analyzer):
        """Test creating MTF analyzer."""
        assert analyzer._primary_tf == "1h"
        assert analyzer._filter_tf == "4h"
        assert analyzer._min_candles == 50

    def test_analyze_with_single_timeframe(self, analyzer, sample_ohlcv_bullish):
        """Test analysis with single timeframe data."""
        ohlcv_data = {"1h": sample_ohlcv_bullish}

        result = analyzer.analyze(ohlcv_data, "BTC/USDT")

        assert isinstance(result, MultiTimeframeAnalysis)
        assert result.symbol == "BTC/USDT"
        assert "1h" in result.analyses
        assert result.primary_analysis is not None

    def test_analyze_with_multiple_timeframes(self, analyzer, sample_ohlcv_bullish):
        """Test analysis with multiple timeframes."""
        ohlcv_data = {
            "1h": sample_ohlcv_bullish,
            "4h": sample_ohlcv_bullish.iloc[::4].reset_index(drop=True),
        }

        result = analyzer.analyze(ohlcv_data, "BTC/USDT")

        assert "1h" in result.analyses
        # 4h data has 25 candles (100/4), less than min_candles=50, so skipped
        # This is expected behavior

    def test_filter_trend_bullish(self, analyzer, sample_ohlcv_bullish):
        """Test filter trend detection for bullish data."""
        ohlcv_data = {"1h": sample_ohlcv_bullish}

        result = analyzer.analyze(ohlcv_data, "BTC/USDT")

        # Bullish data should have bullish filter trend
        assert result.filter_trend in [
            TrendDirection.BULLISH,
            TrendDirection.NEUTRAL,
        ]

    def test_filter_trend_bearish(self, analyzer, sample_ohlcv_bearish):
        """Test filter trend detection for bearish data."""
        ohlcv_data = {"1h": sample_ohlcv_bearish}

        result = analyzer.analyze(ohlcv_data, "BTC/USDT")

        # Bearish data should have bearish filter trend
        assert result.filter_trend in [
            TrendDirection.BEARISH,
            TrendDirection.NEUTRAL,
        ]

    def test_alignment_check_same_direction(self, analyzer, sample_ohlcv_bullish):
        """Test alignment when timeframes agree."""
        ohlcv_data = {"1h": sample_ohlcv_bullish}

        result = analyzer.analyze(ohlcv_data, "BTC/USDT")

        # Single timeframe is always aligned
        assert result.aligned is True

    def test_simple_summary_generated(self, analyzer, sample_ohlcv_bullish):
        """Test simple summary is generated."""
        ohlcv_data = {"1h": sample_ohlcv_bullish}

        result = analyzer.analyze(ohlcv_data, "BTC/USDT")

        assert result.simple_summary != ""
        assert isinstance(result.simple_summary, str)

    def test_technical_summary_generated(self, analyzer, sample_ohlcv_bullish):
        """Test technical summary is generated."""
        ohlcv_data = {"1h": sample_ohlcv_bullish}

        result = analyzer.analyze(ohlcv_data, "BTC/USDT")

        assert result.technical_summary != ""
        assert "Filter:" in result.technical_summary

    def test_to_dict(self, analyzer, sample_ohlcv_bullish):
        """Test converting result to dict."""
        ohlcv_data = {"1h": sample_ohlcv_bullish}

        result = analyzer.analyze(ohlcv_data, "BTC/USDT")
        result_dict = result.to_dict()

        assert "symbol" in result_dict
        assert "timestamp" in result_dict
        assert "filter_trend" in result_dict
        assert "aligned" in result_dict
        assert "analyses" in result_dict

    def test_skips_insufficient_data(self, analyzer):
        """Test skipping timeframes with insufficient data."""
        # Create small dataset (< min_candles)
        dates = pd.date_range(start="2024-01-01", periods=30, freq="1h", tz=UTC)
        small_df = pd.DataFrame(
            {
                "datetime": dates,
                "open": [50000.0] * 30,
                "high": [51000.0] * 30,
                "low": [49000.0] * 30,
                "close": [50500.0] * 30,
                "volume": [1000.0] * 30,
            }
        )

        ohlcv_data = {"1h": small_df}
        result = analyzer.analyze(ohlcv_data, "BTC/USDT")

        # Should have no analyses due to insufficient data
        assert len(result.analyses) == 0
        assert result.filter_trend == TrendDirection.NEUTRAL


class TestApplyTrendFilter:
    """Tests for apply_trend_filter function."""

    def test_bullish_filter_allows_long(self):
        """Test bullish filter allows long signals."""
        result = apply_trend_filter(
            primary_signal=SignalType.LONG,
            filter_trend=TrendDirection.BULLISH,
            filter_confidence=0.7,
        )

        assert result == SignalType.LONG

    def test_bullish_filter_blocks_short(self):
        """Test bullish filter blocks short signals."""
        result = apply_trend_filter(
            primary_signal=SignalType.SHORT,
            filter_trend=TrendDirection.BULLISH,
            filter_confidence=0.7,
        )

        assert result == SignalType.NO_ACTION

    def test_bearish_filter_allows_short(self):
        """Test bearish filter allows short signals."""
        result = apply_trend_filter(
            primary_signal=SignalType.SHORT,
            filter_trend=TrendDirection.BEARISH,
            filter_confidence=0.7,
        )

        assert result == SignalType.SHORT

    def test_bearish_filter_blocks_long(self):
        """Test bearish filter blocks long signals."""
        result = apply_trend_filter(
            primary_signal=SignalType.LONG,
            filter_trend=TrendDirection.BEARISH,
            filter_confidence=0.7,
        )

        assert result == SignalType.NO_ACTION

    def test_neutral_filter_allows_any(self):
        """Test neutral filter allows any signal."""
        result_long = apply_trend_filter(
            primary_signal=SignalType.LONG,
            filter_trend=TrendDirection.NEUTRAL,
            filter_confidence=0.7,
        )
        result_short = apply_trend_filter(
            primary_signal=SignalType.SHORT,
            filter_trend=TrendDirection.NEUTRAL,
            filter_confidence=0.7,
        )

        assert result_long == SignalType.LONG
        assert result_short == SignalType.SHORT

    def test_low_confidence_allows_any(self):
        """Test low confidence bypasses filter."""
        result = apply_trend_filter(
            primary_signal=SignalType.SHORT,
            filter_trend=TrendDirection.BULLISH,
            filter_confidence=0.3,  # Below min_confidence
            min_confidence=0.5,
        )

        # Low confidence should allow any signal
        assert result == SignalType.SHORT

    def test_no_action_passes_through(self):
        """Test NO_ACTION signal passes through unchanged."""
        result = apply_trend_filter(
            primary_signal=SignalType.NO_ACTION,
            filter_trend=TrendDirection.BULLISH,
            filter_confidence=0.7,
        )

        assert result == SignalType.NO_ACTION

    def test_close_signals_pass_through(self):
        """Test close signals pass through unchanged."""
        result_close_long = apply_trend_filter(
            primary_signal=SignalType.CLOSE_LONG,
            filter_trend=TrendDirection.BEARISH,
            filter_confidence=0.7,
        )
        result_close_short = apply_trend_filter(
            primary_signal=SignalType.CLOSE_SHORT,
            filter_trend=TrendDirection.BULLISH,
            filter_confidence=0.7,
        )

        assert result_close_long == SignalType.CLOSE_LONG
        assert result_close_short == SignalType.CLOSE_SHORT

    def test_custom_min_confidence(self):
        """Test custom minimum confidence threshold."""
        # With confidence 0.6 and min 0.7, filter should not apply
        result = apply_trend_filter(
            primary_signal=SignalType.SHORT,
            filter_trend=TrendDirection.BULLISH,
            filter_confidence=0.6,
            min_confidence=0.7,
        )

        assert result == SignalType.SHORT


class TestMultiTimeframeAnalysisDataclass:
    """Tests for MultiTimeframeAnalysis dataclass."""

    def test_create_analysis(self):
        """Test creating analysis result."""
        analysis = MultiTimeframeAnalysis(
            symbol="BTC/USDT",
            timestamp=datetime.now(UTC),
            analyses={},
            filter_trend=TrendDirection.BULLISH,
            filter_confidence=0.75,
            aligned=True,
        )

        assert analysis.symbol == "BTC/USDT"
        assert analysis.filter_trend == TrendDirection.BULLISH
        assert analysis.filter_confidence == 0.75
        assert analysis.aligned is True

    def test_optional_fields(self):
        """Test optional fields have defaults."""
        analysis = MultiTimeframeAnalysis(
            symbol="BTC/USDT",
            timestamp=datetime.now(UTC),
            analyses={},
            filter_trend=TrendDirection.NEUTRAL,
            filter_confidence=0.5,
            aligned=True,
        )

        assert analysis.primary_timeframe is None
        assert analysis.primary_analysis is None
        assert analysis.filter_timeframe is None
        assert analysis.filter_analysis is None
        assert analysis.simple_summary == ""
        assert analysis.technical_summary == ""

    def test_to_dict_includes_all_fields(self):
        """Test to_dict includes all relevant fields."""
        analysis = MultiTimeframeAnalysis(
            symbol="BTC/USDT",
            timestamp=datetime.now(UTC),
            analyses={},
            filter_trend=TrendDirection.BULLISH,
            filter_confidence=0.75,
            aligned=True,
            primary_timeframe="1h",
            filter_timeframe="4h",
            simple_summary="Test summary",
            technical_summary="Test technical",
        )

        result = analysis.to_dict()

        assert result["symbol"] == "BTC/USDT"
        assert result["filter_trend"] == "bullish"
        assert result["filter_confidence"] == 0.75
        assert result["aligned"] is True
        assert result["primary_timeframe"] == "1h"
        assert result["filter_timeframe"] == "4h"
        assert "timestamp" in result
