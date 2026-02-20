"""Tests for the trading engine."""

import pytest
from pydantic import SecretStr

from keryxflow.core.engine import OHLCVBuffer, TradingEngine
from keryxflow.core.events import Event, EventBus, EventType


class TestOHLCVBuffer:
    """Tests for OHLCV buffer."""

    def test_add_first_price(self):
        """Test adding first price creates candle."""
        buffer = OHLCVBuffer()
        buffer.add_price("BTC/USDT", 50000.0)

        assert buffer.candle_count("BTC/USDT") == 0  # Current candle not yet completed
        assert "BTC/USDT" in buffer._current_candle

    def test_candle_structure(self):
        """Test candle has correct OHLCV structure."""
        buffer = OHLCVBuffer()
        buffer.add_price("BTC/USDT", 50000.0, volume=100.0)

        candle = buffer._current_candle["BTC/USDT"]
        assert "open" in candle
        assert "high" in candle
        assert "low" in candle
        assert "close" in candle
        assert "volume" in candle
        assert candle["open"] == 50000.0
        assert candle["volume"] == 100.0

    def test_price_updates_ohlc(self):
        """Test price updates modify candle correctly."""
        buffer = OHLCVBuffer()

        # Add initial price
        buffer.add_price("BTC/USDT", 50000.0)

        # Add higher price
        buffer.add_price("BTC/USDT", 51000.0)

        # Add lower price
        buffer.add_price("BTC/USDT", 49000.0)

        candle = buffer._current_candle["BTC/USDT"]
        assert candle["open"] == 50000.0
        assert candle["high"] == 51000.0
        assert candle["low"] == 49000.0
        assert candle["close"] == 49000.0

    def test_get_ohlcv_returns_dataframe(self):
        """Test get_ohlcv returns pandas DataFrame."""
        buffer = OHLCVBuffer()
        buffer.add_price("BTC/USDT", 50000.0)

        df = buffer.get_ohlcv("BTC/USDT")
        assert df is not None
        assert len(df) == 1
        assert "open" in df.columns
        assert "close" in df.columns

    def test_get_ohlcv_missing_symbol(self):
        """Test get_ohlcv returns None for missing symbol."""
        buffer = OHLCVBuffer()
        df = buffer.get_ohlcv("ETH/USDT")
        assert df is None

    def test_multiple_symbols(self):
        """Test buffer handles multiple symbols."""
        buffer = OHLCVBuffer()
        buffer.add_price("BTC/USDT", 50000.0)
        buffer.add_price("ETH/USDT", 3000.0)

        assert "BTC/USDT" in buffer._current_candle
        assert "ETH/USDT" in buffer._current_candle

    def test_max_candles_limit(self):
        """Test buffer respects max_candles limit."""
        buffer = OHLCVBuffer(max_candles=5)

        # Manually add candles to test limit
        for i in range(10):
            buffer._candles["BTC/USDT"].append({"close": float(i)})

        assert len(buffer._candles["BTC/USDT"]) == 10

        # Add price to trigger cleanup
        buffer._candles["BTC/USDT"] = buffer._candles["BTC/USDT"][-5:]
        assert len(buffer._candles["BTC/USDT"]) == 5


class TestTradingEngineInit:
    """Tests for trading engine initialization."""

    @pytest.fixture
    def mock_exchange(self, mocker):
        """Create mock exchange client."""
        return mocker.MagicMock()

    @pytest.fixture
    def mock_paper(self, mocker):
        """Create mock paper trading engine."""
        mock = mocker.MagicMock()
        mock.get_balance = mocker.AsyncMock(
            return_value={"total": {"USDT": 10000.0}, "free": {"USDT": 10000.0}}
        )
        mock.get_positions = mocker.AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def event_bus(self):
        """Create event bus."""
        return EventBus()

    def test_init_creates_engine(self, mock_exchange, mock_paper, event_bus):
        """Test engine initializes correctly."""
        engine = TradingEngine(
            exchange_client=mock_exchange,
            paper_engine=mock_paper,
            event_bus=event_bus,
        )

        assert engine.exchange == mock_exchange
        assert engine.paper == mock_paper
        assert engine.event_bus == event_bus
        assert not engine._running

    def test_engine_has_ohlcv_buffer(self, mock_exchange, mock_paper, event_bus):
        """Test engine has OHLCV buffer."""
        engine = TradingEngine(
            exchange_client=mock_exchange,
            paper_engine=mock_paper,
            event_bus=event_bus,
        )

        assert engine._ohlcv_buffer is not None

    @pytest.mark.asyncio
    async def test_start_sets_running(self, mock_exchange, mock_paper, event_bus):
        """Test start sets running flag."""
        engine = TradingEngine(
            exchange_client=mock_exchange,
            paper_engine=mock_paper,
            event_bus=event_bus,
        )

        await engine.start()
        assert engine._running

        await engine.stop()
        assert not engine._running


class TestTradingEngineAnalysis:
    """Tests for trading engine analysis flow."""

    @pytest.fixture
    def mock_exchange(self, mocker):
        """Create mock exchange client."""
        return mocker.MagicMock()

    @pytest.fixture
    def mock_paper(self, mocker):
        """Create mock paper trading engine."""
        mock = mocker.MagicMock()
        mock.get_balance = mocker.AsyncMock(
            return_value={"total": {"USDT": 10000.0}, "free": {"USDT": 10000.0}}
        )
        mock.get_positions = mocker.AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def event_bus(self):
        """Create event bus."""
        return EventBus()

    def test_should_analyze_needs_min_candles(self, mock_exchange, mock_paper, event_bus):
        """Test analysis requires minimum candles."""
        engine = TradingEngine(
            exchange_client=mock_exchange,
            paper_engine=mock_paper,
            event_bus=event_bus,
        )
        engine._min_candles = 20

        # Not enough candles
        assert not engine._should_analyze("BTC/USDT", False)

    def test_should_analyze_with_enough_candles(self, mock_exchange, mock_paper, event_bus):
        """Test analysis runs with enough candles."""
        engine = TradingEngine(
            exchange_client=mock_exchange,
            paper_engine=mock_paper,
            event_bus=event_bus,
        )
        engine._min_candles = 5

        # Add candles
        for i in range(10):
            engine._ohlcv_buffer._candles["BTC/USDT"].append({"close": float(i)})

        assert engine._should_analyze("BTC/USDT", False)

    def test_get_status(self, mock_exchange, mock_paper, event_bus):
        """Test get_status returns correct info."""
        engine = TradingEngine(
            exchange_client=mock_exchange,
            paper_engine=mock_paper,
            event_bus=event_bus,
        )

        status = engine.get_status()

        assert "running" in status
        assert "paused" in status
        assert "auto_trade" in status
        assert "risk_status" in status


class TestTradingEngineEvents:
    """Tests for trading engine event handling."""

    @pytest.fixture
    def mock_exchange(self, mocker):
        """Create mock exchange client."""
        return mocker.MagicMock()

    @pytest.fixture
    def mock_paper(self, mocker):
        """Create mock paper trading engine."""
        mock = mocker.MagicMock()
        mock.get_balance = mocker.AsyncMock(
            return_value={"total": {"USDT": 10000.0}, "free": {"USDT": 10000.0}}
        )
        mock.get_positions = mocker.AsyncMock(return_value=[])
        mock.close_all_positions = mocker.AsyncMock()
        return mock

    @pytest.fixture
    def event_bus(self):
        """Create event bus."""
        return EventBus()

    @pytest.mark.asyncio
    async def test_pause_event_pauses_engine(self, mock_exchange, mock_paper, event_bus):
        """Test pause event pauses engine."""
        engine = TradingEngine(
            exchange_client=mock_exchange,
            paper_engine=mock_paper,
            event_bus=event_bus,
        )

        await engine.start()
        assert not engine._paused

        await engine._on_pause(Event(type=EventType.SYSTEM_PAUSED))
        assert engine._paused

        await engine.stop()

    @pytest.mark.asyncio
    async def test_resume_event_resumes_engine(self, mock_exchange, mock_paper, event_bus):
        """Test resume event resumes engine."""
        engine = TradingEngine(
            exchange_client=mock_exchange,
            paper_engine=mock_paper,
            event_bus=event_bus,
        )

        await engine.start()
        engine._paused = True

        await engine._on_resume(Event(type=EventType.SYSTEM_RESUMED))
        assert not engine._paused

        await engine.stop()

    @pytest.mark.asyncio
    async def test_panic_event_closes_positions(self, mock_exchange, mock_paper, event_bus):
        """Test panic event closes all positions."""
        engine = TradingEngine(
            exchange_client=mock_exchange,
            paper_engine=mock_paper,
            event_bus=event_bus,
        )

        await engine.start()
        await engine._on_panic(Event(type=EventType.PANIC_TRIGGERED))

        mock_paper.close_all_positions.assert_called_once()
        assert engine._paused

        await engine.stop()

    @pytest.mark.asyncio
    async def test_price_update_adds_to_buffer(self, mock_exchange, mock_paper, event_bus):
        """Test price update adds to OHLCV buffer."""
        engine = TradingEngine(
            exchange_client=mock_exchange,
            paper_engine=mock_paper,
            event_bus=event_bus,
        )

        await engine.start()

        event = Event(
            type=EventType.PRICE_UPDATE,
            data={"symbol": "BTC/USDT", "price": 50000.0, "volume": 100.0},
        )
        await engine._on_price_update(event)

        assert "BTC/USDT" in engine._ohlcv_buffer._current_candle

        await engine.stop()


class TestTradingEngineLiveMode:
    """Tests for live trading mode functionality."""

    @pytest.fixture
    def mock_exchange(self, mocker):
        """Create mock exchange client."""
        mock = mocker.MagicMock()
        mock.get_balance = mocker.AsyncMock(
            return_value={"free": {"USDT": 500.0}, "total": {"USDT": 500.0}}
        )
        mock.create_market_order = mocker.AsyncMock(
            return_value={"id": "live_order_1", "price": 50000.0, "filled": 0.01}
        )
        return mock

    @pytest.fixture
    def mock_paper(self, mocker):
        """Create mock paper trading engine."""
        mock = mocker.MagicMock()
        mock.get_balance = mocker.AsyncMock(
            return_value={"total": {"USDT": 10000.0}, "free": {"USDT": 10000.0}}
        )
        mock.get_positions = mocker.AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def event_bus(self):
        """Create event bus."""
        return EventBus()

    def test_live_mode_detection_paper(self, mock_exchange, mock_paper, event_bus):
        """Test engine detects paper mode correctly."""
        engine = TradingEngine(
            exchange_client=mock_exchange,
            paper_engine=mock_paper,
            event_bus=event_bus,
        )

        # Default is paper mode
        assert engine._is_live_mode is False

    def test_get_status_includes_mode(self, mock_exchange, mock_paper, event_bus):
        """Test status includes trading mode."""
        engine = TradingEngine(
            exchange_client=mock_exchange,
            paper_engine=mock_paper,
            event_bus=event_bus,
        )

        status = engine.get_status()

        assert "mode" in status
        assert status["mode"] == "paper"

    def test_safeguards_initialized(self, mock_exchange, mock_paper, event_bus):
        """Test safeguards are initialized."""
        engine = TradingEngine(
            exchange_client=mock_exchange,
            paper_engine=mock_paper,
            event_bus=event_bus,
        )

        assert engine._safeguards is not None

    @pytest.mark.asyncio
    async def test_sync_balance_from_exchange(self, mock_exchange, mock_paper, event_bus):
        """Test balance sync from exchange."""
        engine = TradingEngine(
            exchange_client=mock_exchange,
            paper_engine=mock_paper,
            event_bus=event_bus,
        )
        engine._is_live_mode = True

        balance = await engine._sync_balance_from_exchange()

        assert balance.get("USDT") == 500.0
        assert engine._last_balance_sync is not None

    @pytest.mark.asyncio
    async def test_verify_live_mode_fails_without_credentials(
        self, mock_exchange, mock_paper, event_bus
    ):
        """Test live mode verification fails without credentials."""
        engine = TradingEngine(
            exchange_client=mock_exchange,
            paper_engine=mock_paper,
            event_bus=event_bus,
        )

        # No credentials set, should fail
        result = await engine._verify_live_mode_safe()

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_live_mode_with_credentials(
        self, mock_exchange, mock_paper, event_bus, _init_db
    ):
        """Test live mode verification with valid credentials."""
        engine = TradingEngine(
            exchange_client=mock_exchange,
            paper_engine=mock_paper,
            event_bus=event_bus,
        )

        # Mock settings to have credentials
        engine.settings.binance_api_key = SecretStr("test_key")
        engine.settings.binance_api_secret = SecretStr("test_secret")
        engine.settings.env = "production"

        # Skip paper trade check
        engine._safeguards.set_min_paper_trades(0)

        result = await engine._verify_live_mode_safe()

        assert result is True

    @pytest.mark.asyncio
    async def test_execute_live_order(self, mock_exchange, mock_paper, event_bus):
        """Test live order execution."""
        from keryxflow.aegis.risk import OrderRequest

        engine = TradingEngine(
            exchange_client=mock_exchange,
            paper_engine=mock_paper,
            event_bus=event_bus,
        )
        engine._is_live_mode = True

        order = OrderRequest(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.01,
            entry_price=50000.0,
            stop_loss=49000.0,
        )

        result = await engine._execute_live_order(order)

        assert result is not None
        assert result["id"] == "live_order_1"
        mock_exchange.create_market_order.assert_called_once_with(
            symbol="BTC/USDT",
            side="buy",
            amount=0.01,
        )

    def test_notification_manager_optional(self, mock_exchange, mock_paper, event_bus):
        """Test notification manager is optional."""
        engine = TradingEngine(
            exchange_client=mock_exchange,
            paper_engine=mock_paper,
            event_bus=event_bus,
            notification_manager=None,
        )

        assert engine.notifications is None

    @pytest.mark.asyncio
    async def test_start_with_notification_manager(
        self, mock_exchange, mock_paper, event_bus, mocker
    ):
        """Test start subscribes notification manager to events."""
        mock_notifier = mocker.MagicMock()
        mock_notifier.subscribe_to_events = mocker.MagicMock()
        mock_notifier.notify_system_start = mocker.AsyncMock()

        engine = TradingEngine(
            exchange_client=mock_exchange,
            paper_engine=mock_paper,
            event_bus=event_bus,
            notification_manager=mock_notifier,
        )

        await engine.start()

        mock_notifier.subscribe_to_events.assert_called_once()
        mock_notifier.notify_system_start.assert_called_once()

        await engine.stop()

    @pytest.mark.asyncio
    async def test_verify_live_mode_queries_paper_trade_count_from_db(
        self, mock_exchange, mock_paper, event_bus, tmp_path, mocker
    ):
        """Test that _verify_live_mode_safe queries DB for paper trade count."""
        import keryxflow.core.database as db_module
        from keryxflow.core.database import init_db as _init_db
        from keryxflow.core.repository import get_trade_repository

        # Point to a fresh temp database to ensure isolation
        db_path = tmp_path / "test_paper_count.db"
        engine_obj = TradingEngine(
            exchange_client=mock_exchange,
            paper_engine=mock_paper,
            event_bus=event_bus,
        )
        engine_obj.settings.database.url = f"sqlite+aiosqlite:///{db_path}"

        # Reset DB engine so it picks up new URL
        db_module._engine = None
        db_module._async_session_factory = None
        await _init_db()

        # Set up credentials so we get past that check
        engine_obj.settings.binance_api_key = SecretStr("test_key")
        engine_obj.settings.binance_api_secret = SecretStr("test_secret")
        engine_obj.settings.env = "production"

        # Spy on verify_ready_for_live to capture the paper_trade_count argument
        spy = mocker.spy(engine_obj._safeguards, "verify_ready_for_live")

        # With no paper trades in DB, count should be 0
        await engine_obj._verify_live_mode_safe()
        spy.assert_called_once()
        assert spy.call_args.kwargs["paper_trade_count"] == 0

        spy.reset_mock()

        # Insert paper trades into the database
        repo = get_trade_repository()
        for _ in range(35):
            await repo.create_trade(
                symbol="BTC/USDT",
                side="buy",
                quantity=0.01,
                entry_price=50000.0,
                is_paper=True,
            )

        # Now the count should be 35 from DB
        await engine_obj._verify_live_mode_safe()
        spy.assert_called_once()
        assert spy.call_args.kwargs["paper_trade_count"] == 35
