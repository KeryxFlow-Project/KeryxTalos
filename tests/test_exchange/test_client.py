"""Tests for exchange client (CCXT wrapper)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import ccxt.async_support as ccxt
import pytest
from tenacity import RetryError

from keryxflow.exchange.client import ExchangeClient, get_exchange_client

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_exchange():
    """Create a mock CCXT exchange instance."""
    exchange = AsyncMock(spec=ccxt.binance)
    exchange.fetch_time = AsyncMock(return_value=1700000000000)
    exchange.close = AsyncMock()
    exchange.set_sandbox_mode = MagicMock()
    return exchange


@pytest.fixture
def client(mock_exchange):
    """Return a pre-connected ExchangeClient with mocked exchange."""
    c = ExchangeClient(sandbox=True)
    c._exchange = mock_exchange
    return c


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


class TestSingleton:
    """Tests for get_exchange_client() singleton."""

    def test_returns_same_instance(self):
        first = get_exchange_client()
        second = get_exchange_client()
        assert first is second

    def test_reset_via_conftest(self):
        """conftest resets _client to None; a new call should produce a fresh instance."""
        import keryxflow.exchange.client as mod

        inst = get_exchange_client()
        mod._client = None
        new_inst = get_exchange_client()
        assert new_inst is not inst


# ---------------------------------------------------------------------------
# Connect / Disconnect
# ---------------------------------------------------------------------------


class TestConnect:
    """Tests for connect() and disconnect()."""

    @patch("keryxflow.exchange.client.ccxt.binance")
    async def test_connect_sandbox(self, mock_binance_cls):
        mock_ex = AsyncMock()
        mock_ex.fetch_time = AsyncMock(return_value=1700000000000)
        mock_ex.set_sandbox_mode = MagicMock()
        mock_binance_cls.return_value = mock_ex

        c = ExchangeClient(sandbox=True)
        result = await c.connect()

        assert result is True
        assert c.is_connected
        mock_ex.set_sandbox_mode.assert_called_once_with(True)
        mock_ex.fetch_time.assert_awaited_once()

    @patch("keryxflow.exchange.client.ccxt.binance")
    async def test_connect_no_sandbox(self, mock_binance_cls):
        mock_ex = AsyncMock()
        mock_ex.fetch_time = AsyncMock(return_value=1700000000000)
        mock_binance_cls.return_value = mock_ex

        c = ExchangeClient(sandbox=False)
        result = await c.connect()

        assert result is True
        mock_ex.set_sandbox_mode.assert_not_called()

    @patch("keryxflow.exchange.client.ccxt.binance")
    async def test_connect_network_error(self, mock_binance_cls):
        mock_ex = AsyncMock()
        mock_ex.fetch_time = AsyncMock(side_effect=ccxt.NetworkError("timeout"))
        mock_binance_cls.return_value = mock_ex

        c = ExchangeClient(sandbox=True)
        result = await c.connect()

        assert result is False

    @patch("keryxflow.exchange.client.ccxt.binance")
    async def test_connect_exchange_error(self, mock_binance_cls):
        mock_ex = AsyncMock()
        mock_ex.fetch_time = AsyncMock(side_effect=ccxt.ExchangeError("bad key"))
        mock_binance_cls.return_value = mock_ex

        c = ExchangeClient(sandbox=True)
        result = await c.connect()

        assert result is False

    @patch("keryxflow.exchange.client.ccxt.binance")
    async def test_connect_generic_error(self, mock_binance_cls):
        mock_ex = AsyncMock()
        mock_ex.fetch_time = AsyncMock(side_effect=RuntimeError("boom"))
        mock_binance_cls.return_value = mock_ex

        c = ExchangeClient(sandbox=True)
        result = await c.connect()

        assert result is False

    async def test_disconnect(self, client, mock_exchange):
        await client.disconnect()

        mock_exchange.close.assert_awaited_once()
        assert client._exchange is None
        assert not client.is_connected

    async def test_disconnect_no_exchange(self):
        c = ExchangeClient(sandbox=True)
        await c.disconnect()  # should not raise


# ---------------------------------------------------------------------------
# Connection state helpers
# ---------------------------------------------------------------------------


class TestConnectionState:
    """Tests for is_connected and _ensure_connected."""

    def test_is_connected_true(self, client):
        assert client.is_connected is True

    def test_is_connected_false(self):
        c = ExchangeClient(sandbox=True)
        assert c.is_connected is False

    def test_ensure_connected_raises(self):
        c = ExchangeClient(sandbox=True)
        with pytest.raises(RuntimeError, match="Not connected"):
            c._ensure_connected()

    def test_ensure_connected_ok(self, client):
        client._ensure_connected()  # should not raise


# ---------------------------------------------------------------------------
# Data retrieval methods
# ---------------------------------------------------------------------------


class TestGetTicker:
    """Tests for get_ticker()."""

    async def test_success(self, client, mock_exchange):
        mock_exchange.fetch_ticker = AsyncMock(
            return_value={
                "symbol": "BTC/USDT",
                "last": 50000.0,
                "bid": 49990.0,
                "ask": 50010.0,
                "high": 51000.0,
                "low": 49000.0,
                "baseVolume": 1234.5,
                "quoteVolume": 61725000.0,
                "timestamp": 1700000000000,
                "datetime": "2023-11-14T22:13:20.000Z",
            }
        )

        ticker = await client.get_ticker("BTC/USDT")

        assert ticker["symbol"] == "BTC/USDT"
        assert ticker["last"] == 50000.0
        assert ticker["bid"] == 49990.0
        assert ticker["ask"] == 50010.0
        assert ticker["volume"] == 1234.5
        assert ticker["quote_volume"] == 61725000.0
        mock_exchange.fetch_ticker.assert_awaited_once_with("BTC/USDT")

    async def test_not_connected(self):
        c = ExchangeClient(sandbox=True)
        with pytest.raises((RuntimeError, RetryError)):
            await c.get_ticker("BTC/USDT")


class TestGetOHLCV:
    """Tests for get_ohlcv()."""

    @patch("keryxflow.exchange.client.ccxt.binance")
    async def test_sandbox_uses_temp_client(self, mock_binance_cls, client):
        """In sandbox mode, OHLCV fetches via a temporary non-sandbox client."""
        fake_ohlcv = [[1700000000000, 50000, 51000, 49000, 50500, 100]]
        temp_exchange = AsyncMock()
        temp_exchange.fetch_ohlcv = AsyncMock(return_value=fake_ohlcv)
        temp_exchange.close = AsyncMock()
        mock_binance_cls.return_value = temp_exchange

        result = await client.get_ohlcv("BTC/USDT", "1h", limit=50)

        assert result == fake_ohlcv
        temp_exchange.fetch_ohlcv.assert_awaited_once_with(
            "BTC/USDT",
            "1h",
            since=None,
            limit=50,
        )
        temp_exchange.close.assert_awaited_once()

    async def test_non_sandbox_uses_main_exchange(self, mock_exchange):
        fake_ohlcv = [[1700000000000, 50000, 51000, 49000, 50500, 100]]
        mock_exchange.fetch_ohlcv = AsyncMock(return_value=fake_ohlcv)

        c = ExchangeClient(sandbox=False)
        c._exchange = mock_exchange

        result = await c.get_ohlcv("BTC/USDT", "1h", limit=50)

        assert result == fake_ohlcv
        mock_exchange.fetch_ohlcv.assert_awaited_once_with(
            "BTC/USDT",
            "1h",
            since=None,
            limit=50,
        )

    async def test_with_since_param(self, mock_exchange):
        mock_exchange.fetch_ohlcv = AsyncMock(return_value=[])

        c = ExchangeClient(sandbox=False)
        c._exchange = mock_exchange

        await c.get_ohlcv("BTC/USDT", "1h", limit=10, since=1700000000000)
        mock_exchange.fetch_ohlcv.assert_awaited_once_with(
            "BTC/USDT",
            "1h",
            since=1700000000000,
            limit=10,
        )

    async def test_not_connected(self):
        c = ExchangeClient(sandbox=True)
        with pytest.raises((RuntimeError, RetryError)):
            await c.get_ohlcv("BTC/USDT")


class TestGetBalance:
    """Tests for get_balance()."""

    async def test_success(self, client, mock_exchange):
        mock_exchange.fetch_balance = AsyncMock(
            return_value={
                "total": {"USDT": 10000.0, "BTC": 0.5},
                "free": {"USDT": 9000.0, "BTC": 0.5},
                "used": {"USDT": 1000.0, "BTC": 0.0},
                "info": {},
            }
        )

        balance = await client.get_balance()

        assert balance["total"]["USDT"] == 10000.0
        assert balance["free"]["BTC"] == 0.5
        assert "info" not in balance

    async def test_not_connected(self):
        c = ExchangeClient(sandbox=True)
        with pytest.raises((RuntimeError, RetryError)):
            await c.get_balance()


class TestGetOrderBook:
    """Tests for get_order_book()."""

    async def test_success(self, client, mock_exchange):
        mock_exchange.fetch_order_book = AsyncMock(
            return_value={
                "bids": [[49990, 1.0], [49980, 2.0], [49970, 3.0]],
                "asks": [[50010, 1.0], [50020, 2.0], [50030, 3.0]],
                "timestamp": 1700000000000,
            }
        )

        book = await client.get_order_book("BTC/USDT", limit=2)

        assert book["symbol"] == "BTC/USDT"
        assert len(book["bids"]) == 2
        assert len(book["asks"]) == 2
        assert book["timestamp"] == 1700000000000
        mock_exchange.fetch_order_book.assert_awaited_once_with("BTC/USDT", 2)

    async def test_not_connected(self):
        c = ExchangeClient(sandbox=True)
        with pytest.raises((RuntimeError, RetryError)):
            await c.get_order_book("BTC/USDT")


# ---------------------------------------------------------------------------
# Order methods
# ---------------------------------------------------------------------------


class TestCreateMarketOrder:
    """Tests for create_market_order()."""

    async def test_success(self, client, mock_exchange):
        mock_exchange.create_market_order = AsyncMock(
            return_value={
                "id": "order-123",
                "symbol": "BTC/USDT",
                "side": "buy",
                "amount": 0.1,
                "status": "closed",
            }
        )

        result = await client.create_market_order("BTC/USDT", "buy", 0.1)

        assert result["id"] == "order-123"
        assert result["side"] == "buy"
        mock_exchange.create_market_order.assert_awaited_once_with(
            "BTC/USDT",
            "buy",
            0.1,
        )

    async def test_not_connected(self):
        c = ExchangeClient(sandbox=True)
        with pytest.raises(RuntimeError, match="Not connected"):
            await c.create_market_order("BTC/USDT", "buy", 0.1)


class TestCreateLimitOrder:
    """Tests for create_limit_order()."""

    async def test_success(self, client, mock_exchange):
        mock_exchange.create_limit_order = AsyncMock(
            return_value={
                "id": "order-456",
                "symbol": "BTC/USDT",
                "side": "sell",
                "amount": 0.05,
                "price": 55000.0,
                "status": "open",
            }
        )

        result = await client.create_limit_order("BTC/USDT", "sell", 0.05, 55000.0)

        assert result["id"] == "order-456"
        assert result["price"] == 55000.0
        mock_exchange.create_limit_order.assert_awaited_once_with(
            "BTC/USDT",
            "sell",
            0.05,
            55000.0,
        )

    async def test_not_connected(self):
        c = ExchangeClient(sandbox=True)
        with pytest.raises(RuntimeError, match="Not connected"):
            await c.create_limit_order("BTC/USDT", "sell", 0.05, 55000.0)


class TestCancelOrder:
    """Tests for cancel_order()."""

    async def test_success(self, client, mock_exchange):
        mock_exchange.cancel_order = AsyncMock(
            return_value={
                "id": "order-123",
                "status": "canceled",
            }
        )

        result = await client.cancel_order("order-123", "BTC/USDT")

        assert result["status"] == "canceled"
        mock_exchange.cancel_order.assert_awaited_once_with("order-123", "BTC/USDT")

    async def test_not_connected(self):
        c = ExchangeClient(sandbox=True)
        with pytest.raises(RuntimeError, match="Not connected"):
            await c.cancel_order("order-123", "BTC/USDT")


class TestGetOrder:
    """Tests for get_order()."""

    async def test_success(self, client, mock_exchange):
        mock_exchange.fetch_order = AsyncMock(
            return_value={
                "id": "order-123",
                "status": "closed",
                "filled": 0.1,
            }
        )

        result = await client.get_order("order-123", "BTC/USDT")

        assert result["id"] == "order-123"
        assert result["filled"] == 0.1
        mock_exchange.fetch_order.assert_awaited_once_with("order-123", "BTC/USDT")

    async def test_not_connected(self):
        c = ExchangeClient(sandbox=True)
        with pytest.raises(RuntimeError, match="Not connected"):
            await c.get_order("order-123", "BTC/USDT")


# ---------------------------------------------------------------------------
# Price feed
# ---------------------------------------------------------------------------


class TestPriceFeed:
    """Tests for start_price_feed / stop_price_feed / _price_feed_loop."""

    async def test_start_creates_task(self, client, mock_exchange):
        mock_exchange.fetch_ticker = AsyncMock(
            return_value={
                "symbol": "BTC/USDT",
                "last": 50000.0,
                "bid": 49990.0,
                "ask": 50010.0,
                "high": 51000.0,
                "low": 49000.0,
                "baseVolume": 1234.5,
                "quoteVolume": 61725000.0,
                "timestamp": 1700000000000,
                "datetime": "2023-11-14T22:13:20.000Z",
            }
        )

        await client.start_price_feed(symbols=["BTC/USDT"], interval=0.01)

        assert client._running is True
        assert client._price_task is not None

        # Let loop run briefly then stop
        await asyncio.sleep(0.05)
        await client.stop_price_feed()

        assert client._running is False
        assert client._price_task is None

    async def test_start_already_running_noop(self, client, mock_exchange):
        mock_exchange.fetch_ticker = AsyncMock(
            return_value={
                "symbol": "BTC/USDT",
                "last": 50000.0,
                "bid": 49990.0,
                "ask": 50010.0,
                "high": 51000.0,
                "low": 49000.0,
                "baseVolume": 100.0,
                "quoteVolume": 5000000.0,
                "timestamp": 1700000000000,
                "datetime": "2023-11-14T22:13:20.000Z",
            }
        )

        await client.start_price_feed(symbols=["BTC/USDT"], interval=0.01)
        first_task = client._price_task

        # Second call is a no-op
        await client.start_price_feed(symbols=["ETH/USDT"], interval=0.01)
        assert client._price_task is first_task

        await client.stop_price_feed()

    async def test_stop_when_not_running_noop(self, client):
        await client.stop_price_feed()  # should not raise

    async def test_loop_publishes_events(self, client, mock_exchange):
        mock_exchange.fetch_ticker = AsyncMock(
            return_value={
                "symbol": "BTC/USDT",
                "last": 50000.0,
                "bid": 49990.0,
                "ask": 50010.0,
                "high": 51000.0,
                "low": 49000.0,
                "baseVolume": 100.0,
                "quoteVolume": 5000000.0,
                "timestamp": 1700000000000,
                "datetime": "2023-11-14T22:13:20.000Z",
            }
        )

        publish_mock = AsyncMock()
        client.event_bus.publish = publish_mock

        await client.start_price_feed(symbols=["BTC/USDT"], interval=0.01)
        await asyncio.sleep(0.05)
        await client.stop_price_feed()

        assert publish_mock.await_count >= 1

    async def test_loop_handles_per_symbol_error(self, client):
        """A failing symbol should not crash the loop."""
        call_count = 0

        async def ticker_side_effect(symbol):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("transient error")
            return {
                "symbol": symbol,
                "last": 50000.0,
                "bid": 49990.0,
                "ask": 50010.0,
                "volume": 100.0,
            }

        # Patch get_ticker directly to bypass tenacity retry delays
        client.get_ticker = AsyncMock(side_effect=ticker_side_effect)

        await client.start_price_feed(symbols=["BTC/USDT"], interval=0.01)
        await asyncio.sleep(0.1)
        await client.stop_price_feed()

        # Loop should have continued past initial errors
        assert call_count > 2

    async def test_default_symbols_from_settings(self, client, mock_exchange):
        """When no symbols passed, uses settings.system.symbols."""
        mock_exchange.fetch_ticker = AsyncMock(
            return_value={
                "symbol": "BTC/USDT",
                "last": 50000.0,
                "bid": 49990.0,
                "ask": 50010.0,
                "high": 51000.0,
                "low": 49000.0,
                "baseVolume": 100.0,
                "quoteVolume": 5000000.0,
                "timestamp": 1700000000000,
                "datetime": "2023-11-14T22:13:20.000Z",
            }
        )

        await client.start_price_feed(interval=0.01)
        assert client._running is True
        await asyncio.sleep(0.03)
        await client.stop_price_feed()
