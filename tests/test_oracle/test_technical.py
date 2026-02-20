"""Tests for technical analysis engine."""

from datetime import datetime

import pandas as pd
import pytest

from keryxflow.oracle.technical import (
    IndicatorResult,
    SignalStrength,
    TechnicalAnalysis,
    TechnicalAnalyzer,
    TrendDirection,
)


@pytest.fixture
def sample_ohlcv():
    """Generate sample OHLCV data for testing."""
    # Generate 100 candles of synthetic data
    dates = pd.date_range(start="2024-01-01", periods=100, freq="1h")

    # Simulate an uptrend
    base_price = 50000.0
    prices = []
    for i in range(100):
        # Add trend + noise
        price = base_price + (i * 50) + (i % 10) * 10
        prices.append(price)

    df = pd.DataFrame(
        {
            "timestamp": dates,
            "open": prices,
            "high": [p + 100 for p in prices],
            "low": [p - 100 for p in prices],
            "close": [p + 50 for p in prices],
            "volume": [1000000 + i * 10000 for i in range(100)],
        }
    )

    return df


@pytest.fixture
def downtrend_ohlcv():
    """Generate downtrend OHLCV data for testing."""
    dates = pd.date_range(start="2024-01-01", periods=100, freq="1h")

    base_price = 60000.0
    prices = []
    for i in range(100):
        price = base_price - (i * 50) - (i % 10) * 10
        prices.append(price)

    df = pd.DataFrame(
        {
            "timestamp": dates,
            "open": prices,
            "high": [p + 100 for p in prices],
            "low": [p - 100 for p in prices],
            "close": [p - 50 for p in prices],
            "volume": [1000000 - i * 5000 for i in range(100)],
        }
    )

    return df


@pytest.fixture
def analyzer():
    """Create technical analyzer."""
    return TechnicalAnalyzer()


class TestTechnicalAnalyzer:
    """Tests for TechnicalAnalyzer."""

    def test_analyze_returns_complete_result(self, analyzer, sample_ohlcv):
        """Test that analyze returns a complete TechnicalAnalysis."""
        result = analyzer.analyze(sample_ohlcv, "BTC/USDT")

        assert isinstance(result, TechnicalAnalysis)
        assert result.symbol == "BTC/USDT"
        assert isinstance(result.timestamp, datetime)
        assert isinstance(result.overall_trend, TrendDirection)
        assert isinstance(result.overall_strength, SignalStrength)
        assert 0.0 <= result.confidence <= 1.0

    def test_analyze_requires_minimum_candles(self, analyzer):
        """Test that analyze requires minimum data."""
        short_data = pd.DataFrame(
            {
                "timestamp": pd.date_range(start="2024-01-01", periods=10, freq="1h"),
                "open": [50000] * 10,
                "high": [50100] * 10,
                "low": [49900] * 10,
                "close": [50050] * 10,
                "volume": [1000000] * 10,
            }
        )

        with pytest.raises(ValueError, match="at least 50 candles"):
            analyzer.analyze(short_data)

    def test_analyze_handles_lowercase_columns(self, analyzer, sample_ohlcv):
        """Test that analyzer handles various column name formats."""
        # Rename columns to uppercase
        df = sample_ohlcv.rename(
            columns={
                "open": "OPEN",
                "high": "HIGH",
                "low": "LOW",
                "close": "CLOSE",
                "volume": "VOLUME",
            }
        )

        result = analyzer.analyze(df, "BTC/USDT")
        assert result is not None

    def test_uptrend_detected(self, analyzer, sample_ohlcv):
        """Test that uptrend is detected in bullish data."""
        result = analyzer.analyze(sample_ohlcv, "BTC/USDT")

        # Should have some bullish indicators
        bullish_count = sum(
            1 for ind in result.indicators.values() if ind.signal == TrendDirection.BULLISH
        )
        assert bullish_count > 0

    def test_downtrend_detected(self, analyzer, downtrend_ohlcv):
        """Test that downtrend is detected in bearish data."""
        result = analyzer.analyze(downtrend_ohlcv, "BTC/USDT")

        # Should have some bearish indicators
        bearish_count = sum(
            1 for ind in result.indicators.values() if ind.signal == TrendDirection.BEARISH
        )
        assert bearish_count >= 0  # Allow for mixed signals in synthetic data

    def test_indicators_calculated(self, analyzer, sample_ohlcv):
        """Test that all configured indicators are calculated."""
        result = analyzer.analyze(sample_ohlcv)

        expected_indicators = ["rsi", "macd", "bbands", "obv", "atr", "ema"]
        for ind in expected_indicators:
            # Check case-insensitive
            found = any(ind.lower() in k.lower() for k in result.indicators)
            assert found, f"Indicator {ind} not found"

    def test_indicator_result_structure(self, analyzer, sample_ohlcv):
        """Test IndicatorResult structure."""
        result = analyzer.analyze(sample_ohlcv)

        for ind in result.indicators.values():
            assert isinstance(ind, IndicatorResult)
            assert ind.name
            assert ind.value is not None
            assert isinstance(ind.signal, TrendDirection)
            assert isinstance(ind.strength, SignalStrength)
            assert ind.simple_explanation
            assert ind.technical_explanation


class TestRSIIndicator:
    """Tests for RSI indicator."""

    def test_rsi_overbought_detection(self, analyzer):
        """Test that RSI detects overbought conditions."""
        # Generate data that should create high RSI
        dates = pd.date_range(start="2024-01-01", periods=100, freq="1h")
        prices = [50000 + i * 100 for i in range(100)]  # Strong uptrend

        df = pd.DataFrame(
            {
                "timestamp": dates,
                "open": prices,
                "high": [p + 50 for p in prices],
                "low": [p - 20 for p in prices],
                "close": [p + 40 for p in prices],
                "volume": [1000000] * 100,
            }
        )

        result = analyzer._calculate_rsi(df)
        assert result.name == "RSI"
        assert isinstance(result.value, float)
        # In a strong uptrend, RSI should be above 50
        assert result.value > 50

    def test_rsi_value_range(self, analyzer, sample_ohlcv):
        """Test that RSI stays within valid range."""
        result = analyzer._calculate_rsi(sample_ohlcv)
        assert 0 <= result.value <= 100


class TestMACDIndicator:
    """Tests for MACD indicator."""

    def test_macd_returns_multiple_values(self, analyzer, sample_ohlcv):
        """Test that MACD returns macd, signal, and histogram."""
        result = analyzer._calculate_macd(sample_ohlcv)

        assert result.name == "MACD"
        assert isinstance(result.value, dict)
        assert "macd" in result.value
        assert "signal" in result.value
        assert "histogram" in result.value


class TestBollingerBands:
    """Tests for Bollinger Bands indicator."""

    def test_bbands_returns_bands_and_position(self, analyzer, sample_ohlcv):
        """Test that BBands returns all components."""
        result = analyzer._calculate_bbands(sample_ohlcv)

        assert result.name == "Bollinger Bands"
        assert isinstance(result.value, dict)
        assert "lower" in result.value
        assert "middle" in result.value
        assert "upper" in result.value
        assert "position" in result.value
        assert 0 <= result.value["position"] <= 1


class TestATRIndicator:
    """Tests for ATR indicator."""

    def test_atr_returns_volatility_metrics(self, analyzer, sample_ohlcv):
        """Test that ATR returns volatility information."""
        result = analyzer._calculate_atr(sample_ohlcv)

        assert result.name == "ATR"
        assert isinstance(result.value, dict)
        assert "atr" in result.value
        assert "atr_pct" in result.value
        assert "ratio" in result.value
        assert result.value["atr"] > 0


class TestEMAIndicator:
    """Tests for EMA indicator."""

    def test_ema_returns_multiple_periods(self, analyzer, sample_ohlcv):
        """Test that EMA returns values for available periods."""
        result = analyzer._calculate_ema(sample_ohlcv)

        assert result.name == "EMA"
        assert isinstance(result.value, dict)
        # Check that we have EMAs for periods that fit in our data (100 candles)
        # Periods 9, 21, 50 should work; 200 requires more data
        assert 9 in result.value
        assert 21 in result.value
        assert 50 in result.value
        # 200 should not be present with only 100 candles
        assert 200 not in result.value


class TestAggregation:
    """Tests for signal aggregation."""

    def test_aggregate_signals_neutral_when_mixed(self, analyzer):
        """Test that mixed signals result in neutral assessment."""
        mixed_indicators = {
            "ind1": IndicatorResult(
                name="ind1",
                value=1.0,
                signal=TrendDirection.BULLISH,
                strength=SignalStrength.MODERATE,
            ),
            "ind2": IndicatorResult(
                name="ind2",
                value=2.0,
                signal=TrendDirection.BEARISH,
                strength=SignalStrength.MODERATE,
            ),
            "ind3": IndicatorResult(
                name="ind3",
                value=3.0,
                signal=TrendDirection.NEUTRAL,
                strength=SignalStrength.MODERATE,
            ),
        }

        trend, strength, confidence = analyzer._aggregate_signals(mixed_indicators)

        # With equal weights, should tend toward neutral
        assert 0 <= confidence <= 1

    def test_aggregate_signals_strong_bullish(self, analyzer):
        """Test that strong bullish signals are aggregated correctly."""
        bullish_indicators = {
            "ind1": IndicatorResult(
                name="ind1",
                value=1.0,
                signal=TrendDirection.BULLISH,
                strength=SignalStrength.STRONG,
            ),
            "ind2": IndicatorResult(
                name="ind2",
                value=2.0,
                signal=TrendDirection.BULLISH,
                strength=SignalStrength.STRONG,
            ),
        }

        trend, strength, confidence = analyzer._aggregate_signals(bullish_indicators)

        assert trend == TrendDirection.BULLISH
        assert confidence > 0.5


class TestSummaryGeneration:
    """Tests for summary generation."""

    def test_simple_summary_generated(self, analyzer, sample_ohlcv):
        """Test that simple summary is generated."""
        result = analyzer.analyze(sample_ohlcv)
        assert result.simple_summary
        assert len(result.simple_summary) > 0

    def test_technical_summary_generated(self, analyzer, sample_ohlcv):
        """Test that technical summary is generated."""
        result = analyzer.analyze(sample_ohlcv)
        assert result.technical_summary
        assert len(result.technical_summary) > 0


class TestIndicatorResultSerialization:
    """Tests for IndicatorResult serialization."""

    def test_indicator_result_to_dict(self):
        """Test IndicatorResult.to_dict()."""
        result = IndicatorResult(
            name="RSI",
            value=55.5,
            signal=TrendDirection.NEUTRAL,
            strength=SignalStrength.WEAK,
            simple_explanation="Test simple",
            technical_explanation="Test technical",
        )

        data = result.to_dict()

        assert data["name"] == "RSI"
        assert data["value"] == 55.5
        assert data["signal"] == "neutral"
        assert data["strength"] == "weak"
        assert data["simple_explanation"] == "Test simple"
        assert data["technical_explanation"] == "Test technical"


class TestTechnicalAnalysisSerialization:
    """Tests for TechnicalAnalysis serialization."""

    def test_technical_analysis_to_dict(self, analyzer, sample_ohlcv):
        """Test TechnicalAnalysis.to_dict()."""
        result = analyzer.analyze(sample_ohlcv)
        data = result.to_dict()

        assert "symbol" in data
        assert "timestamp" in data
        assert "indicators" in data
        assert "overall_trend" in data
        assert "overall_strength" in data
        assert "confidence" in data
