"""Tests for the trading engine."""


import pytest

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
