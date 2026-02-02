"""LLM Brain using Claude for market context analysis."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from keryxflow.config import get_settings
from keryxflow.core.events import EventBus, get_event_bus
from keryxflow.core.logging import get_logger
from keryxflow.oracle.feeds import NewsDigest, NewsSentiment
from keryxflow.oracle.technical import TechnicalAnalysis, TrendDirection

if TYPE_CHECKING:
    from keryxflow.memory.manager import MemoryContext

logger = get_logger(__name__)


class MarketBias(str, Enum):
    """Market bias from LLM analysis."""

    STRONGLY_BULLISH = "strongly_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    STRONGLY_BEARISH = "strongly_bearish"
    UNCERTAIN = "uncertain"


class ActionRecommendation(str, Enum):
    """Recommended action from LLM."""

    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"
    WAIT = "wait"


@dataclass
class MarketContext:
    """Complete market context from LLM analysis."""

    symbol: str
    timestamp: datetime
    bias: MarketBias
    confidence: float  # 0.0 to 1.0
    recommendation: ActionRecommendation
    reasoning: str

    # Key factors
    key_bullish_factors: list[str] = field(default_factory=list)
    key_bearish_factors: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)

    # For beginners
    simple_explanation: str = ""

    # Raw LLM response (for debugging)
    raw_response: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "bias": self.bias.value,
            "confidence": self.confidence,
            "recommendation": self.recommendation.value,
            "reasoning": self.reasoning,
            "key_bullish_factors": self.key_bullish_factors,
            "key_bearish_factors": self.key_bearish_factors,
            "risks": self.risks,
            "simple_explanation": self.simple_explanation,
        }


class OracleBrain:
    """
    LLM-powered market analysis brain.

    Uses Claude to analyze technical indicators and news context
    to provide trading insights.
    """

    SYSTEM_PROMPT = """You are a cryptocurrency market analyst assistant for a trading bot.
Your role is to analyze technical indicators and news to provide clear, actionable insights.

Guidelines:
1. Be objective and data-driven in your analysis
2. Always acknowledge uncertainty and risks
3. Never guarantee profits or specific outcomes
4. Consider both bullish and bearish scenarios
5. Prioritize capital preservation
6. Provide clear, concise reasoning

Your response should be in this exact JSON format:
{
    "bias": "bullish|bearish|neutral|uncertain",
    "confidence": 0.0-1.0,
    "recommendation": "strong_buy|buy|hold|sell|strong_sell|wait",
    "reasoning": "Brief technical reasoning",
    "bullish_factors": ["factor1", "factor2"],
    "bearish_factors": ["factor1", "factor2"],
    "risks": ["risk1", "risk2"],
    "simple_explanation": "Beginner-friendly 1-2 sentence summary"
}

Always respond with valid JSON only, no additional text."""

    def __init__(self, event_bus: EventBus | None = None):
        """Initialize the Oracle Brain."""
        self.settings = get_settings()
        self.event_bus = event_bus or get_event_bus()
        self._llm = None
        self._chain = None
        self._last_analysis: MarketContext | None = None
        self._last_analysis_time: datetime | None = None

    def _init_llm(self) -> None:
        """Lazily initialize the LLM."""
        if self._llm is not None:
            return

        api_key = self.settings.anthropic_api_key.get_secret_value()
        if not api_key:
            raise ValueError("Anthropic API key not configured")

        try:
            from langchain_anthropic import ChatAnthropic
            from langchain_core.prompts import ChatPromptTemplate

            self._llm = ChatAnthropic(
                model=self.settings.oracle.llm_model,
                api_key=api_key,
                max_tokens=self.settings.oracle.max_tokens,
                temperature=0.3,  # Lower temperature for more consistent analysis
            )

            prompt = ChatPromptTemplate.from_messages([
                ("system", self.SYSTEM_PROMPT),
                ("human", "{input}"),
            ])

            self._chain = prompt | self._llm

            logger.info("llm_initialized", model=self.settings.oracle.llm_model)

        except ImportError as e:
            raise ImportError(
                "langchain-anthropic is required. Install with: pip install langchain-anthropic"
            ) from e

    async def analyze(
        self,
        symbol: str,
        technical: TechnicalAnalysis | None = None,
        news: NewsDigest | None = None,
        memory_context: "MemoryContext | None" = None,
    ) -> MarketContext:
        """
        Analyze market context using LLM.

        Args:
            symbol: Trading pair symbol
            technical: Technical analysis results
            news: News digest
            memory_context: Memory context from past trades and rules

        Returns:
            MarketContext with LLM analysis
        """
        if not self.settings.oracle.llm_enabled:
            return self._create_fallback_context(symbol, technical, news)

        try:
            self._init_llm()
        except ValueError as e:
            logger.warning("llm_init_failed", error=str(e))
            return self._create_fallback_context(symbol, technical, news)

        # Build analysis prompt
        prompt = self._build_prompt(symbol, technical, news, memory_context)

        try:
            # Call LLM
            if self._chain is None:
                raise ValueError("LLM chain not initialized")

            response = await self._chain.ainvoke({"input": prompt})
            raw_response = response.content if hasattr(response, "content") else str(response)

            # Parse response
            context = self._parse_response(symbol, raw_response)

            # Cache result
            self._last_analysis = context
            self._last_analysis_time = datetime.now(UTC)

            # Emit event
            await self.event_bus.publish("oracle.analysis_complete", context.to_dict())

            logger.info(
                "llm_analysis_complete",
                symbol=symbol,
                bias=context.bias.value,
                confidence=context.confidence,
                recommendation=context.recommendation.value,
            )

            return context

        except Exception as e:
            logger.error("llm_analysis_failed", error=str(e))
            return self._create_fallback_context(symbol, technical, news)

    def _build_prompt(
        self,
        symbol: str,
        technical: TechnicalAnalysis | None,
        news: NewsDigest | None,
        memory_context: "MemoryContext | None" = None,
    ) -> str:
        """Build the analysis prompt for the LLM."""
        parts = [f"Analyze {symbol} with the following data:\n"]

        if technical:
            parts.append("## Technical Analysis")
            parts.append(f"Overall Trend: {technical.overall_trend.value}")
            parts.append(f"Strength: {technical.overall_strength.value}")
            parts.append(f"Confidence: {technical.confidence:.0%}")
            parts.append("")

            for name, indicator in technical.indicators.items():
                signal = indicator.signal.value
                strength = indicator.strength.value
                parts.append(f"- {name}: {signal} ({strength})")

            parts.append("")

        if news:
            parts.append("## News Context")
            parts.append(f"Overall Sentiment: {news.overall_sentiment.value}")
            parts.append(f"Sentiment Score: {news.sentiment_score:+.2f}")
            parts.append("")

            for item in news.items[:5]:
                age = f"{item.age_hours:.1f}h ago"
                sentiment = f"[{item.sentiment.value}]" if item.sentiment != NewsSentiment.UNKNOWN else ""
                parts.append(f"- [{age}] {item.title} {sentiment}")

            parts.append("")

        # Include memory context if available
        if memory_context and memory_context.has_relevant_context():
            parts.append(memory_context.to_prompt_context())
            parts.append("")

        parts.append("Provide your analysis in the required JSON format.")

        return "\n".join(parts)

    def _parse_response(self, symbol: str, raw_response: str) -> MarketContext:
        """Parse LLM response into MarketContext."""
        import json

        try:
            # Clean response (remove markdown code blocks if present)
            cleaned = raw_response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            cleaned = cleaned.strip()

            data = json.loads(cleaned)

            # Map bias string to enum
            bias_map = {
                "strongly_bullish": MarketBias.STRONGLY_BULLISH,
                "bullish": MarketBias.BULLISH,
                "neutral": MarketBias.NEUTRAL,
                "bearish": MarketBias.BEARISH,
                "strongly_bearish": MarketBias.STRONGLY_BEARISH,
                "uncertain": MarketBias.UNCERTAIN,
            }
            bias = bias_map.get(data.get("bias", "uncertain"), MarketBias.UNCERTAIN)

            # Map recommendation string to enum
            rec_map = {
                "strong_buy": ActionRecommendation.STRONG_BUY,
                "buy": ActionRecommendation.BUY,
                "hold": ActionRecommendation.HOLD,
                "sell": ActionRecommendation.SELL,
                "strong_sell": ActionRecommendation.STRONG_SELL,
                "wait": ActionRecommendation.WAIT,
            }
            recommendation = rec_map.get(
                data.get("recommendation", "wait"),
                ActionRecommendation.WAIT,
            )

            return MarketContext(
                symbol=symbol,
                timestamp=datetime.now(UTC),
                bias=bias,
                confidence=float(data.get("confidence", 0.5)),
                recommendation=recommendation,
                reasoning=data.get("reasoning", ""),
                key_bullish_factors=data.get("bullish_factors", []),
                key_bearish_factors=data.get("bearish_factors", []),
                risks=data.get("risks", []),
                simple_explanation=data.get("simple_explanation", ""),
                raw_response=raw_response,
            )

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("llm_parse_failed", error=str(e), response=raw_response[:200])
            return MarketContext(
                symbol=symbol,
                timestamp=datetime.now(UTC),
                bias=MarketBias.UNCERTAIN,
                confidence=0.3,
                recommendation=ActionRecommendation.WAIT,
                reasoning="Failed to parse LLM response",
                simple_explanation="Analysis unavailable. Proceed with caution.",
                raw_response=raw_response,
            )

    def _create_fallback_context(
        self,
        symbol: str,
        technical: TechnicalAnalysis | None,
        news: NewsDigest | None,
    ) -> MarketContext:
        """Create a fallback context when LLM is unavailable."""
        # Derive context from technical and news data
        bullish_factors = []
        bearish_factors = []

        if technical:
            if technical.overall_trend == TrendDirection.BULLISH:
                bullish_factors.append("Technical indicators are bullish")
            elif technical.overall_trend == TrendDirection.BEARISH:
                bearish_factors.append("Technical indicators are bearish")

        if news:
            if news.overall_sentiment == NewsSentiment.BULLISH:
                bullish_factors.append("News sentiment is positive")
            elif news.overall_sentiment == NewsSentiment.BEARISH:
                bearish_factors.append("News sentiment is negative")

        # Determine bias
        if len(bullish_factors) > len(bearish_factors):
            bias = MarketBias.BULLISH
            recommendation = ActionRecommendation.BUY
        elif len(bearish_factors) > len(bullish_factors):
            bias = MarketBias.BEARISH
            recommendation = ActionRecommendation.SELL
        else:
            bias = MarketBias.NEUTRAL
            recommendation = ActionRecommendation.HOLD

        return MarketContext(
            symbol=symbol,
            timestamp=datetime.now(UTC),
            bias=bias,
            confidence=0.5,  # Lower confidence without LLM
            recommendation=recommendation,
            reasoning="Analysis based on technical and news data (LLM unavailable)",
            key_bullish_factors=bullish_factors,
            key_bearish_factors=bearish_factors,
            risks=["LLM analysis unavailable - reduced confidence"],
            simple_explanation="Basic analysis available. LLM features require API key.",
        )

    def get_last_analysis(self) -> MarketContext | None:
        """Get the last analysis result."""
        return self._last_analysis

    def format_for_display(self, context: MarketContext, simple: bool = True) -> str:
        """Format context for display."""
        if simple:
            emoji_map = {
                MarketBias.STRONGLY_BULLISH: "🚀",
                MarketBias.BULLISH: "📈",
                MarketBias.NEUTRAL: "➡️",
                MarketBias.BEARISH: "📉",
                MarketBias.STRONGLY_BEARISH: "💥",
                MarketBias.UNCERTAIN: "❓",
            }
            emoji = emoji_map.get(context.bias, "❓")

            rec_map = {
                ActionRecommendation.STRONG_BUY: "Strong Buy",
                ActionRecommendation.BUY: "Buy",
                ActionRecommendation.HOLD: "Hold",
                ActionRecommendation.SELL: "Sell",
                ActionRecommendation.STRONG_SELL: "Strong Sell",
                ActionRecommendation.WAIT: "Wait",
            }
            rec_text = rec_map.get(context.recommendation, "Wait")

            return (
                f"{emoji} Context: {context.bias.value.replace('_', ' ').title()} "
                f"({context.confidence:.0%})\n"
                f"▶ Suggestion: {rec_text}\n"
                f"▶ {context.simple_explanation}"
            )
        else:
            lines = [
                f"Market Context: {context.symbol}",
                f"Bias: {context.bias.value} | Confidence: {context.confidence:.0%}",
                f"Recommendation: {context.recommendation.value}",
                "",
                "Reasoning:",
                context.reasoning,
            ]

            if context.key_bullish_factors:
                lines.append("\nBullish Factors:")
                for factor in context.key_bullish_factors:
                    lines.append(f"  + {factor}")

            if context.key_bearish_factors:
                lines.append("\nBearish Factors:")
                for factor in context.key_bearish_factors:
                    lines.append(f"  - {factor}")

            if context.risks:
                lines.append("\nRisks:")
                for risk in context.risks:
                    lines.append(f"  ⚠ {risk}")

            return "\n".join(lines)


# Global instance
_brain: OracleBrain | None = None


def get_oracle_brain() -> OracleBrain:
    """Get the global Oracle Brain instance."""
    global _brain
    if _brain is None:
        _brain = OracleBrain()
    return _brain
