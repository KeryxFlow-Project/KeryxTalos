"""Tests for Oracle Brain (LLM integration)."""

from datetime import UTC, datetime

import pytest

from keryxflow.oracle.brain import (
    ActionRecommendation,
    MarketBias,
    MarketContext,
    OracleBrain,
)
from keryxflow.oracle.feeds import NewsDigest, NewsSentiment
from keryxflow.oracle.technical import (
    IndicatorResult,
    SignalStrength,
    TechnicalAnalysis,
    TrendDirection,
)


@pytest.fixture
def sample_technical():
    """Create sample technical analysis."""
    return TechnicalAnalysis(
        symbol="BTC/USDT",
        timestamp=datetime.now(UTC),
        indicators={
            "RSI": IndicatorResult(
                name="RSI",
                value=65.0,
                signal=TrendDirection.BULLISH,
                strength=SignalStrength.MODERATE,
                simple_explanation="RSI is bullish",
                technical_explanation="RSI(14) = 65.0",
            ),
            "MACD": IndicatorResult(
                name="MACD",
                value={"macd": 100, "signal": 80, "histogram": 20},
                signal=TrendDirection.BULLISH,
                strength=SignalStrength.MODERATE,
                simple_explanation="MACD is bullish",
                technical_explanation="MACD bullish crossover",
            ),
        },
        overall_trend=TrendDirection.BULLISH,
        overall_strength=SignalStrength.MODERATE,
        confidence=0.7,
        simple_summary="Market looks bullish",
        technical_summary="Trend: BULLISH | RSI: bullish (moderate)",
    )


@pytest.fixture
def sample_news():
    """Create sample news digest."""
    return NewsDigest(
        items=[],
        timestamp=datetime.now(UTC),
        overall_sentiment=NewsSentiment.BULLISH,
        sentiment_score=0.5,
        summary="Market sentiment is positive",
    )


class TestMarketContext:
    """Tests for MarketContext."""

    def test_to_dict(self):
        """Test MarketContext.to_dict()."""
        context = MarketContext(
            symbol="BTC/USDT",
            timestamp=datetime.now(UTC),
            bias=MarketBias.BULLISH,
            confidence=0.75,
            recommendation=ActionRecommendation.BUY,
            reasoning="Technical indicators are bullish",
            key_bullish_factors=["RSI above 50", "MACD positive"],
            key_bearish_factors=[],
            risks=["Volatility is high"],
            simple_explanation="Market looks good for buying",
        )

        data = context.to_dict()

        assert data["symbol"] == "BTC/USDT"
        assert data["bias"] == "bullish"
        assert data["confidence"] == 0.75
        assert data["recommendation"] == "buy"
        assert "RSI above 50" in data["key_bullish_factors"]


class TestOracleBrain:
    """Tests for OracleBrain."""

    def test_build_prompt_with_technical(self, sample_technical):
        """Test prompt building with technical analysis."""
        brain = OracleBrain()
        prompt = brain._build_prompt("BTC/USDT", sample_technical, None)

        assert "BTC/USDT" in prompt
        assert "Technical Analysis" in prompt
        assert "bullish" in prompt.lower()
        assert "RSI" in prompt

    def test_build_prompt_with_news(self, sample_technical, sample_news):
        """Test prompt building with news."""
        brain = OracleBrain()
        prompt = brain._build_prompt("BTC/USDT", sample_technical, sample_news)

        assert "News Context" in prompt
        assert "bullish" in prompt.lower()

    def test_build_prompt_no_data(self):
        """Test prompt building with no data."""
        brain = OracleBrain()
        prompt = brain._build_prompt("BTC/USDT", None, None)

        assert "BTC/USDT" in prompt
        assert "JSON" in prompt

    def test_parse_response_valid_json(self):
        """Test parsing valid JSON response."""
        brain = OracleBrain()

        valid_response = """
        {
            "bias": "bullish",
            "confidence": 0.8,
            "recommendation": "buy",
            "reasoning": "Strong technical signals",
            "bullish_factors": ["RSI above 50"],
            "bearish_factors": [],
            "risks": ["High volatility"],
            "simple_explanation": "Good time to buy"
        }
        """

        context = brain._parse_response("BTC/USDT", valid_response)

        assert context.bias == MarketBias.BULLISH
        assert context.confidence == 0.8
        assert context.recommendation == ActionRecommendation.BUY
        assert "RSI above 50" in context.key_bullish_factors

    def test_parse_response_with_markdown(self):
        """Test parsing response wrapped in markdown code blocks."""
        brain = OracleBrain()

        markdown_response = """```json
        {
            "bias": "bearish",
            "confidence": 0.6,
            "recommendation": "sell",
            "reasoning": "Weak momentum",
            "bullish_factors": [],
            "bearish_factors": ["RSI dropping"],
            "risks": [],
            "simple_explanation": "Consider selling"
        }
        ```"""

        context = brain._parse_response("BTC/USDT", markdown_response)

        assert context.bias == MarketBias.BEARISH
        assert context.recommendation == ActionRecommendation.SELL

    def test_parse_response_invalid_json(self):
        """Test parsing invalid JSON returns fallback context."""
        brain = OracleBrain()

        invalid_response = "This is not valid JSON at all"

        context = brain._parse_response("BTC/USDT", invalid_response)

        assert context.bias == MarketBias.UNCERTAIN
        assert context.recommendation == ActionRecommendation.WAIT
        assert context.confidence == 0.3

    def test_create_fallback_context_bullish(self, sample_technical, sample_news):
        """Test fallback context creation for bullish signals."""
        brain = OracleBrain()
        context = brain._create_fallback_context("BTC/USDT", sample_technical, sample_news)

        assert context.symbol == "BTC/USDT"
        assert context.bias == MarketBias.BULLISH
        assert len(context.key_bullish_factors) > 0

    def test_create_fallback_context_no_data(self):
        """Test fallback context with no data."""
        brain = OracleBrain()
        context = brain._create_fallback_context("BTC/USDT", None, None)

        assert context.symbol == "BTC/USDT"
        assert context.bias == MarketBias.NEUTRAL
        assert context.confidence == 0.5

    def test_format_for_display_simple(self):
        """Test simple display formatting."""
        brain = OracleBrain()
        context = MarketContext(
            symbol="BTC/USDT",
            timestamp=datetime.now(UTC),
            bias=MarketBias.BULLISH,
            confidence=0.8,
            recommendation=ActionRecommendation.BUY,
            reasoning="Test reasoning",
            simple_explanation="Good time to buy",
        )

        formatted = brain.format_for_display(context, simple=True)

        assert "Bullish" in formatted
        assert "80%" in formatted
        assert "Buy" in formatted
        assert "Good time to buy" in formatted

    def test_format_for_display_technical(self):
        """Test technical display formatting."""
        brain = OracleBrain()
        context = MarketContext(
            symbol="BTC/USDT",
            timestamp=datetime.now(UTC),
            bias=MarketBias.BEARISH,
            confidence=0.6,
            recommendation=ActionRecommendation.SELL,
            reasoning="Technical weakness",
            key_bullish_factors=[],
            key_bearish_factors=["RSI declining"],
            risks=["Volatility risk"],
        )

        formatted = brain.format_for_display(context, simple=False)

        assert "Market Context" in formatted
        assert "bearish" in formatted
        assert "RSI declining" in formatted
        assert "Volatility risk" in formatted


class TestMarketBiasMapping:
    """Tests for market bias mapping."""

    def test_all_biases_mappable(self):
        """Test that all bias strings map correctly."""
        brain = OracleBrain()

        test_cases = [
            (
                '{"bias": "strongly_bullish", "confidence": 0.9, "recommendation": "strong_buy", "reasoning": "", "bullish_factors": [], "bearish_factors": [], "risks": [], "simple_explanation": ""}',
                MarketBias.STRONGLY_BULLISH,
            ),
            (
                '{"bias": "bullish", "confidence": 0.7, "recommendation": "buy", "reasoning": "", "bullish_factors": [], "bearish_factors": [], "risks": [], "simple_explanation": ""}',
                MarketBias.BULLISH,
            ),
            (
                '{"bias": "neutral", "confidence": 0.5, "recommendation": "hold", "reasoning": "", "bullish_factors": [], "bearish_factors": [], "risks": [], "simple_explanation": ""}',
                MarketBias.NEUTRAL,
            ),
            (
                '{"bias": "bearish", "confidence": 0.7, "recommendation": "sell", "reasoning": "", "bullish_factors": [], "bearish_factors": [], "risks": [], "simple_explanation": ""}',
                MarketBias.BEARISH,
            ),
            (
                '{"bias": "strongly_bearish", "confidence": 0.9, "recommendation": "strong_sell", "reasoning": "", "bullish_factors": [], "bearish_factors": [], "risks": [], "simple_explanation": ""}',
                MarketBias.STRONGLY_BEARISH,
            ),
        ]

        for response, expected_bias in test_cases:
            context = brain._parse_response("BTC/USDT", response)
            assert context.bias == expected_bias, f"Expected {expected_bias}, got {context.bias}"


class TestRecommendationMapping:
    """Tests for recommendation mapping."""

    def test_all_recommendations_mappable(self):
        """Test that all recommendation strings map correctly."""
        brain = OracleBrain()

        test_cases = [
            ("strong_buy", ActionRecommendation.STRONG_BUY),
            ("buy", ActionRecommendation.BUY),
            ("hold", ActionRecommendation.HOLD),
            ("sell", ActionRecommendation.SELL),
            ("strong_sell", ActionRecommendation.STRONG_SELL),
            ("wait", ActionRecommendation.WAIT),
        ]

        for rec_str, expected_rec in test_cases:
            response = f'{{"bias": "neutral", "confidence": 0.5, "recommendation": "{rec_str}", "reasoning": "", "bullish_factors": [], "bearish_factors": [], "risks": [], "simple_explanation": ""}}'
            context = brain._parse_response("BTC/USDT", response)
            assert context.recommendation == expected_rec
