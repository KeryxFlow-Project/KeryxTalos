"""Technical analysis engine using pandas-ta indicators."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import pandas as pd
import pandas_ta as ta

from keryxflow.config import get_settings
from keryxflow.core.glossary import get_term
from keryxflow.core.logging import get_logger

logger = get_logger(__name__)


class TrendDirection(str, Enum):
    """Market trend direction."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class SignalStrength(str, Enum):
    """Signal strength classification."""

    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    NONE = "none"


@dataclass
class IndicatorResult:
    """Result from a single indicator calculation."""

    name: str
    value: float | dict[str, float]
    signal: TrendDirection
    strength: SignalStrength
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Human-readable explanations
    simple_explanation: str = ""
    technical_explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "value": self.value,
            "signal": self.signal.value,
            "strength": self.strength.value,
            "simple_explanation": self.simple_explanation,
            "technical_explanation": self.technical_explanation,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class TechnicalAnalysis:
    """Complete technical analysis result."""

    symbol: str
    timestamp: datetime
    indicators: dict[str, IndicatorResult]
    overall_trend: TrendDirection
    overall_strength: SignalStrength
    confidence: float  # 0.0 to 1.0

    # Aggregated explanations
    simple_summary: str = ""
    technical_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "indicators": {k: v.to_dict() for k, v in self.indicators.items()},
            "overall_trend": self.overall_trend.value,
            "overall_strength": self.overall_strength.value,
            "confidence": self.confidence,
            "simple_summary": self.simple_summary,
            "technical_summary": self.technical_summary,
        }


class TechnicalAnalyzer:
    """
    Technical analysis engine.

    Calculates various indicators and provides both technical
    and beginner-friendly explanations.
    """

    def __init__(self) -> None:
        """Initialize the analyzer with settings."""
        self.settings = get_settings().oracle

    def analyze(self, ohlcv: pd.DataFrame, symbol: str = "BTC/USDT") -> TechnicalAnalysis:
        """
        Perform complete technical analysis on OHLCV data.

        Args:
            ohlcv: DataFrame with columns: timestamp, open, high, low, close, volume
            symbol: Trading pair symbol

        Returns:
            TechnicalAnalysis with all indicator results
        """
        if len(ohlcv) < 50:
            raise ValueError("Need at least 50 candles for technical analysis")

        # Ensure column names are lowercase
        ohlcv.columns = ohlcv.columns.str.lower()

        indicators: dict[str, IndicatorResult] = {}

        # Calculate each enabled indicator
        if "rsi" in self.settings.indicators:
            indicators["rsi"] = self._calculate_rsi(ohlcv)

        if "macd" in self.settings.indicators:
            indicators["macd"] = self._calculate_macd(ohlcv)

        if "bbands" in self.settings.indicators:
            indicators["bbands"] = self._calculate_bbands(ohlcv)

        if "obv" in self.settings.indicators:
            indicators["obv"] = self._calculate_obv(ohlcv)

        if "atr" in self.settings.indicators:
            indicators["atr"] = self._calculate_atr(ohlcv)

        if "ema" in self.settings.indicators:
            indicators["ema"] = self._calculate_ema(ohlcv)

        # Aggregate signals
        overall_trend, overall_strength, confidence = self._aggregate_signals(indicators)

        # Generate summaries
        simple_summary = self._generate_simple_summary(indicators, overall_trend)
        technical_summary = self._generate_technical_summary(indicators, overall_trend)

        analysis = TechnicalAnalysis(
            symbol=symbol,
            timestamp=datetime.now(UTC),
            indicators=indicators,
            overall_trend=overall_trend,
            overall_strength=overall_strength,
            confidence=confidence,
            simple_summary=simple_summary,
            technical_summary=technical_summary,
        )

        logger.info(
            "technical_analysis_complete",
            symbol=symbol,
            trend=overall_trend.value,
            strength=overall_strength.value,
            confidence=confidence,
        )

        return analysis

    def _calculate_rsi(self, ohlcv: pd.DataFrame) -> IndicatorResult:
        """Calculate RSI indicator."""
        rsi = ta.rsi(ohlcv["close"], length=self.settings.rsi_period)
        current_rsi = float(rsi.iloc[-1])

        # Determine signal
        if current_rsi > self.settings.rsi_overbought:
            signal = TrendDirection.BEARISH
            strength = SignalStrength.STRONG if current_rsi > 80 else SignalStrength.MODERATE
            simple = f"RSI is {current_rsi:.0f} — the market looks overheated. May be time to be cautious."
            technical = f"RSI({self.settings.rsi_period}) = {current_rsi:.1f}, overbought zone (>{self.settings.rsi_overbought})"
        elif current_rsi < self.settings.rsi_oversold:
            signal = TrendDirection.BULLISH
            strength = SignalStrength.STRONG if current_rsi < 20 else SignalStrength.MODERATE
            simple = f"RSI is {current_rsi:.0f} — the market looks oversold. Could be a buying opportunity."
            technical = f"RSI({self.settings.rsi_period}) = {current_rsi:.1f}, oversold zone (<{self.settings.rsi_oversold})"
        else:
            signal = TrendDirection.NEUTRAL
            strength = SignalStrength.WEAK
            simple = f"RSI is {current_rsi:.0f} — the market is balanced, no extreme conditions."
            technical = f"RSI({self.settings.rsi_period}) = {current_rsi:.1f}, neutral zone"

        return IndicatorResult(
            name="RSI",
            value=current_rsi,
            signal=signal,
            strength=strength,
            simple_explanation=simple,
            technical_explanation=technical,
        )

    def _calculate_macd(self, ohlcv: pd.DataFrame) -> IndicatorResult:
        """Calculate MACD indicator."""
        macd = ta.macd(
            ohlcv["close"],
            fast=self.settings.macd_fast,
            slow=self.settings.macd_slow,
            signal=self.settings.macd_signal,
        )

        macd_line = float(macd.iloc[-1, 0])  # MACD line
        signal_line = float(macd.iloc[-1, 1])  # Signal line
        histogram = float(macd.iloc[-1, 2])  # Histogram

        # Previous values for crossover detection
        prev_macd = float(macd.iloc[-2, 0])
        prev_signal = float(macd.iloc[-2, 1])

        # Detect crossovers
        bullish_cross = prev_macd <= prev_signal and macd_line > signal_line
        bearish_cross = prev_macd >= prev_signal and macd_line < signal_line

        if bullish_cross:
            signal = TrendDirection.BULLISH
            strength = SignalStrength.STRONG
            simple = "MACD just crossed up — momentum is shifting positive."
            technical = f"MACD bullish crossover: {macd_line:.4f} > Signal {signal_line:.4f}"
        elif bearish_cross:
            signal = TrendDirection.BEARISH
            strength = SignalStrength.STRONG
            simple = "MACD just crossed down — momentum is shifting negative."
            technical = f"MACD bearish crossover: {macd_line:.4f} < Signal {signal_line:.4f}"
        elif histogram > 0:
            signal = TrendDirection.BULLISH
            strength = SignalStrength.MODERATE if histogram > abs(macd_line) * 0.1 else SignalStrength.WEAK
            simple = "MACD is positive — buyers are in control for now."
            technical = f"MACD histogram positive: {histogram:.4f}"
        else:
            signal = TrendDirection.BEARISH
            strength = SignalStrength.MODERATE if abs(histogram) > abs(macd_line) * 0.1 else SignalStrength.WEAK
            simple = "MACD is negative — sellers are in control for now."
            technical = f"MACD histogram negative: {histogram:.4f}"

        return IndicatorResult(
            name="MACD",
            value={"macd": macd_line, "signal": signal_line, "histogram": histogram},
            signal=signal,
            strength=strength,
            simple_explanation=simple,
            technical_explanation=technical,
        )

    def _calculate_bbands(self, ohlcv: pd.DataFrame) -> IndicatorResult:
        """Calculate Bollinger Bands indicator."""
        bbands = ta.bbands(
            ohlcv["close"],
            length=self.settings.bbands_period,
            std=self.settings.bbands_std,
        )

        current_price = float(ohlcv["close"].iloc[-1])
        lower = float(bbands.iloc[-1, 0])  # BBL
        middle = float(bbands.iloc[-1, 1])  # BBM
        upper = float(bbands.iloc[-1, 2])  # BBU
        # bandwidth available in bbands.iloc[-1, 3] if needed

        # Position within bands (0 = lower, 1 = upper)
        position = (current_price - lower) / (upper - lower) if upper != lower else 0.5

        if position > 0.95:
            signal = TrendDirection.BEARISH
            strength = SignalStrength.STRONG
            simple = "Price is touching the upper band — may be overextended."
            technical = f"Price at {position:.0%} of Bollinger Bands, near upper band"
        elif position < 0.05:
            signal = TrendDirection.BULLISH
            strength = SignalStrength.STRONG
            simple = "Price is touching the lower band — may be oversold."
            technical = f"Price at {position:.0%} of Bollinger Bands, near lower band"
        elif position > 0.7:
            signal = TrendDirection.BULLISH
            strength = SignalStrength.MODERATE
            simple = "Price is in the upper range — showing strength."
            technical = f"Price at {position:.0%} of BB, above middle band"
        elif position < 0.3:
            signal = TrendDirection.BEARISH
            strength = SignalStrength.MODERATE
            simple = "Price is in the lower range — showing weakness."
            technical = f"Price at {position:.0%} of BB, below middle band"
        else:
            signal = TrendDirection.NEUTRAL
            strength = SignalStrength.WEAK
            simple = "Price is in the middle of the bands — balanced momentum."
            technical = f"Price at {position:.0%} of BB, near middle band"

        return IndicatorResult(
            name="Bollinger Bands",
            value={"lower": lower, "middle": middle, "upper": upper, "position": position},
            signal=signal,
            strength=strength,
            simple_explanation=simple,
            technical_explanation=technical,
        )

    def _calculate_obv(self, ohlcv: pd.DataFrame) -> IndicatorResult:
        """Calculate On-Balance Volume indicator."""
        obv = ta.obv(ohlcv["close"], ohlcv["volume"])
        current_obv = float(obv.iloc[-1])

        # Calculate OBV trend using EMA
        obv_ema = ta.ema(obv, length=20)
        obv_ema_value = float(obv_ema.iloc[-1])

        # OBV change over last 5 periods
        obv_5_ago = float(obv.iloc[-5]) if len(obv) >= 5 else current_obv
        obv_change = (current_obv - obv_5_ago) / abs(obv_5_ago) if obv_5_ago != 0 else 0

        if current_obv > obv_ema_value and obv_change > 0.01:
            signal = TrendDirection.BULLISH
            strength = SignalStrength.STRONG if obv_change > 0.05 else SignalStrength.MODERATE
            simple = "Volume is flowing in — money entering the market."
            technical = f"OBV above EMA(20), +{obv_change:.1%} over 5 periods"
        elif current_obv < obv_ema_value and obv_change < -0.01:
            signal = TrendDirection.BEARISH
            strength = SignalStrength.STRONG if obv_change < -0.05 else SignalStrength.MODERATE
            simple = "Volume is flowing out — money leaving the market."
            technical = f"OBV below EMA(20), {obv_change:.1%} over 5 periods"
        else:
            signal = TrendDirection.NEUTRAL
            strength = SignalStrength.WEAK
            simple = "Volume is stable — no clear money flow direction."
            technical = f"OBV near EMA(20), {obv_change:+.1%} change"

        return IndicatorResult(
            name="OBV",
            value=current_obv,
            signal=signal,
            strength=strength,
            simple_explanation=simple,
            technical_explanation=technical,
        )

    def _calculate_atr(self, ohlcv: pd.DataFrame) -> IndicatorResult:
        """Calculate Average True Range indicator."""
        atr = ta.atr(ohlcv["high"], ohlcv["low"], ohlcv["close"], length=14)
        current_atr = float(atr.iloc[-1])
        current_price = float(ohlcv["close"].iloc[-1])

        # ATR as percentage of price
        atr_pct = current_atr / current_price

        # Compare to historical ATR
        avg_atr = float(atr.mean())
        atr_ratio = current_atr / avg_atr if avg_atr > 0 else 1.0

        if atr_ratio > 1.5:
            signal = TrendDirection.NEUTRAL  # High volatility is not directional
            strength = SignalStrength.STRONG
            simple = f"Market is very volatile — moves of ${current_atr:.2f} ({atr_pct:.1%}) are normal right now."
            technical = f"ATR(14) = {current_atr:.2f} ({atr_pct:.2%}), {atr_ratio:.1f}x average"
        elif atr_ratio < 0.5:
            signal = TrendDirection.NEUTRAL
            strength = SignalStrength.WEAK
            simple = f"Market is very calm — volatility is low with ${current_atr:.2f} typical moves."
            technical = f"ATR(14) = {current_atr:.2f} ({atr_pct:.2%}), {atr_ratio:.1f}x average (compressed)"
        else:
            signal = TrendDirection.NEUTRAL
            strength = SignalStrength.MODERATE
            simple = f"Volatility is normal — expect moves around ${current_atr:.2f}."
            technical = f"ATR(14) = {current_atr:.2f} ({atr_pct:.2%}), normal range"

        return IndicatorResult(
            name="ATR",
            value={"atr": current_atr, "atr_pct": atr_pct, "ratio": atr_ratio},
            signal=signal,
            strength=strength,
            simple_explanation=simple,
            technical_explanation=technical,
        )

    def _calculate_ema(self, ohlcv: pd.DataFrame) -> IndicatorResult:
        """Calculate EMA crossover signals."""
        current_price = float(ohlcv["close"].iloc[-1])
        emas: dict[int, float] = {}

        for period in self.settings.ema_periods:
            # Skip EMAs that require more data than available
            if period > len(ohlcv):
                continue
            ema = ta.ema(ohlcv["close"], length=period)
            if ema is not None and len(ema) > 0 and not pd.isna(ema.iloc[-1]):
                emas[period] = float(ema.iloc[-1])

        # Check EMA alignment (bullish = shorter above longer)
        # Only check alignment for EMAs we actually calculated
        available_periods = sorted([p for p in self.settings.ema_periods if p in emas])
        bullish_alignment = 0
        bearish_alignment = 0

        for i in range(len(available_periods) - 1):
            shorter = available_periods[i]
            longer = available_periods[i + 1]
            if emas[shorter] > emas[longer]:
                bullish_alignment += 1
            else:
                bearish_alignment += 1

        num_period_pairs = max(1, len(available_periods) - 1)

        # Price position relative to EMAs
        above_count = sum(1 for v in emas.values() if current_price > v)
        total_emas = len(emas)

        if bullish_alignment == num_period_pairs and above_count == total_emas and total_emas > 0:
            signal = TrendDirection.BULLISH
            strength = SignalStrength.STRONG
            simple = "All moving averages are aligned upward — strong uptrend."
            technical = "Price above all EMAs, perfect bullish alignment"
        elif bearish_alignment == num_period_pairs and above_count == 0 and total_emas > 0:
            signal = TrendDirection.BEARISH
            strength = SignalStrength.STRONG
            simple = "All moving averages are aligned downward — strong downtrend."
            technical = "Price below all EMAs, perfect bearish alignment"
        elif above_count > total_emas // 2:
            signal = TrendDirection.BULLISH
            strength = SignalStrength.MODERATE
            simple = "Price is above most moving averages — generally bullish."
            technical = f"Price above {above_count}/{total_emas} EMAs"
        elif above_count < total_emas // 2:
            signal = TrendDirection.BEARISH
            strength = SignalStrength.MODERATE
            simple = "Price is below most moving averages — generally bearish."
            technical = f"Price below {total_emas - above_count}/{total_emas} EMAs"
        else:
            signal = TrendDirection.NEUTRAL
            strength = SignalStrength.WEAK
            simple = "Mixed signals from moving averages — no clear trend."
            technical = f"Price mixed vs EMAs ({above_count}/{total_emas} above)"

        return IndicatorResult(
            name="EMA",
            value=emas,
            signal=signal,
            strength=strength,
            simple_explanation=simple,
            technical_explanation=technical,
        )

    def _aggregate_signals(
        self, indicators: dict[str, IndicatorResult]
    ) -> tuple[TrendDirection, SignalStrength, float]:
        """Aggregate all indicator signals into overall assessment."""
        if not indicators:
            return TrendDirection.NEUTRAL, SignalStrength.NONE, 0.0

        # Weight signals by strength
        strength_weights = {
            SignalStrength.STRONG: 3,
            SignalStrength.MODERATE: 2,
            SignalStrength.WEAK: 1,
            SignalStrength.NONE: 0,
        }

        bullish_score = 0
        bearish_score = 0
        neutral_score = 0
        total_weight = 0

        for result in indicators.values():
            weight = strength_weights[result.strength]
            total_weight += weight

            if result.signal == TrendDirection.BULLISH:
                bullish_score += weight
            elif result.signal == TrendDirection.BEARISH:
                bearish_score += weight
            else:
                neutral_score += weight

        if total_weight == 0:
            return TrendDirection.NEUTRAL, SignalStrength.NONE, 0.0

        # Determine overall trend
        if bullish_score > bearish_score and bullish_score > neutral_score:
            overall_trend = TrendDirection.BULLISH
            dominant_score = bullish_score
        elif bearish_score > bullish_score and bearish_score > neutral_score:
            overall_trend = TrendDirection.BEARISH
            dominant_score = bearish_score
        else:
            overall_trend = TrendDirection.NEUTRAL
            dominant_score = neutral_score

        # Calculate confidence (0-1)
        confidence = dominant_score / total_weight

        # Determine overall strength
        if confidence > 0.7:
            overall_strength = SignalStrength.STRONG
        elif confidence > 0.4:
            overall_strength = SignalStrength.MODERATE
        elif confidence > 0.2:
            overall_strength = SignalStrength.WEAK
        else:
            overall_strength = SignalStrength.NONE

        return overall_trend, overall_strength, confidence

    def _generate_simple_summary(
        self, indicators: dict[str, IndicatorResult], trend: TrendDirection
    ) -> str:
        """Generate a beginner-friendly summary."""
        if trend == TrendDirection.BULLISH:
            base = "The market looks positive."
        elif trend == TrendDirection.BEARISH:
            base = "The market looks cautious."
        else:
            base = "The market is balanced."

        # Add key insight from strongest indicator
        strongest: IndicatorResult | None = None
        for result in indicators.values():
            if strongest is None or (
                result.strength.value < (strongest.strength.value if strongest else "none")
            ):
                strongest = result

        if strongest and strongest.simple_explanation:
            return f"{base} {strongest.simple_explanation}"

        return base

    def _generate_technical_summary(
        self, indicators: dict[str, IndicatorResult], trend: TrendDirection
    ) -> str:
        """Generate a technical summary."""
        parts = [f"Trend: {trend.value.upper()}"]

        for name, result in indicators.items():
            if result.strength in (SignalStrength.STRONG, SignalStrength.MODERATE):
                parts.append(f"{name}: {result.signal.value} ({result.strength.value})")

        return " | ".join(parts)

    def get_indicator_help(self, indicator_name: str) -> dict[str, str] | None:
        """Get help text for an indicator from the glossary."""
        return get_term(indicator_name.lower())


# Global instance
_analyzer: TechnicalAnalyzer | None = None


def get_technical_analyzer() -> TechnicalAnalyzer:
    """Get the global technical analyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = TechnicalAnalyzer()
    return _analyzer
