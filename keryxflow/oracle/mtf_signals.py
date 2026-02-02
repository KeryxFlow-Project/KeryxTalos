"""Multi-Timeframe Signal Generator."""

from datetime import UTC, datetime

import pandas as pd

from keryxflow.config import get_settings
from keryxflow.core.events import Event, EventBus, EventType
from keryxflow.core.logging import get_logger
from keryxflow.oracle.brain import MarketContext, OracleBrain
from keryxflow.oracle.feeds import NewsAggregator, NewsDigest
from keryxflow.oracle.mtf_analyzer import (
    MTFAnalyzer,
    MultiTimeframeAnalysis,
    apply_trend_filter,
    get_mtf_analyzer,
)
from keryxflow.oracle.signals import (
    SignalGenerator,
    SignalSource,
    SignalType,
    TradingSignal,
)
from keryxflow.oracle.technical import (
    TechnicalAnalyzer,
    TrendDirection,
)

logger = get_logger(__name__)


class MTFSignalGenerator(SignalGenerator):
    """
    Signal generator with Multi-Timeframe Analysis support.

    Extends the base SignalGenerator to support:
    - Analysis across multiple timeframes
    - Higher timeframe trend filtering
    - Timeframe alignment detection
    - Fallback to single-timeframe when MTF data unavailable
    """

    def __init__(
        self,
        technical_analyzer: TechnicalAnalyzer | None = None,
        news_aggregator: NewsAggregator | None = None,
        brain: OracleBrain | None = None,
        event_bus: EventBus | None = None,
        mtf_analyzer: MTFAnalyzer | None = None,
        publish_events: bool = True,
    ):
        """
        Initialize the MTF signal generator.

        Args:
            technical_analyzer: Technical analyzer for single-TF analysis
            news_aggregator: News aggregator
            brain: LLM brain for analysis
            event_bus: Event bus for publishing
            mtf_analyzer: MTF analyzer (or get global)
            publish_events: Whether to publish events
        """
        super().__init__(
            technical_analyzer=technical_analyzer,
            news_aggregator=news_aggregator,
            brain=brain,
            event_bus=event_bus,
            publish_events=publish_events,
        )

        self._mtf_analyzer = mtf_analyzer or get_mtf_analyzer()
        self._mtf_settings = get_settings().oracle.mtf

    async def generate_signal(
        self,
        symbol: str,
        ohlcv: pd.DataFrame | dict[str, pd.DataFrame],
        current_price: float | None = None,
        include_news: bool = True,
        include_llm: bool = True,
    ) -> TradingSignal:
        """
        Generate a trading signal with MTF support.

        If ohlcv is a dict with multiple timeframes, performs MTF analysis.
        If ohlcv is a single DataFrame, falls back to single-TF analysis.

        Args:
            symbol: Trading pair symbol
            ohlcv: Either a DataFrame (single TF) or dict[timeframe, DataFrame]
            current_price: Current price (defaults to last close of primary TF)
            include_news: Whether to include news analysis
            include_llm: Whether to include LLM analysis

        Returns:
            TradingSignal with MTF context when available
        """
        # Determine if this is MTF or single-TF
        if isinstance(ohlcv, dict):
            return await self._generate_mtf_signal(
                symbol=symbol,
                ohlcv_data=ohlcv,
                current_price=current_price,
                include_news=include_news,
                include_llm=include_llm,
            )
        else:
            # Fallback to single-TF analysis
            return await super().generate_signal(
                symbol=symbol,
                ohlcv=ohlcv,
                current_price=current_price,
                include_news=include_news,
                include_llm=include_llm,
            )

    async def _generate_mtf_signal(
        self,
        symbol: str,
        ohlcv_data: dict[str, pd.DataFrame],
        current_price: float | None = None,
        include_news: bool = True,
        include_llm: bool = True,
    ) -> TradingSignal:
        """
        Generate a signal using multi-timeframe analysis.

        Args:
            symbol: Trading pair symbol
            ohlcv_data: Dict mapping timeframe to DataFrame
            current_price: Current price
            include_news: Include news analysis
            include_llm: Include LLM analysis

        Returns:
            TradingSignal with MTF context
        """
        # Get primary timeframe data
        primary_tf = self._mtf_settings.primary_timeframe
        primary_df = ohlcv_data.get(primary_tf)

        if primary_df is None:
            # Try to find any available timeframe
            if ohlcv_data:
                primary_tf = next(iter(ohlcv_data.keys()))
                primary_df = ohlcv_data[primary_tf]
            else:
                return self._no_action_signal(symbol, "No OHLCV data available")

        # Get current price from primary timeframe
        if current_price is None:
            current_price = float(primary_df["close"].iloc[-1])

        # Perform MTF analysis
        try:
            mtf_analysis = self._mtf_analyzer.analyze(ohlcv_data, symbol)
        except Exception as e:
            logger.warning("mtf_analysis_failed", symbol=symbol, error=str(e))
            # Fallback to single-TF
            return await super().generate_signal(
                symbol=symbol,
                ohlcv=primary_df,
                current_price=current_price,
                include_news=include_news,
                include_llm=include_llm,
            )

        # Generate base signal from primary timeframe
        if mtf_analysis.primary_analysis is None:
            return self._no_action_signal(symbol, "Primary timeframe analysis unavailable")

        # Get technical signal from primary analysis
        base_signal = self._technical_to_signal(mtf_analysis.primary_analysis)
        base_confidence = mtf_analysis.primary_analysis.confidence

        # Apply trend filter
        filtered_signal = apply_trend_filter(
            primary_signal=base_signal,
            filter_trend=mtf_analysis.filter_trend,
            filter_confidence=mtf_analysis.filter_confidence,
            min_confidence=self._mtf_settings.min_filter_confidence,
        )

        # Adjust confidence based on alignment
        if mtf_analysis.aligned:
            # Alignment boosts confidence
            adjusted_confidence = min(1.0, base_confidence * 1.2)
        else:
            # Divergence reduces confidence
            adjusted_confidence = base_confidence * 0.8

        # News analysis (optional)
        news_digest: NewsDigest | None = None
        if include_news and self.settings.oracle.news_enabled:
            try:
                news_digest = await self.news.fetch_news(symbols=[symbol])
            except Exception as e:
                logger.warning("news_fetch_failed", symbol=symbol, error=str(e))

        # LLM analysis (optional) - use primary timeframe analysis
        llm_context: MarketContext | None = None
        source = SignalSource.TECHNICAL
        if include_llm and self.settings.oracle.llm_enabled:
            try:
                llm_context = await self.brain.analyze(
                    symbol, mtf_analysis.primary_analysis, news_digest
                )
                source = SignalSource.HYBRID

                # LLM can further adjust the signal
                filtered_signal, llm_confidence = self._adjust_with_llm(
                    filtered_signal, llm_context
                )
                adjusted_confidence = (adjusted_confidence * 0.6) + (llm_confidence * 0.4)
            except Exception as e:
                logger.warning("llm_analysis_failed", symbol=symbol, error=str(e))

        # Calculate price targets
        entry, stop_loss, take_profit = self._calculate_targets(
            current_price, filtered_signal, mtf_analysis.primary_analysis
        )

        # Risk/reward
        risk_reward = None
        if stop_loss and take_profit:
            risk = abs(current_price - stop_loss)
            reward = abs(take_profit - current_price)
            risk_reward = reward / risk if risk > 0 else 0

        # Determine final strength
        strength = self._confidence_to_strength(adjusted_confidence)

        # Generate explanations
        simple_reason = self._generate_mtf_simple_reason(filtered_signal, mtf_analysis, llm_context)
        technical_reason = self._generate_mtf_technical_reason(
            filtered_signal, mtf_analysis, llm_context
        )

        signal = TradingSignal(
            symbol=symbol,
            signal_type=filtered_signal,
            strength=strength,
            confidence=adjusted_confidence,
            source=source,
            timestamp=datetime.now(UTC),
            entry_price=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward=risk_reward,
            technical_trend=mtf_analysis.primary_analysis.overall_trend,
            llm_bias=llm_context.bias if llm_context else None,
            news_sentiment=news_digest.overall_sentiment.value if news_digest else None,
            simple_reason=simple_reason,
            technical_reason=technical_reason,
            technical_data=mtf_analysis.primary_analysis.to_dict(),
            llm_data=llm_context.to_dict() if llm_context else None,
            # MTF-specific fields
            primary_timeframe=mtf_analysis.primary_timeframe,
            filter_timeframe=mtf_analysis.filter_timeframe,
            filter_trend=mtf_analysis.filter_trend,
            timeframe_alignment=mtf_analysis.aligned,
            mtf_data=mtf_analysis.to_dict(),
        )

        # Check for significant change
        if self._is_significant_change(symbol, signal):
            if self._publish_events:
                await self.event_bus.publish(
                    Event(type=EventType.SIGNAL_GENERATED, data=signal.to_dict())
                )
            self._last_signals[symbol] = signal

        logger.info(
            "mtf_signal_generated",
            symbol=symbol,
            type=signal.signal_type.value,
            strength=signal.strength.value,
            confidence=signal.confidence,
            filter_trend=mtf_analysis.filter_trend.value,
            aligned=mtf_analysis.aligned,
        )

        return signal

    def _generate_mtf_simple_reason(
        self,
        signal: SignalType,
        mtf: MultiTimeframeAnalysis,
        llm: MarketContext | None,
    ) -> str:
        """Generate a beginner-friendly explanation for MTF signal."""
        if signal == SignalType.NO_ACTION:
            if mtf.filter_trend != TrendDirection.NEUTRAL:
                trend = "bullish" if mtf.filter_trend == TrendDirection.BULLISH else "bearish"
                return f"Waiting for better timing. The bigger picture shows {trend} bias, but short-term signals don't align."
            return "No clear opportunity right now. Better to wait."

        action = "buying" if signal == SignalType.LONG else "selling"
        alignment = "All timeframes agree" if mtf.aligned else "Shorter timeframes are mixed"

        base = f"Signal suggests {action}. {alignment}."

        if llm and llm.simple_explanation:
            return f"{base} {llm.simple_explanation}"

        return f"{base} {mtf.simple_summary}"

    def _generate_mtf_technical_reason(
        self,
        signal: SignalType,
        mtf: MultiTimeframeAnalysis,
        llm: MarketContext | None,
    ) -> str:
        """Generate technical explanation for MTF signal."""
        parts = [f"Signal: {signal.value.upper()}"]
        parts.append(mtf.technical_summary)

        if llm:
            parts.append(f"LLM: {llm.bias.value} ({llm.confidence:.0%})")

        return " | ".join(parts)


# Global instance
_mtf_generator: MTFSignalGenerator | None = None


def get_mtf_signal_generator() -> MTFSignalGenerator:
    """Get the global MTF signal generator instance."""
    global _mtf_generator
    if _mtf_generator is None:
        _mtf_generator = MTFSignalGenerator()
    return _mtf_generator
