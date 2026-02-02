"""Tests for signal generator."""

from datetime import UTC, datetime

import pandas as pd
import pytest

from keryxflow.oracle.brain import ActionRecommendation, MarketBias, MarketContext
from keryxflow.oracle.signals import (
    SignalGenerator,
    SignalSource,
    SignalStrength,
    SignalType,
    TradingSignal,
)
from keryxflow.oracle.technical import (
    IndicatorResult,
    TechnicalAnalysis,
    TrendDirection,
)


@pytest.fixture
def sample_ohlcv():
    """Generate sample OHLCV data for testing."""
    dates = pd.date_range(start="2024-01-01", periods=100, freq="1h")

    base_price = 50000.0
    prices = []
    for i in range(100):
        price = base_price + (i * 50) + (i % 10) * 10
        prices.append(price)

    return pd.DataFrame({
        "timestamp": dates,
        "open": prices,
        "high": [p + 100 for p in prices],
        "low": [p - 100 for p in prices],
        "close": [p + 50 for p in prices],
        "volume": [1000000 + i * 10000 for i in range(100)],
    })


@pytest.fixture
def bullish_technical():
    """Create bullish technical analysis."""
    return TechnicalAnalysis(
        symbol="BTC/USDT",
        timestamp=datetime.now(UTC),
        indicators={
            "RSI": IndicatorResult(
                name="RSI",
                value=65.0,
                signal=TrendDirection.BULLISH,
                strength=SignalStrength.MODERATE,
            ),
            "ATR": IndicatorResult(
                name="ATR",
                value={"atr": 1000, "atr_pct": 0.02, "ratio": 1.0},
                signal=TrendDirection.NEUTRAL,
                strength=SignalStrength.MODERATE,
            ),
        },
        overall_trend=TrendDirection.BULLISH,
        overall_strength=SignalStrength.STRONG,
        confidence=0.8,
        simple_summary="Market looks bullish",
        technical_summary="Trend: BULLISH",
    )


@pytest.fixture
def bearish_technical():
    """Create bearish technical analysis."""
    return TechnicalAnalysis(
        symbol="BTC/USDT",
        timestamp=datetime.now(UTC),
        indicators={
            "RSI": IndicatorResult(
                name="RSI",
                value=35.0,
                signal=TrendDirection.BEARISH,
                strength=SignalStrength.MODERATE,
            ),
            "ATR": IndicatorResult(
                name="ATR",
                value={"atr": 1000, "atr_pct": 0.02, "ratio": 1.0},
                signal=TrendDirection.NEUTRAL,
                strength=SignalStrength.MODERATE,
            ),
        },
        overall_trend=TrendDirection.BEARISH,
        overall_strength=SignalStrength.STRONG,
        confidence=0.8,
        simple_summary="Market looks bearish",
        technical_summary="Trend: BEARISH",
    )


@pytest.fixture
def neutral_technical():
    """Create neutral technical analysis."""
    return TechnicalAnalysis(
        symbol="BTC/USDT",
        timestamp=datetime.now(UTC),
        indicators={
            "RSI": IndicatorResult(
                name="RSI",
                value=50.0,
                signal=TrendDirection.NEUTRAL,
                strength=SignalStrength.WEAK,
            ),
        },
        overall_trend=TrendDirection.NEUTRAL,
        overall_strength=SignalStrength.WEAK,
        confidence=0.4,
        simple_summary="Market is neutral",
        technical_summary="Trend: NEUTRAL",
    )


@pytest.fixture
def bullish_llm():
    """Create bullish LLM context."""
    return MarketContext(
        symbol="BTC/USDT",
        timestamp=datetime.now(UTC),
        bias=MarketBias.BULLISH,
        confidence=0.75,
        recommendation=ActionRecommendation.BUY,
        reasoning="LLM says bullish",
        simple_explanation="Good time to buy",
    )


@pytest.fixture
def bearish_llm():
    """Create bearish LLM context."""
    return MarketContext(
        symbol="BTC/USDT",
        timestamp=datetime.now(UTC),
        bias=MarketBias.BEARISH,
        confidence=0.75,
        recommendation=ActionRecommendation.SELL,
        reasoning="LLM says bearish",
        simple_explanation="Consider selling",
    )


class TestTradingSignal:
    """Tests for TradingSignal."""

    def test_to_dict(self):
        """Test TradingSignal.to_dict()."""
        signal = TradingSignal(
            symbol="BTC/USDT",
            signal_type=SignalType.LONG,
            strength=SignalStrength.STRONG,
            confidence=0.8,
            source=SignalSource.HYBRID,
            timestamp=datetime.now(UTC),
            entry_price=50000.0,
            stop_loss=48000.0,
            take_profit=54000.0,
            risk_reward=2.0,
            simple_reason="Test signal",
            technical_reason="Test technical",
        )

        data = signal.to_dict()

        assert data["symbol"] == "BTC/USDT"
        assert data["signal_type"] == "long"
        assert data["strength"] == "strong"
        assert data["confidence"] == 0.8
        assert data["entry_price"] == 50000.0
        assert data["stop_loss"] == 48000.0

    def test_is_actionable_long(self):
        """Test is_actionable for LONG signal."""
        signal = TradingSignal(
            symbol="BTC/USDT",
            signal_type=SignalType.LONG,
            strength=SignalStrength.STRONG,
            confidence=0.8,
            source=SignalSource.TECHNICAL,
            timestamp=datetime.now(UTC),
        )
        assert signal.is_actionable

    def test_is_actionable_no_action(self):
        """Test is_actionable for NO_ACTION signal."""
        signal = TradingSignal(
            symbol="BTC/USDT",
            signal_type=SignalType.NO_ACTION,
            strength=SignalStrength.NONE,
            confidence=0.0,
            source=SignalSource.TECHNICAL,
            timestamp=datetime.now(UTC),
        )
        assert not signal.is_actionable

    def test_is_entry_long(self):
        """Test is_entry for LONG signal."""
        signal = TradingSignal(
            symbol="BTC/USDT",
            signal_type=SignalType.LONG,
            strength=SignalStrength.STRONG,
            confidence=0.8,
            source=SignalSource.TECHNICAL,
            timestamp=datetime.now(UTC),
        )
        assert signal.is_entry

    def test_is_entry_close(self):
        """Test is_entry for CLOSE signal."""
        signal = TradingSignal(
            symbol="BTC/USDT",
            signal_type=SignalType.CLOSE_LONG,
            strength=SignalStrength.STRONG,
            confidence=0.8,
            source=SignalSource.TECHNICAL,
            timestamp=datetime.now(UTC),
        )
        assert not signal.is_entry


class TestSignalGenerator:
    """Tests for SignalGenerator."""

    def test_technical_to_signal_bullish(self, bullish_technical):
        """Test technical to signal conversion for bullish."""
        generator = SignalGenerator()
        signal_type = generator._technical_to_signal(bullish_technical)
        assert signal_type == SignalType.LONG

    def test_technical_to_signal_bearish(self, bearish_technical):
        """Test technical to signal conversion for bearish."""
        generator = SignalGenerator()
        signal_type = generator._technical_to_signal(bearish_technical)
        assert signal_type == SignalType.SHORT

    def test_technical_to_signal_neutral(self, neutral_technical):
        """Test technical to signal conversion for neutral."""
        generator = SignalGenerator()
        signal_type = generator._technical_to_signal(neutral_technical)
        assert signal_type == SignalType.NO_ACTION

    def test_adjust_with_llm_agreement(self, bullish_llm):
        """Test LLM adjustment when LLM agrees."""
        generator = SignalGenerator()
        signal, confidence = generator._adjust_with_llm(SignalType.LONG, bullish_llm)

        assert signal == SignalType.LONG
        assert confidence > 0

    def test_adjust_with_llm_disagreement(self, bearish_llm):
        """Test LLM adjustment when LLM disagrees."""
        generator = SignalGenerator()
        signal, confidence = generator._adjust_with_llm(SignalType.LONG, bearish_llm)

        assert signal == SignalType.NO_ACTION
        assert confidence < 0.75  # Should be reduced

    def test_adjust_with_llm_strong_buy(self, bullish_llm):
        """Test LLM can upgrade weak signals."""
        generator = SignalGenerator()
        bullish_llm.recommendation = ActionRecommendation.STRONG_BUY

        signal, confidence = generator._adjust_with_llm(SignalType.NO_ACTION, bullish_llm)

        assert signal == SignalType.LONG

    def test_calculate_targets_long(self, bullish_technical):
        """Test target calculation for LONG signal."""
        generator = SignalGenerator()
        entry, stop, target = generator._calculate_targets(
            50000.0, SignalType.LONG, bullish_technical
        )

        assert entry == 50000.0
        assert stop is not None
        assert stop < entry  # Stop below entry for long
        assert target is not None
        assert target > entry  # Target above entry for long

    def test_calculate_targets_short(self, bullish_technical):
        """Test target calculation for SHORT signal."""
        generator = SignalGenerator()
        entry, stop, target = generator._calculate_targets(
            50000.0, SignalType.SHORT, bullish_technical
        )

        assert entry == 50000.0
        assert stop is not None
        assert stop > entry  # Stop above entry for short
        assert target is not None
        assert target < entry  # Target below entry for short

    def test_calculate_targets_no_action(self, bullish_technical):
        """Test target calculation for NO_ACTION signal."""
        generator = SignalGenerator()
        entry, stop, target = generator._calculate_targets(
            50000.0, SignalType.NO_ACTION, bullish_technical
        )

        assert entry is None
        assert stop is None
        assert target is None

    def test_confidence_to_strength_strong(self):
        """Test confidence to strength conversion - strong."""
        generator = SignalGenerator()
        assert generator._confidence_to_strength(0.8) == SignalStrength.STRONG

    def test_confidence_to_strength_moderate(self):
        """Test confidence to strength conversion - moderate."""
        generator = SignalGenerator()
        assert generator._confidence_to_strength(0.55) == SignalStrength.MODERATE

    def test_confidence_to_strength_weak(self):
        """Test confidence to strength conversion - weak."""
        generator = SignalGenerator()
        assert generator._confidence_to_strength(0.35) == SignalStrength.WEAK

    def test_confidence_to_strength_none(self):
        """Test confidence to strength conversion - none."""
        generator = SignalGenerator()
        assert generator._confidence_to_strength(0.1) == SignalStrength.NONE

    def test_no_action_signal(self):
        """Test no-action signal creation."""
        generator = SignalGenerator()
        signal = generator._no_action_signal("BTC/USDT", "Test reason")

        assert signal.symbol == "BTC/USDT"
        assert signal.signal_type == SignalType.NO_ACTION
        assert signal.strength == SignalStrength.NONE
        assert signal.confidence == 0.0
        assert "Test reason" in signal.simple_reason

    def test_is_significant_change_new_symbol(self):
        """Test significant change detection for new symbol."""
        generator = SignalGenerator()
        signal = TradingSignal(
            symbol="BTC/USDT",
            signal_type=SignalType.LONG,
            strength=SignalStrength.STRONG,
            confidence=0.8,
            source=SignalSource.TECHNICAL,
            timestamp=datetime.now(UTC),
        )

        assert generator._is_significant_change("BTC/USDT", signal)

    def test_is_significant_change_same_signal(self):
        """Test significant change detection for same signal."""
        generator = SignalGenerator()
        signal = TradingSignal(
            symbol="BTC/USDT",
            signal_type=SignalType.LONG,
            strength=SignalStrength.STRONG,
            confidence=0.8,
            source=SignalSource.TECHNICAL,
            timestamp=datetime.now(UTC),
        )

        generator._last_signals["BTC/USDT"] = signal

        # Same signal should not be significant
        assert not generator._is_significant_change("BTC/USDT", signal)

    def test_is_significant_change_type_changed(self):
        """Test significant change detection when signal type changes."""
        generator = SignalGenerator()
        old_signal = TradingSignal(
            symbol="BTC/USDT",
            signal_type=SignalType.LONG,
            strength=SignalStrength.STRONG,
            confidence=0.8,
            source=SignalSource.TECHNICAL,
            timestamp=datetime.now(UTC),
        )
        generator._last_signals["BTC/USDT"] = old_signal

        new_signal = TradingSignal(
            symbol="BTC/USDT",
            signal_type=SignalType.SHORT,
            strength=SignalStrength.STRONG,
            confidence=0.8,
            source=SignalSource.TECHNICAL,
            timestamp=datetime.now(UTC),
        )

        assert generator._is_significant_change("BTC/USDT", new_signal)

    def test_format_signal_simple(self):
        """Test simple signal formatting."""
        generator = SignalGenerator()
        signal = TradingSignal(
            symbol="BTC/USDT",
            signal_type=SignalType.LONG,
            strength=SignalStrength.STRONG,
            confidence=0.8,
            source=SignalSource.HYBRID,
            timestamp=datetime.now(UTC),
            entry_price=50000.0,
            stop_loss=48000.0,
            take_profit=54000.0,
            risk_reward=2.0,
            simple_reason="Good entry point",
        )

        formatted = generator.format_signal(signal, simple=True)

        assert "LONG" in formatted
        assert "BTC/USDT" in formatted
        assert "80%" in formatted
        assert "50,000" in formatted or "50000" in formatted
        assert "Good entry point" in formatted

    def test_format_signal_no_action(self):
        """Test formatting no-action signal."""
        generator = SignalGenerator()
        signal = TradingSignal(
            symbol="BTC/USDT",
            signal_type=SignalType.NO_ACTION,
            strength=SignalStrength.NONE,
            confidence=0.2,
            source=SignalSource.TECHNICAL,
            timestamp=datetime.now(UTC),
            simple_reason="No clear opportunity",
        )

        formatted = generator.format_signal(signal, simple=True)

        assert "NO_ACTION" in formatted
        assert "No clear opportunity" in formatted


class TestSignalIntegration:
    """Integration tests for signal generation."""

    def test_combine_signals_bullish(self, bullish_technical, bullish_llm):
        """Test combining bullish signals."""
        generator = SignalGenerator()
        signal = generator._combine_signals(
            symbol="BTC/USDT",
            current_price=50000.0,
            technical=bullish_technical,
            news=None,
            llm=bullish_llm,
        )

        assert signal.signal_type == SignalType.LONG
        assert signal.source == SignalSource.HYBRID
        assert signal.llm_bias == MarketBias.BULLISH

    def test_combine_signals_conflicting(self, bullish_technical, bearish_llm):
        """Test combining conflicting signals."""
        generator = SignalGenerator()
        signal = generator._combine_signals(
            symbol="BTC/USDT",
            current_price=50000.0,
            technical=bullish_technical,
            news=None,
            llm=bearish_llm,
        )

        # LLM should veto the bullish technical signal
        assert signal.signal_type == SignalType.NO_ACTION

    def test_combine_signals_technical_only(self, bullish_technical):
        """Test combining with technical only."""
        generator = SignalGenerator()
        signal = generator._combine_signals(
            symbol="BTC/USDT",
            current_price=50000.0,
            technical=bullish_technical,
            news=None,
            llm=None,
        )

        assert signal.signal_type == SignalType.LONG
        assert signal.source == SignalSource.TECHNICAL
        assert signal.llm_bias is None
