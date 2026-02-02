"""Data loading utilities for backtesting."""

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from keryxflow.core.logging import get_logger
from keryxflow.exchange.client import ExchangeClient

logger = get_logger(__name__)


class DataLoader:
    """Loads historical OHLCV data for backtesting."""

    REQUIRED_COLUMNS = ["datetime", "open", "high", "low", "close", "volume"]

    def __init__(self, exchange_client: ExchangeClient | None = None):
        """Initialize the data loader."""
        self.exchange = exchange_client

    async def load_from_exchange(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1h",
    ) -> pd.DataFrame:
        """
        Load historical OHLCV data from exchange.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
            start: Start datetime (UTC)
            end: End datetime (UTC)
            timeframe: Candle timeframe (e.g., "1m", "1h", "1d")

        Returns:
            DataFrame with OHLCV data
        """
        if self.exchange is None:
            raise ValueError("Exchange client required for loading from exchange")

        logger.info(
            "loading_historical_data",
            symbol=symbol,
            start=start.isoformat(),
            end=end.isoformat(),
            timeframe=timeframe,
        )

        # Fetch OHLCV data
        all_candles = []
        current_start = start

        while current_start < end:
            candles = await self.exchange.get_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                since=int(current_start.timestamp() * 1000),
                limit=1000,
            )

            if not candles:
                break

            all_candles.extend(candles)

            # Move to next batch
            last_timestamp = candles[-1][0]
            current_start = datetime.fromtimestamp(last_timestamp / 1000, tz=UTC)

            # Avoid infinite loop
            if len(candles) < 1000:
                break

        if not all_candles:
            raise ValueError(f"No data found for {symbol} in specified range")

        # Convert to DataFrame
        df = pd.DataFrame(
            all_candles,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )

        # Convert timestamp to datetime
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.drop(columns=["timestamp"])

        # Filter to requested range
        df = df[(df["datetime"] >= start) & (df["datetime"] <= end)]

        # Sort and reset index
        df = df.sort_values("datetime").reset_index(drop=True)

        logger.info("data_loaded", symbol=symbol, candles=len(df))

        return df

    def load_from_csv(self, path: str | Path) -> pd.DataFrame:
        """
        Load OHLCV data from CSV file.

        Expected CSV format:
        datetime,open,high,low,close,volume
        2024-01-01 00:00:00,42000.0,42100.0,41900.0,42050.0,100.5

        Args:
            path: Path to CSV file

        Returns:
            DataFrame with OHLCV data
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {path}")

        logger.info("loading_csv", path=str(path))

        df = pd.read_csv(path)

        # Validate columns
        if not self.validate_data(df):
            raise ValueError(f"Invalid CSV format. Required columns: {self.REQUIRED_COLUMNS}")

        # Parse datetime
        df["datetime"] = pd.to_datetime(df["datetime"], utc=True)

        # Sort and reset index
        df = df.sort_values("datetime").reset_index(drop=True)

        logger.info("csv_loaded", candles=len(df))

        return df

    def validate_data(self, df: pd.DataFrame) -> bool:
        """
        Validate that DataFrame has required OHLCV columns.

        Args:
            df: DataFrame to validate

        Returns:
            True if valid, False otherwise
        """
        # Check required columns exist
        missing = set(self.REQUIRED_COLUMNS) - set(df.columns)
        if missing:
            logger.warning("missing_columns", columns=list(missing))
            return False

        # Check for null values in required columns
        for col in self.REQUIRED_COLUMNS:
            if df[col].isna().any():
                logger.warning("null_values_found", column=col)
                return False

        # Check numeric columns are valid
        numeric_cols = ["open", "high", "low", "close", "volume"]
        for col in numeric_cols:
            if not pd.api.types.is_numeric_dtype(df[col]):
                logger.warning("non_numeric_column", column=col)
                return False

        return True

    def resample(
        self,
        df: pd.DataFrame,
        target_timeframe: str,
    ) -> pd.DataFrame:
        """
        Resample OHLCV data to a different timeframe.

        Args:
            df: Source DataFrame
            target_timeframe: Target timeframe (e.g., "1h", "4h", "1d")

        Returns:
            Resampled DataFrame
        """
        # Set datetime as index
        df = df.set_index("datetime")

        # Resample
        resampled = df.resample(target_timeframe).agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )

        # Drop any rows with NaN (incomplete candles)
        resampled = resampled.dropna()

        # Reset index
        resampled = resampled.reset_index()

        return resampled
