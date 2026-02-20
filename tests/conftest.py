"""Shared pytest fixtures."""

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
    # Force paper mode for tests
    os.environ["KERYXFLOW_MODE"] = "paper"

    # Reset global instances before each test
    import keryxflow.aegis.risk as risk_module
    import keryxflow.agent.cognitive as cognitive_module
    import keryxflow.agent.executor as executor_module
    import keryxflow.agent.reflection as reflection_module
    import keryxflow.agent.scheduler as scheduler_module
    import keryxflow.agent.session as session_module
    import keryxflow.agent.strategy as strategy_module
    import keryxflow.agent.tools as tools_module
    import keryxflow.config as config_module
    import keryxflow.core.database as db_module
    import keryxflow.core.events as events_module
    import keryxflow.exchange.demo as demo_module
    import keryxflow.exchange.kraken as kraken_module
    import keryxflow.exchange.okx as okx_module
    import keryxflow.exchange.paper as paper_module
    import keryxflow.memory.episodic as episodic_module
    import keryxflow.memory.manager as manager_module
    import keryxflow.memory.semantic as semantic_module

    config_module._settings = None
    db_module._engine = None
    db_module._async_session_factory = None
    events_module._event_bus = None
    demo_module._demo_client = None
    kraken_module._kraken_client = None
    okx_module._okx_client = None
    paper_module._paper_engine = None
    episodic_module._episodic_memory = None
    semantic_module._semantic_memory = None
    manager_module._memory_manager = None
    tools_module._toolkit = None
    executor_module._executor = None
    cognitive_module._agent = None
    reflection_module._reflection_engine = None
    scheduler_module._scheduler = None
    session_module._session = None
    strategy_module._strategy_manager = None
    risk_module._risk_manager = None

    yield

    # Cleanup
    import contextlib

    if db_path.exists():
        with contextlib.suppress(PermissionError):
            db_path.unlink()


@pytest_asyncio.fixture
async def init_db():
    """Initialize the database tables."""
    from keryxflow.core.database import init_db as _init_db

    await _init_db()


@pytest_asyncio.fixture
async def db_session(init_db):
    """Get an async database session for testing."""
    from keryxflow.core.database import get_session_factory

    async_session = get_session_factory()
    async with async_session() as session:
        yield session


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
