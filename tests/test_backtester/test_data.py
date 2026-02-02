"""Tests for backtester data loading."""

import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from keryxflow.backtester.data import DataLoader


class TestDataLoader:
    """Tests for DataLoader."""

    def test_init_without_exchange(self):
        """Test initialization without exchange client."""
        loader = DataLoader()
        assert loader.exchange is None

    def test_validate_data_valid(self):
        """Test validation with valid data."""
        loader = DataLoader()

        df = pd.DataFrame(
            {
                "datetime": [datetime.now(UTC)],
                "open": [100.0],
                "high": [105.0],
                "low": [95.0],
                "close": [102.0],
                "volume": [1000.0],
            }
        )

        assert loader.validate_data(df) is True

    def test_validate_data_missing_columns(self):
        """Test validation with missing columns."""
        loader = DataLoader()

        df = pd.DataFrame(
            {
                "datetime": [datetime.now(UTC)],
                "open": [100.0],
                "close": [102.0],
            }
        )

        assert loader.validate_data(df) is False

    def test_validate_data_null_values(self):
        """Test validation with null values."""
        loader = DataLoader()

        df = pd.DataFrame(
            {
                "datetime": [datetime.now(UTC), datetime.now(UTC)],
                "open": [100.0, None],
                "high": [105.0, 106.0],
                "low": [95.0, 94.0],
                "close": [102.0, 103.0],
                "volume": [1000.0, 1100.0],
            }
        )

        assert loader.validate_data(df) is False

    def test_validate_data_non_numeric(self):
        """Test validation with non-numeric data."""
        loader = DataLoader()

        df = pd.DataFrame(
            {
                "datetime": [datetime.now(UTC)],
                "open": ["one hundred"],
                "high": [105.0],
                "low": [95.0],
                "close": [102.0],
                "volume": [1000.0],
            }
        )

        assert loader.validate_data(df) is False

    def test_load_from_csv(self):
        """Test loading from CSV file."""
        loader = DataLoader()

        # Create temp CSV
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("datetime,open,high,low,close,volume\n")
            f.write("2024-01-01 00:00:00,100.0,105.0,95.0,102.0,1000.0\n")
            f.write("2024-01-01 01:00:00,102.0,108.0,100.0,106.0,1200.0\n")
            temp_path = f.name

        try:
            df = loader.load_from_csv(temp_path)

            assert len(df) == 2
            assert "datetime" in df.columns
            assert "open" in df.columns
            assert "close" in df.columns
            assert df["open"].iloc[0] == 100.0
        finally:
            Path(temp_path).unlink()

    def test_load_from_csv_not_found(self):
        """Test loading from non-existent CSV."""
        loader = DataLoader()

        with pytest.raises(FileNotFoundError):
            loader.load_from_csv("/nonexistent/path.csv")

    def test_load_from_csv_invalid_format(self):
        """Test loading from invalid CSV."""
        loader = DataLoader()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("col1,col2\n")
            f.write("a,b\n")
            temp_path = f.name

        try:
            with pytest.raises(ValueError):
                loader.load_from_csv(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_resample(self):
        """Test resampling to different timeframe."""
        loader = DataLoader()

        # Create hourly data
        dates = pd.date_range("2024-01-01", periods=24, freq="h", tz=UTC)
        df = pd.DataFrame(
            {
                "datetime": dates,
                "open": [100 + i for i in range(24)],
                "high": [105 + i for i in range(24)],
                "low": [95 + i for i in range(24)],
                "close": [102 + i for i in range(24)],
                "volume": [1000 + i * 10 for i in range(24)],
            }
        )

        # Resample to 4h
        resampled = loader.resample(df, "4h")

        assert len(resampled) == 6  # 24h / 4h = 6 candles
        assert resampled["open"].iloc[0] == 100  # First open
        assert resampled["close"].iloc[0] == 105  # Last close of first 4h


class TestDataLoaderExchange:
    """Tests for exchange data loading (requires mocking)."""

    @pytest.mark.asyncio
    async def test_load_from_exchange_no_client(self):
        """Test loading without exchange client raises error."""
        loader = DataLoader()

        with pytest.raises(ValueError, match="Exchange client required"):
            await loader.load_from_exchange(
                symbol="BTC/USDT",
                start=datetime(2024, 1, 1, tzinfo=UTC),
                end=datetime(2024, 1, 2, tzinfo=UTC),
            )
