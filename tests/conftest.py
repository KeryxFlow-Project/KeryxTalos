"""Shared pytest fixtures."""

import pytest


@pytest.fixture
def sample_ohlcv_data():
    """Sample OHLCV data for testing."""
    return [
        [1704067200000, 42000.0, 42500.0, 41800.0, 42200.0, 1000.0],
        [1704070800000, 42200.0, 42800.0, 42100.0, 42600.0, 1200.0],
        [1704074400000, 42600.0, 43000.0, 42400.0, 42900.0, 1500.0],
        [1704078000000, 42900.0, 43200.0, 42700.0, 43100.0, 1100.0],
        [1704081600000, 43100.0, 43500.0, 42900.0, 43300.0, 1300.0],
    ]


@pytest.fixture
def sample_balance():
    """Sample balance for testing."""
    return {
        "total": {"USDT": 10000.0, "BTC": 0.1},
        "free": {"USDT": 9000.0, "BTC": 0.05},
        "used": {"USDT": 1000.0, "BTC": 0.05},
    }
