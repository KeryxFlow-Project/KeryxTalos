"""Shared pytest fixtures."""

import asyncio
import os

import pytest
import pytest_asyncio


@pytest.fixture(autouse=True)
def setup_test_database(tmp_path):
    """Set up a fresh test database for each test."""
    # Create a unique temp database for this test
    db_path = tmp_path / "test_keryxflow.db"
    # KERYXFLOW_DB_ prefix + url field
    os.environ["KERYXFLOW_DB_URL"] = f"sqlite+aiosqlite:///{db_path}"

    # Reset global instances before each test
    import keryxflow.config as config_module
    import keryxflow.core.database as db_module
    import keryxflow.core.events as events_module
    import keryxflow.exchange.paper as paper_module

    config_module._settings = None
    db_module._engine = None
    db_module._async_session_factory = None
    events_module._event_bus = None
    paper_module._paper_engine = None

    yield

    # Cleanup
    if db_path.exists():
        try:
            db_path.unlink()
        except PermissionError:
            pass  # May be locked on Windows


@pytest_asyncio.fixture
async def init_db():
    """Initialize the database tables."""
    from keryxflow.core.database import init_db as _init_db
    await _init_db()


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
