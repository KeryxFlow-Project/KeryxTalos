"""Multi-Timeframe Analysis coordinator."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pandas as pd

from keryxflow.config import get_settings
from keryxflow.core.logging import get_logger
from keryxflow.oracle.technical import (
    TechnicalAnalysis,
    TechnicalAnalyzer,
    TrendDirection,
    get_technical_analyzer,
)

if TYPE_CHECKING:
    from keryxflow.oracle.signals import SignalType

logger = get_logger(__name__)


@dataclass
class MultiTimeframeAnalysis:
    """
    Result of multi-timeframe analysis.

    Combines technical analysis from multiple timeframes into a
    coherent view of market conditions.
    """

    symbol: str
    timestamp: datetime
    analyses: dict[str, TechnicalAnalysis]  # timeframe -> analysis
    filter_trend: TrendDirection
    filter_confidence: float
    aligned: bool

    # Primary timeframe analysis (shortcut)
    primary_timeframe: str | None = None
    primary_analysis: TechnicalAnalysis | None = None

    # Filter timeframe analysis (shortcut)
    filter_timeframe: str | None = None
    filter_analysis: TechnicalAnalysis | None = None

    # Aggregated summaries
    simple_summary: str = ""
    technical_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "analyses": {tf: a.to_dict() for tf, a in self.analyses.items()},
            "filter_trend": self.filter_trend.value,
            "filter_confidence": self.filter_confidence,
            "aligned": self.aligned,
            "primary_timeframe": self.primary_timeframe,
            "filter_timeframe": self.filter_timeframe,
            "simple_summary": self.simple_summary,
            "technical_summary": self.technical_summary,
        }


class MTFAnalyzer:
    """
    Multi-Timeframe Analysis coordinator.

    Performs technical analysis on multiple timeframes and determines:
    - Higher timeframe trend direction (filter)
    - Alignment between timeframes
    - Overall market context
    """

    def __init__(
        self,
        analyzer: TechnicalAnalyzer | None = None,
        primary_timeframe: str | None = None,
        filter_timeframe: str | None = None,
        min_candles: int = 50,
    ):
        """
        Initialize the MTF analyzer.

        Args:
            analyzer: Technical analyzer to use (or get global)
            primary_timeframe: Timeframe for entry signals
            filter_timeframe: Timeframe for trend filtering
            min_candles: Minimum candles required for analysis
        """
        self._analyzer = analyzer or get_technical_analyzer()
        self._min_candles = min_candles

        # Get settings if not provided
        settings = get_settings()
        mtf_settings = settings.oracle.mtf

        self._primary_tf = primary_timeframe or mtf_settings.primary_timeframe
        self._filter_tf = filter_timeframe or mtf_settings.filter_timeframe

    def analyze(
        self,
        ohlcv_data: dict[str, pd.DataFrame],
        symbol: str,
    ) -> MultiTimeframeAnalysis:
        """
        Perform multi-timeframe analysis.

        Args:
            ohlcv_data: Dict mapping timeframe to OHLCV DataFrame
            symbol: Trading pair symbol

        Returns:
            MultiTimeframeAnalysis with results from all timeframes
        """
        analyses: dict[str, TechnicalAnalysis] = {}

        # Analyze each timeframe
        for timeframe, df in ohlcv_data.items():
            if df is None or len(df) < self._min_candles:
                logger.debug(
                    "mtf_skip_timeframe",
                    timeframe=timeframe,
                    candles=len(df) if df is not None else 0,
                    min_required=self._min_candles,
                )
                continue

            try:
                analysis = self._analyzer.analyze(df, symbol)
                analyses[timeframe] = analysis
                logger.debug(
                    "mtf_analyzed_timeframe",
                    timeframe=timeframe,
                    trend=analysis.overall_trend.value,
                    confidence=analysis.confidence,
                )
            except Exception as e:
                logger.warning(
                    "mtf_analysis_failed",
                    timeframe=timeframe,
                    error=str(e),
                )

        # Determine filter trend
        filter_trend, filter_confidence = self._determine_filter_trend(analyses)

        # Check alignment
        aligned = self._check_alignment(analyses)

        # Get primary and filter analyses
        primary_analysis = analyses.get(self._primary_tf)
        filter_analysis = analyses.get(self._filter_tf)

        # Generate summaries
        simple_summary = self._generate_simple_summary(analyses, filter_trend, aligned)
        technical_summary = self._generate_technical_summary(
            analyses, filter_trend, filter_confidence, aligned
        )

        result = MultiTimeframeAnalysis(
            symbol=symbol,
            timestamp=datetime.now(UTC),
            analyses=analyses,
            filter_trend=filter_trend,
            filter_confidence=filter_confidence,
            aligned=aligned,
            primary_timeframe=self._primary_tf,
            primary_analysis=primary_analysis,
            filter_timeframe=self._filter_tf,
            filter_analysis=filter_analysis,
            simple_summary=simple_summary,
            technical_summary=technical_summary,
        )

        logger.info(
            "mtf_analysis_complete",
            symbol=symbol,
            timeframes=list(analyses.keys()),
            filter_trend=filter_trend.value,
            filter_confidence=f"{filter_confidence:.2f}",
            aligned=aligned,
        )

        return result

    def _determine_filter_trend(
        self, analyses: dict[str, TechnicalAnalysis]
    ) -> tuple[TrendDirection, float]:
        """
        Determine the trend from the filter timeframe.

        Args:
            analyses: Dict of timeframe -> TechnicalAnalysis

        Returns:
            Tuple of (trend direction, confidence)
        """
        filter_analysis = analyses.get(self._filter_tf)

        if filter_analysis is None:
            # Fallback: use highest timeframe available
            if not analyses:
                return TrendDirection.NEUTRAL, 0.0

            # Sort by timeframe duration (longest first)
            from keryxflow.core.mtf_buffer import timeframe_to_seconds

            sorted_tfs = sorted(
                analyses.keys(),
                key=lambda tf: timeframe_to_seconds(tf),
                reverse=True,
            )
            filter_analysis = analyses[sorted_tfs[0]]

        return filter_analysis.overall_trend, filter_analysis.confidence

    def _check_alignment(self, analyses: dict[str, TechnicalAnalysis]) -> bool:
        """
        Check if all timeframes are aligned in the same direction.

        Args:
            analyses: Dict of timeframe -> TechnicalAnalysis

        Returns:
            True if all non-neutral trends point the same direction
        """
        if len(analyses) < 2:
            return True

        directional_trends = [
            a.overall_trend for a in analyses.values() if a.overall_trend != TrendDirection.NEUTRAL
        ]

        if not directional_trends:
            return True  # All neutral = aligned

        # Check if all directional trends are the same
        first_trend = directional_trends[0]
        return all(t == first_trend for t in directional_trends)

    def _generate_simple_summary(
        self,
        analyses: dict[str, TechnicalAnalysis],
        filter_trend: TrendDirection,
        aligned: bool,
    ) -> str:
        """Generate a beginner-friendly summary of MTF analysis."""
        if not analyses:
            return "Not enough data for multi-timeframe analysis."

        trend_str = {
            TrendDirection.BULLISH: "upward",
            TrendDirection.BEARISH: "downward",
            TrendDirection.NEUTRAL: "sideways",
        }

        base = f"The bigger picture shows the market moving {trend_str[filter_trend]}."

        if aligned:
            base += " All timeframes agree on the direction."
        else:
            base += " Shorter timeframes show mixed signals."

        return base

    def _generate_technical_summary(
        self,
        analyses: dict[str, TechnicalAnalysis],
        filter_trend: TrendDirection,
        filter_confidence: float,
        aligned: bool,
    ) -> str:
        """Generate a technical summary of MTF analysis."""
        parts = [f"Filter: {filter_trend.value.upper()} ({filter_confidence:.0%})"]

        for tf, analysis in sorted(analyses.items()):
            parts.append(f"{tf}: {analysis.overall_trend.value} ({analysis.confidence:.0%})")

        alignment_str = "ALIGNED" if aligned else "DIVERGENT"
        parts.append(f"Status: {alignment_str}")

        return " | ".join(parts)


def apply_trend_filter(
    primary_signal: "SignalType",
    filter_trend: TrendDirection,
    filter_confidence: float,
    min_confidence: float = 0.5,
) -> "SignalType":
    """
    Apply trend filter to a signal.

    The filter timeframe trend restricts which signals from the primary
    timeframe are allowed:
    - BULLISH filter: only LONG signals allowed
    - BEARISH filter: only SHORT signals allowed
    - NEUTRAL filter: all signals allowed

    Args:
        primary_signal: Signal from primary timeframe
        filter_trend: Trend from filter timeframe
        filter_confidence: Confidence in filter trend
        min_confidence: Minimum confidence to apply filter

    Returns:
        Filtered signal (may be NO_ACTION if filtered out)
    """
    from keryxflow.oracle.signals import SignalType

    # Low confidence = allow any signal
    if filter_confidence < min_confidence:
        return primary_signal

    # BULLISH filter = only allow LONG
    if filter_trend == TrendDirection.BULLISH and primary_signal == SignalType.SHORT:
        return SignalType.NO_ACTION

    # BEARISH filter = only allow SHORT
    if filter_trend == TrendDirection.BEARISH and primary_signal == SignalType.LONG:
        return SignalType.NO_ACTION

    return primary_signal


# Global instance
_mtf_analyzer: MTFAnalyzer | None = None


def get_mtf_analyzer() -> MTFAnalyzer:
    """Get the global MTF analyzer instance."""
    global _mtf_analyzer
    if _mtf_analyzer is None:
        _mtf_analyzer = MTFAnalyzer()
    return _mtf_analyzer
