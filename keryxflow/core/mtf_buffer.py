"""Multi-Timeframe OHLCV Buffer for managing candles across multiple timeframes."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pandas as pd


@dataclass
class TimeframeConfig:
    """Configuration for a single timeframe."""

    timeframe: str  # "1m", "5m", "15m", "1h", "4h", "1d"
    interval_seconds: int  # 60, 300, 900, 3600, 14400, 86400
    max_candles: int = 100
    is_primary: bool = False  # Timeframe used for entry signals
    is_filter: bool = False  # Timeframe used for trend filtering


# Mapping from timeframe string to seconds
TIMEFRAME_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "6h": 21600,
    "8h": 28800,
    "12h": 43200,
    "1d": 86400,
    "1w": 604800,
}


def timeframe_to_seconds(timeframe: str) -> int:
    """Convert timeframe string to seconds."""
    if timeframe in TIMEFRAME_SECONDS:
        return TIMEFRAME_SECONDS[timeframe]

    # Parse custom timeframes like "2h", "15m"
    unit = timeframe[-1]
    value = int(timeframe[:-1])

    multipliers = {"m": 60, "h": 3600, "d": 86400, "w": 604800}
    if unit in multipliers:
        return value * multipliers[unit]

    raise ValueError(f"Unknown timeframe format: {timeframe}")


def get_candle_time(dt: datetime, interval_seconds: int) -> datetime:
    """Get the candle start time for a given datetime and interval."""
    timestamp = dt.timestamp()
    candle_timestamp = (timestamp // interval_seconds) * interval_seconds
    return datetime.fromtimestamp(candle_timestamp, tz=UTC)


@dataclass
class TimeframeBuffer:
    """Buffer for a single timeframe."""

    config: TimeframeConfig
    candles: list[dict[str, Any]] = field(default_factory=list)
    current_candle: dict[str, Any] | None = None
    last_candle_time: datetime | None = None

    def add_price(self, price: float, volume: float = 0.0) -> bool:
        """
        Add a price update to the buffer.

        Returns True if a new candle was completed.
        """
        now = datetime.now(UTC)
        candle_time = get_candle_time(now, self.config.interval_seconds)
        completed = False

        # Check if we need to start a new candle
        if self.last_candle_time != candle_time:
            # Save previous candle if exists
            if self.current_candle is not None:
                self.candles.append(self.current_candle)
                # Keep only max_candles
                if len(self.candles) > self.config.max_candles:
                    self.candles = self.candles[-self.config.max_candles :]
                completed = len(self.candles) > 0

            # Start new candle
            self.current_candle = {
                "timestamp": candle_time,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume,
            }
            self.last_candle_time = candle_time
            return completed

        # Update current candle
        if self.current_candle is not None:
            self.current_candle["high"] = max(self.current_candle["high"], price)
            self.current_candle["low"] = min(self.current_candle["low"], price)
            self.current_candle["close"] = price
            self.current_candle["volume"] += volume

        return False

    def add_candle(
        self,
        timestamp: int | float | datetime,
        open_price: float,
        high: float,
        low: float,
        close: float,
        volume: float,
    ) -> None:
        """Add a historical candle directly to the buffer."""
        # Convert timestamp (ms) to datetime
        if isinstance(timestamp, int | float):
            candle_time = datetime.fromtimestamp(timestamp / 1000, tz=UTC)
        else:
            candle_time = timestamp

        candle = {
            "timestamp": candle_time,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }

        self.candles.append(candle)

        # Keep only max_candles
        if len(self.candles) > self.config.max_candles:
            self.candles = self.candles[-self.config.max_candles :]

    def get_dataframe(self, include_current: bool = True) -> pd.DataFrame | None:
        """Get OHLCV DataFrame."""
        all_candles = self.candles.copy()

        if include_current and self.current_candle is not None:
            all_candles.append(self.current_candle)

        if not all_candles:
            return None

        df = pd.DataFrame(all_candles)
        df = df.rename(columns={"timestamp": "datetime"})
        return df

    def candle_count(self) -> int:
        """Get number of completed candles."""
        return len(self.candles)


class MultiTimeframeBuffer:
    """
    Buffer that manages OHLCV candles for multiple timeframes.

    Supports:
    - Adding prices that update all timeframes
    - Adding candles directly to specific timeframes
    - Resampling from lower to higher timeframes
    - Retrieving data for analysis
    """

    def __init__(self, configs: list[TimeframeConfig]):
        """
        Initialize the multi-timeframe buffer.

        Args:
            configs: List of timeframe configurations
        """
        self._configs = {c.timeframe: c for c in configs}
        self._buffers: dict[str, dict[str, TimeframeBuffer]] = defaultdict(dict)

        # Validate configs
        primary_count = sum(1 for c in configs if c.is_primary)
        filter_count = sum(1 for c in configs if c.is_filter)

        if primary_count > 1:
            raise ValueError("Only one primary timeframe allowed")
        if filter_count > 1:
            raise ValueError("Only one filter timeframe allowed")

        # Sort timeframes by interval (smallest first)
        self._sorted_timeframes = sorted(configs, key=lambda c: c.interval_seconds)

    @property
    def primary_timeframe(self) -> str | None:
        """Get the primary timeframe string."""
        for tf, config in self._configs.items():
            if config.is_primary:
                return tf
        return None

    @property
    def filter_timeframe(self) -> str | None:
        """Get the filter timeframe string."""
        for tf, config in self._configs.items():
            if config.is_filter:
                return tf
        return None

    @property
    def timeframes(self) -> list[str]:
        """Get list of all configured timeframes."""
        return list(self._configs.keys())

    def _get_or_create_buffer(self, symbol: str, timeframe: str) -> TimeframeBuffer:
        """Get or create a buffer for a symbol/timeframe pair."""
        if timeframe not in self._configs:
            raise ValueError(f"Timeframe {timeframe} not configured")

        if timeframe not in self._buffers[symbol]:
            self._buffers[symbol][timeframe] = TimeframeBuffer(config=self._configs[timeframe])

        return self._buffers[symbol][timeframe]

    def add_price(self, symbol: str, price: float, volume: float = 0.0) -> dict[str, bool]:
        """
        Add a price update that propagates to all timeframes.

        Args:
            symbol: Trading pair symbol
            price: Current price
            volume: Trade volume

        Returns:
            Dict mapping timeframe to whether a new candle was completed
        """
        results = {}

        for tf in self._configs:
            buffer = self._get_or_create_buffer(symbol, tf)
            completed = buffer.add_price(price, volume)
            results[tf] = completed

        return results

    def add_candle(
        self,
        symbol: str,
        timeframe: str,
        timestamp: int | float | datetime,
        open_price: float,
        high: float,
        low: float,
        close: float,
        volume: float,
    ) -> None:
        """
        Add a historical candle to a specific timeframe.

        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe string (e.g., "1h", "4h")
            timestamp: Candle timestamp (ms since epoch or datetime)
            open_price: Open price
            high: High price
            low: Low price
            close: Close price
            volume: Volume
        """
        buffer = self._get_or_create_buffer(symbol, timeframe)
        buffer.add_candle(timestamp, open_price, high, low, close, volume)

    def get_ohlcv(self, symbol: str, timeframe: str) -> pd.DataFrame | None:
        """
        Get OHLCV DataFrame for a specific symbol and timeframe.

        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe string

        Returns:
            DataFrame with columns: datetime, open, high, low, close, volume
        """
        if symbol not in self._buffers or timeframe not in self._buffers[symbol]:
            return None

        return self._buffers[symbol][timeframe].get_dataframe()

    def get_all_ohlcv(self, symbol: str) -> dict[str, pd.DataFrame]:
        """
        Get OHLCV DataFrames for all timeframes of a symbol.

        Args:
            symbol: Trading pair symbol

        Returns:
            Dict mapping timeframe to DataFrame
        """
        result = {}

        for timeframe in self._configs:
            df = self.get_ohlcv(symbol, timeframe)
            if df is not None and len(df) > 0:
                result[timeframe] = df

        return result

    def candle_count(self, symbol: str, timeframe: str) -> int:
        """Get number of completed candles for a symbol/timeframe."""
        if symbol not in self._buffers or timeframe not in self._buffers[symbol]:
            return 0

        return self._buffers[symbol][timeframe].candle_count()

    def has_minimum_candles(self, symbol: str, min_candles: int = 50) -> dict[str, bool]:
        """
        Check if each timeframe has minimum required candles.

        Args:
            symbol: Trading pair symbol
            min_candles: Minimum candles required

        Returns:
            Dict mapping timeframe to whether minimum is met
        """
        result = {}

        for timeframe in self._configs:
            count = self.candle_count(symbol, timeframe)
            result[timeframe] = count >= min_candles

        return result

    def resample_from_base(
        self,
        symbol: str,
        base_df: pd.DataFrame,
        base_timeframe: str = "1m",
    ) -> None:
        """
        Resample a base DataFrame to populate higher timeframes.

        Args:
            symbol: Trading pair symbol
            base_df: DataFrame with base timeframe data
            base_timeframe: Timeframe of the base data
        """
        base_seconds = timeframe_to_seconds(base_timeframe)

        for tf, config in self._configs.items():
            if config.interval_seconds <= base_seconds:
                # Skip same or lower timeframes
                continue

            # Resample using pandas
            resampled = self._resample_df(base_df, tf)

            # Add candles to buffer
            buffer = self._get_or_create_buffer(symbol, tf)
            for _, row in resampled.iterrows():
                buffer.add_candle(
                    timestamp=row["datetime"],
                    open_price=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    volume=row["volume"],
                )

    def _resample_df(self, df: pd.DataFrame, target_timeframe: str) -> pd.DataFrame:
        """
        Resample a DataFrame to a higher timeframe.

        Args:
            df: Source DataFrame with datetime column
            target_timeframe: Target timeframe string

        Returns:
            Resampled DataFrame
        """
        # Ensure datetime is index
        if "datetime" in df.columns:
            df = df.set_index("datetime")

        # Map timeframe to pandas resample string
        tf_map = {
            "1m": "1min",
            "5m": "5min",
            "15m": "15min",
            "30m": "30min",
            "1h": "1h",
            "2h": "2h",
            "4h": "4h",
            "6h": "6h",
            "8h": "8h",
            "12h": "12h",
            "1d": "1D",
            "1w": "1W",
        }

        resample_str = tf_map.get(target_timeframe, target_timeframe)

        resampled = df.resample(resample_str).agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )

        resampled = resampled.dropna()
        resampled = resampled.reset_index()
        resampled = resampled.rename(columns={"index": "datetime"})

        return resampled

    def clear(self, symbol: str | None = None) -> None:
        """
        Clear buffers.

        Args:
            symbol: If provided, clear only this symbol. Otherwise clear all.
        """
        if symbol is not None:
            if symbol in self._buffers:
                del self._buffers[symbol]
        else:
            self._buffers.clear()


def create_mtf_buffer_from_settings() -> MultiTimeframeBuffer:
    """
    Create a MultiTimeframeBuffer from application settings.

    Returns:
        Configured MultiTimeframeBuffer instance
    """
    from keryxflow.config import get_settings

    settings = get_settings()
    mtf_settings = settings.oracle.mtf

    configs = []
    for tf in mtf_settings.timeframes:
        interval = timeframe_to_seconds(tf)
        config = TimeframeConfig(
            timeframe=tf,
            interval_seconds=interval,
            max_candles=100,
            is_primary=(tf == mtf_settings.primary_timeframe),
            is_filter=(tf == mtf_settings.filter_timeframe),
        )
        configs.append(config)

    return MultiTimeframeBuffer(configs)
