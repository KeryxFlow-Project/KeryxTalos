"""Analysis tools for technical analysis and calculations.

These tools perform computations and analysis but do not modify state.
They do not require guardrail validation.
"""

from datetime import UTC, datetime
from typing import Any

import pandas as pd

from keryxflow.agent.tools import (
    BaseTool,
    ToolCategory,
    ToolParameter,
    ToolResult,
    TradingToolkit,
)
from keryxflow.core.logging import get_logger

logger = get_logger(__name__)


class CalculateIndicatorsTool(BaseTool):
    """Calculate technical indicators for a trading pair."""

    @property
    def name(self) -> str:
        return "calculate_indicators"

    @property
    def description(self) -> str:
        return (
            "Calculate technical indicators (RSI, MACD, Bollinger Bands, etc.) "
            "for a trading pair. Returns analysis with trend direction and strength."
        )

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="symbol",
                type="string",
                description="Trading pair symbol (e.g., 'BTC/USDT')",
                required=True,
            ),
            ToolParameter(
                name="timeframe",
                type="string",
                description="Candlestick timeframe for analysis",
                required=False,
                default="1h",
                enum=["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
            ),
            ToolParameter(
                name="limit",
                type="integer",
                description="Number of candles to analyze (min 50 for reliable indicators)",
                required=False,
                default=100,
            ),
        ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        symbol = kwargs["symbol"]
        timeframe = kwargs.get("timeframe", "1h")
        limit = max(kwargs.get("limit", 100), 50)  # Minimum 50 for indicators

        try:
            # Fetch OHLCV data
            from keryxflow.exchange import get_exchange_adapter

            client = get_exchange_adapter()
            ohlcv = await client.fetch_ohlcv(symbol, timeframe, limit=limit)

            if len(ohlcv) < 30:
                return ToolResult(
                    success=False,
                    error=f"Insufficient data for analysis. Got {len(ohlcv)} candles, need at least 30.",
                )

            # Convert to DataFrame
            df = pd.DataFrame(
                ohlcv,
                columns=["timestamp", "open", "high", "low", "close", "volume"],
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)

            # Run technical analysis
            from keryxflow.oracle.technical import get_technical_analyzer

            analyzer = get_technical_analyzer()
            analysis = analyzer.analyze(df, symbol)

            # Format indicator results
            indicators_data = {}
            for name, indicator in analysis.indicators.items():
                indicators_data[name] = {
                    "value": indicator.value,
                    "signal": indicator.signal.value,
                    "strength": indicator.strength.value,
                    "simple_explanation": indicator.simple_explanation,
                    "technical_explanation": indicator.technical_explanation,
                }

            return ToolResult(
                success=True,
                data={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "overall_trend": analysis.overall_trend.value,
                    "overall_strength": analysis.overall_strength.value,
                    "confidence": analysis.confidence,
                    "simple_summary": analysis.simple_summary,
                    "technical_summary": analysis.technical_summary,
                    "indicators": indicators_data,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

        except Exception as e:
            logger.error("calculate_indicators_failed", symbol=symbol, error=str(e))
            return ToolResult(
                success=False,
                error=f"Failed to calculate indicators for {symbol}: {str(e)}",
            )


class CalculatePositionSizeTool(BaseTool):
    """Calculate optimal position size based on risk parameters."""

    @property
    def name(self) -> str:
        return "calculate_position_size"

    @property
    def description(self) -> str:
        return (
            "Calculate the optimal position size based on account balance, "
            "entry price, stop loss, and risk percentage per trade. "
            "Uses proper risk management to limit losses."
        )

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="balance",
                type="number",
                description="Account balance in quote currency (e.g., USDT)",
                required=True,
            ),
            ToolParameter(
                name="entry_price",
                type="number",
                description="Planned entry price",
                required=True,
            ),
            ToolParameter(
                name="stop_loss",
                type="number",
                description="Stop loss price",
                required=True,
            ),
            ToolParameter(
                name="risk_pct",
                type="number",
                description="Risk percentage per trade (e.g., 0.01 for 1%)",
                required=False,
                default=0.01,
            ),
        ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        balance = kwargs["balance"]
        entry_price = kwargs["entry_price"]
        stop_loss = kwargs["stop_loss"]
        risk_pct = kwargs.get("risk_pct", 0.01)

        try:
            from keryxflow.aegis.quant import get_quant_engine

            quant = get_quant_engine()

            result = quant.position_size(
                balance=balance,
                entry_price=entry_price,
                stop_loss=stop_loss,
                risk_per_trade=risk_pct,
            )

            return ToolResult(
                success=True,
                data={
                    "quantity": result.quantity,
                    "position_value": result.position_value,
                    "risk_amount": result.risk_amount,
                    "risk_percentage": result.risk_percentage,
                    "stop_distance": result.stop_distance,
                    "simple_explanation": result.simple_explanation,
                    "technical_details": result.technical_details,
                },
            )

        except ValueError as e:
            return ToolResult(
                success=False,
                error=str(e),
            )
        except Exception as e:
            logger.error("calculate_position_size_failed", error=str(e))
            return ToolResult(
                success=False,
                error=f"Failed to calculate position size: {str(e)}",
            )


class CalculateRiskRewardTool(BaseTool):
    """Calculate risk/reward ratio for a trade."""

    @property
    def name(self) -> str:
        return "calculate_risk_reward"

    @property
    def description(self) -> str:
        return (
            "Calculate the risk/reward ratio for a planned trade. "
            "Returns potential profit, potential loss, and the R:R ratio. "
            "A ratio >= 2.0 is generally considered favorable."
        )

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="entry_price",
                type="number",
                description="Entry price for the trade",
                required=True,
            ),
            ToolParameter(
                name="stop_loss",
                type="number",
                description="Stop loss price",
                required=True,
            ),
            ToolParameter(
                name="take_profit",
                type="number",
                description="Take profit target price",
                required=True,
            ),
            ToolParameter(
                name="quantity",
                type="number",
                description="Position quantity (for calculating dollar amounts)",
                required=False,
                default=1.0,
            ),
        ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        entry_price = kwargs["entry_price"]
        stop_loss = kwargs["stop_loss"]
        take_profit = kwargs["take_profit"]
        quantity = kwargs.get("quantity", 1.0)

        try:
            from keryxflow.aegis.quant import get_quant_engine

            quant = get_quant_engine()

            result = quant.risk_reward_ratio(
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                quantity=quantity,
            )

            return ToolResult(
                success=True,
                data={
                    "ratio": result.ratio,
                    "potential_profit": result.potential_profit,
                    "potential_loss": result.potential_loss,
                    "breakeven_winrate": result.breakeven_winrate,
                    "is_favorable": result.is_favorable,
                    "simple_explanation": result.simple_explanation,
                },
            )

        except ValueError as e:
            return ToolResult(
                success=False,
                error=str(e),
            )
        except Exception as e:
            logger.error("calculate_risk_reward_failed", error=str(e))
            return ToolResult(
                success=False,
                error=f"Failed to calculate risk/reward: {str(e)}",
            )


class GetTradingRulesTool(BaseTool):
    """Get active trading rules from semantic memory."""

    @property
    def name(self) -> str:
        return "get_trading_rules"

    @property
    def description(self) -> str:
        return (
            "Get active trading rules from memory. Rules can be learned from "
            "past trades, defined by users, or discovered through backtesting. "
            "Use these rules to inform trading decisions."
        )

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.INTROSPECTION

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="symbol",
                type="string",
                description="Filter rules by symbol (optional)",
                required=False,
            ),
            ToolParameter(
                name="context",
                type="object",
                description="Market context to match rules against (optional)",
                required=False,
            ),
        ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        symbol = kwargs.get("symbol")
        context = kwargs.get("context", {})

        try:
            from keryxflow.memory.semantic import get_semantic_memory

            semantic = get_semantic_memory()

            if context:
                rules = await semantic.get_matching_rules(
                    symbol=symbol,
                    context=context,
                )
            else:
                rules = await semantic.get_active_rules(symbol=symbol)

            rules_data = []
            for rule in rules:
                rules_data.append(
                    {
                        "id": rule.id,
                        "name": rule.name,
                        "description": rule.description,
                        "condition": rule.condition,
                        "category": rule.category,
                        "source": rule.source.value,
                        "confidence": rule.confidence,
                        "success_rate": rule.success_rate,
                        "times_applied": rule.times_applied,
                        "times_successful": rule.times_successful,
                    }
                )

            return ToolResult(
                success=True,
                data={
                    "rules": rules_data,
                    "count": len(rules_data),
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

        except Exception as e:
            logger.error("get_trading_rules_failed", error=str(e))
            return ToolResult(
                success=False,
                error=f"Failed to get trading rules: {str(e)}",
            )


class RecallSimilarTradesTool(BaseTool):
    """Recall similar trades from episodic memory."""

    @property
    def name(self) -> str:
        return "recall_similar_trades"

    @property
    def description(self) -> str:
        return (
            "Recall similar past trades from memory based on current market context. "
            "Returns trades with similar technical conditions and their outcomes. "
            "Use this to learn from past experiences."
        )

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.INTROSPECTION

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="symbol",
                type="string",
                description="Trading pair symbol",
                required=True,
            ),
            ToolParameter(
                name="rsi",
                type="number",
                description="Current RSI value (optional but improves matching)",
                required=False,
            ),
            ToolParameter(
                name="trend",
                type="string",
                description="Current trend direction",
                required=False,
                enum=["bullish", "bearish", "neutral"],
            ),
            ToolParameter(
                name="macd_signal",
                type="string",
                description="Current MACD signal",
                required=False,
                enum=["bullish", "bearish", "neutral"],
            ),
            ToolParameter(
                name="limit",
                type="integer",
                description="Maximum number of similar trades to return",
                required=False,
                default=5,
            ),
        ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        symbol = kwargs["symbol"]
        rsi = kwargs.get("rsi")
        trend = kwargs.get("trend")
        macd_signal = kwargs.get("macd_signal")
        limit = kwargs.get("limit", 5)

        try:
            from keryxflow.memory.episodic import get_episodic_memory

            episodic = get_episodic_memory()

            # Build technical_indicators dict for matching
            technical_indicators = {}
            if rsi is not None:
                technical_indicators["rsi"] = rsi
            if trend:
                technical_indicators["trend"] = trend
            if macd_signal:
                technical_indicators["macd_signal"] = macd_signal

            # Call recall_similar with correct parameters
            matches = await episodic.recall_similar(
                symbol=symbol,
                technical_indicators=technical_indicators if technical_indicators else None,
                limit=limit,
            )

            episodes_data = []
            for match in matches:
                episode = match.episode
                episodes_data.append(
                    {
                        "id": episode.id,
                        "trade_id": episode.trade_id,
                        "symbol": episode.symbol,
                        "side": episode.side,
                        "entry_price": episode.entry_price,
                        "exit_price": episode.exit_price,
                        "pnl": episode.pnl,
                        "pnl_percentage": episode.pnl_percentage,
                        "outcome": episode.outcome.value if episode.outcome else None,
                        "entry_reasoning": episode.entry_reasoning,
                        "lessons_learned": episode.lessons_learned,
                        "similarity_score": match.similarity_score,
                        "entry_timestamp": episode.entry_timestamp.isoformat()
                        if episode.entry_timestamp
                        else None,
                    }
                )

            return ToolResult(
                success=True,
                data={
                    "similar_trades": episodes_data,
                    "count": len(episodes_data),
                    "context_used": technical_indicators,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

        except Exception as e:
            logger.error("recall_similar_trades_failed", symbol=symbol, error=str(e))
            return ToolResult(
                success=False,
                error=f"Failed to recall similar trades: {str(e)}",
            )


class GetMarketPatternsTool(BaseTool):
    """Get identified market patterns from semantic memory."""

    @property
    def name(self) -> str:
        return "get_market_patterns"

    @property
    def description(self) -> str:
        return (
            "Get identified market patterns from memory that match the current "
            "technical context. Patterns include technical patterns, price action "
            "patterns, and time-based patterns that have been observed and validated."
        )

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.INTROSPECTION

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="rsi",
                type="number",
                description="Current RSI value (helps find matching patterns)",
                required=False,
            ),
            ToolParameter(
                name="trend",
                type="string",
                description="Current trend direction",
                required=False,
                enum=["bullish", "bearish", "neutral"],
            ),
            ToolParameter(
                name="symbol",
                type="string",
                description="Filter patterns by symbol (optional)",
                required=False,
            ),
            ToolParameter(
                name="timeframe",
                type="string",
                description="Filter patterns by timeframe (optional)",
                required=False,
            ),
        ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        rsi = kwargs.get("rsi")
        trend = kwargs.get("trend")
        symbol = kwargs.get("symbol")
        timeframe = kwargs.get("timeframe")

        try:
            from keryxflow.memory.semantic import get_semantic_memory

            semantic = get_semantic_memory()

            # Build technical context for matching
            technical_context = {}
            if rsi is not None:
                technical_context["rsi"] = rsi
            if trend:
                technical_context["trend"] = trend

            # If no context provided, use empty dict (will return all valid patterns)
            matches = await semantic.find_matching_patterns(
                technical_context=technical_context,
                symbol=symbol,
                timeframe=timeframe,
            )

            patterns_data = []
            for match in matches:
                pattern = match.pattern
                patterns_data.append(
                    {
                        "id": pattern.id,
                        "name": pattern.name,
                        "description": pattern.description,
                        "pattern_type": pattern.pattern_type.value,
                        "symbol": pattern.symbol,
                        "timeframe": pattern.timeframe,
                        "conditions": pattern.conditions,
                        "expected_outcome": pattern.expected_outcome,
                        "confidence": pattern.confidence,
                        "occurrences": pattern.occurrences,
                        "success_rate": pattern.success_rate,
                        "match_score": match.match_score,
                    }
                )

            return ToolResult(
                success=True,
                data={
                    "patterns": patterns_data,
                    "count": len(patterns_data),
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

        except Exception as e:
            logger.error("get_market_patterns_failed", error=str(e))
            return ToolResult(
                success=False,
                error=f"Failed to get market patterns: {str(e)}",
            )


class CalculateStopLossTool(BaseTool):
    """Calculate stop loss price based on ATR or fixed percentage."""

    @property
    def name(self) -> str:
        return "calculate_stop_loss"

    @property
    def description(self) -> str:
        return (
            "Calculate an appropriate stop loss price based on market volatility (ATR) "
            "or a fixed percentage from entry. ATR-based stops adapt to current volatility."
        )

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="entry_price",
                type="number",
                description="Entry price for the trade",
                required=True,
            ),
            ToolParameter(
                name="side",
                type="string",
                description="Trade side",
                required=True,
                enum=["buy", "sell"],
            ),
            ToolParameter(
                name="method",
                type="string",
                description="Stop loss calculation method",
                required=False,
                default="fixed",
                enum=["fixed", "atr"],
            ),
            ToolParameter(
                name="percentage",
                type="number",
                description="Fixed percentage for stop (e.g., 0.02 for 2%)",
                required=False,
                default=0.02,
            ),
            ToolParameter(
                name="atr_multiplier",
                type="number",
                description="ATR multiplier for volatility-based stop",
                required=False,
                default=2.0,
            ),
            ToolParameter(
                name="symbol",
                type="string",
                description="Symbol for ATR calculation (required if method is 'atr')",
                required=False,
            ),
        ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        entry_price = kwargs["entry_price"]
        side = kwargs["side"]
        method = kwargs.get("method", "fixed")
        percentage = kwargs.get("percentage", 0.02)
        atr_multiplier = kwargs.get("atr_multiplier", 2.0)
        symbol = kwargs.get("symbol")

        try:
            from keryxflow.aegis.quant import get_quant_engine

            quant = get_quant_engine()

            if method == "fixed":
                stop_price = quant.fixed_percentage_stop(
                    entry_price=entry_price,
                    side=side,
                    percentage=percentage,
                )
                method_used = f"Fixed {percentage * 100:.1f}%"

            elif method == "atr":
                if not symbol:
                    return ToolResult(
                        success=False,
                        error="Symbol is required for ATR-based stop loss",
                    )

                # Fetch recent price data for ATR calculation
                from keryxflow.exchange import get_exchange_adapter

                client = get_exchange_adapter()
                ohlcv = await client.fetch_ohlcv(symbol, "1h", limit=20)

                if len(ohlcv) < 15:
                    return ToolResult(
                        success=False,
                        error="Insufficient data for ATR calculation",
                    )

                highs = [c[2] for c in ohlcv]
                lows = [c[3] for c in ohlcv]
                closes = [c[4] for c in ohlcv]

                stop_price = quant.atr_stop_loss(
                    prices_high=highs,
                    prices_low=lows,
                    prices_close=closes,
                    entry_price=entry_price,
                    side=side,
                    multiplier=atr_multiplier,
                )
                method_used = f"ATR x{atr_multiplier}"

            else:
                return ToolResult(
                    success=False,
                    error=f"Unknown method: {method}",
                )

            distance = abs(entry_price - stop_price)
            distance_pct = distance / entry_price

            return ToolResult(
                success=True,
                data={
                    "stop_loss": stop_price,
                    "entry_price": entry_price,
                    "distance": distance,
                    "distance_pct": distance_pct * 100,
                    "method": method_used,
                    "side": side,
                },
            )

        except Exception as e:
            logger.error("calculate_stop_loss_failed", error=str(e))
            return ToolResult(
                success=False,
                error=f"Failed to calculate stop loss: {str(e)}",
            )


def register_analysis_tools(toolkit: TradingToolkit) -> None:
    """Register all analysis tools with the toolkit.

    Args:
        toolkit: The toolkit to register tools with
    """
    tools = [
        CalculateIndicatorsTool(),
        CalculatePositionSizeTool(),
        CalculateRiskRewardTool(),
        GetTradingRulesTool(),
        RecallSimilarTradesTool(),
        GetMarketPatternsTool(),
        CalculateStopLossTool(),
    ]

    for tool in tools:
        toolkit.register(tool)

    logger.info("analysis_tools_registered", count=len(tools))
