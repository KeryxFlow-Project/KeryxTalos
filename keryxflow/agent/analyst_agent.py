"""Analyst Agent for market analysis and pattern recognition.

The AnalystAgent gathers market data, calculates indicators, recalls similar
trades, and produces a MarketAnalysis result with signal direction and confidence.
It does NOT execute trades.
"""

from typing import Any

from keryxflow.agent.base_agent import (
    AgentRole,
    MarketAnalysis,
    SpecializedAgent,
)
from keryxflow.agent.tools import ToolCategory
from keryxflow.core.logging import get_logger

logger = get_logger(__name__)


class AnalystAgent(SpecializedAgent):
    """Specialized agent for market analysis and pattern recognition.

    Uses PERCEPTION and ANALYSIS/INTROSPECTION tools to gather market data,
    calculate indicators, and produce a structured MarketAnalysis result.
    """

    ANALYST_PROMPT = """You are KeryxFlow's Market Analyst agent. Your sole job is to analyze market conditions and identify trading opportunities.

## Your Role
- Gather market data using perception tools (prices, OHLCV, order book)
- Calculate technical indicators (RSI, MACD, Bollinger Bands, etc.)
- Recall similar past trades and applicable trading rules from memory
- Identify market patterns and potential setups

## What You Must Do
1. Get the current price and recent OHLCV data
2. Calculate technical indicators
3. Check memory for similar situations and trading rules
4. Analyze the data and determine if there is a trading signal

## Output Format
After your analysis, clearly state your conclusion:
- Signal: LONG, SHORT, or HOLD
- Confidence: A value from 0.0 to 1.0
- Key indicators and their values
- Your reasoning for the signal

You do NOT execute trades. You only analyze and report.

Current UTC time: {current_time}
"""

    @property
    def role(self) -> AgentRole:
        return AgentRole.ANALYST

    @property
    def system_prompt(self) -> str:
        return self.ANALYST_PROMPT

    @property
    def allowed_categories(self) -> list[ToolCategory]:
        return [ToolCategory.PERCEPTION, ToolCategory.ANALYSIS, ToolCategory.INTROSPECTION]

    async def analyze(self, symbol: str, context: dict[str, Any] | None = None) -> MarketAnalysis:
        """Analyze market conditions for a symbol.

        Args:
            symbol: Trading pair to analyze
            context: Optional additional context (price data, memory)

        Returns:
            MarketAnalysis with signal, confidence, and reasoning
        """
        if not self._initialized:
            await self.initialize()

        # Build user message
        parts = [
            f"Analyze the current market conditions for {symbol} and determine if there is a trading opportunity.\n"
        ]

        if context and context.get("market_data", {}).get(symbol):
            data = context["market_data"][symbol]
            if data.get("price"):
                parts.append(f"Current price data: {data['price']}")

        if context and context.get("memory_context", {}).get(symbol):
            mem = context["memory_context"][symbol]
            similar = len(mem.get("similar_episodes", []))
            rules = len(mem.get("matching_rules", []))
            parts.append(f"Memory: {similar} similar past trades, {rules} applicable rules")

        parts.append("\nUse the available tools to gather data, then provide your analysis.")
        user_message = "\n".join(parts)

        try:
            reasoning, tool_results, tokens = await self._call_claude(user_message)
            signal, confidence = self._parse_analysis(reasoning)

            return MarketAnalysis(
                symbol=symbol,
                signal=signal,
                confidence=confidence,
                reasoning=reasoning[:500],
                tool_results=tool_results,
                tokens_used=tokens,
            )

        except Exception as e:
            logger.error("analyst_agent_failed", symbol=symbol, error=str(e))
            return MarketAnalysis(
                symbol=symbol,
                signal="hold",
                confidence=0.0,
                reasoning=f"Analysis failed: {e}",
            )

    def _parse_analysis(self, reasoning: str) -> tuple[str, float]:
        """Parse signal and confidence from the analyst's reasoning."""
        reasoning_lower = reasoning.lower()

        # Determine signal
        if "signal: long" in reasoning_lower or "signal:long" in reasoning_lower:
            signal = "long"
        elif "signal: short" in reasoning_lower or "signal:short" in reasoning_lower:
            signal = "short"
        elif "long" in reasoning_lower and "short" not in reasoning_lower:
            if (
                "entry" in reasoning_lower
                or "buy" in reasoning_lower
                or "bullish" in reasoning_lower
            ):
                signal = "long"
            else:
                signal = "hold"
        elif "short" in reasoning_lower and "long" not in reasoning_lower:
            if (
                "entry" in reasoning_lower
                or "sell" in reasoning_lower
                or "bearish" in reasoning_lower
            ):
                signal = "short"
            else:
                signal = "hold"
        else:
            signal = "hold"

        # Parse confidence
        confidence = 0.5
        if "confidence: " in reasoning_lower or "confidence:" in reasoning_lower:
            import contextlib
            import re

            match = re.search(r"confidence:\s*(\d+\.?\d*)", reasoning_lower)
            if match:
                with contextlib.suppress(ValueError):
                    confidence = min(1.0, max(0.0, float(match.group(1))))
        elif "high confidence" in reasoning_lower:
            confidence = 0.8
        elif "low confidence" in reasoning_lower:
            confidence = 0.3

        return signal, confidence
