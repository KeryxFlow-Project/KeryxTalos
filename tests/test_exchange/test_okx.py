"""Tests for OKX exchange client and exchange factory."""

from unittest.mock import AsyncMock, patch

import pytest

from keryxflow.exchange.adapter import ExchangeAdapter
from keryxflow.exchange.okx import OKXClient


@pytest.fixture
def okx_client():
    """Create an OKXClient instance for testing."""
    return OKXClient(sandbox=True)


class TestOKXClient:
    """Tests for OKXClient."""

    def test_inherits_from_adapter(self):
        """Test OKXClient implements ExchangeAdapter."""
        assert issubclass(OKXClient, ExchangeAdapter)

    def test_initial_state(self, okx_client):
        """Test initial state of client."""
        assert not okx_client.is_connected
        assert not okx_client._running
        assert okx_client._sandbox is True

    async def test_connect_success(self, okx_client):
        """Test successful connection."""
        mock_exchange = AsyncMock()
        mock_exchange.fetch_time = AsyncMock(return_value=1234567890)

        with patch("keryxflow.exchange.okx.ccxt.okx", return_value=mock_exchange):
            result = await okx_client.connect()

        assert result is True
        assert okx_client.is_connected
        mock_exchange.set_sandbox_mode.assert_called_once_with(True)
        mock_exchange.fetch_time.assert_awaited_once()

    async def test_connect_with_credentials(self, okx_client):
        """Test connection passes passphrase as password to CCXT."""
        from pydantic import SecretStr

        mock_exchange = AsyncMock()
        mock_exchange.fetch_time = AsyncMock(return_value=1234567890)

        okx_client.settings = type(
            "Settings",
            (),
            {
                "has_okx_credentials": True,
                "okx_api_key": SecretStr("test-key"),
                "okx_api_secret": SecretStr("test-secret"),
                "okx_passphrase": SecretStr("test-passphrase"),
                "system": type("System", (), {"symbols": ["BTC/USDT"]})(),
            },
        )()

        with patch("keryxflow.exchange.okx.ccxt.okx", return_value=mock_exchange) as mock_ccxt:
            result = await okx_client.connect()

        assert result is True
        # Verify passphrase was passed as 'password' in config
        call_args = mock_ccxt.call_args[0][0]
        assert call_args["apiKey"] == "test-key"
        assert call_args["secret"] == "test-secret"
        assert call_args["password"] == "test-passphrase"

    async def test_connect_network_error(self, okx_client):
        """Test connection with network error."""
        import ccxt.async_support as ccxt_async

        mock_exchange = AsyncMock()
        mock_exchange.fetch_time = AsyncMock(side_effect=ccxt_async.NetworkError("timeout"))

        with patch("keryxflow.exchange.okx.ccxt.okx", return_value=mock_exchange):
            result = await okx_client.connect()

        assert result is False

    async def test_connect_exchange_error(self, okx_client):
        """Test connection with exchange error."""
        import ccxt.async_support as ccxt_async

        mock_exchange = AsyncMock()
        mock_exchange.fetch_time = AsyncMock(side_effect=ccxt_async.ExchangeError("auth failed"))

        with patch("keryxflow.exchange.okx.ccxt.okx", return_value=mock_exchange):
            result = await okx_client.connect()

        assert result is False

    async def test_disconnect(self, okx_client):
        """Test disconnect."""
        mock_exchange = AsyncMock()
        mock_exchange.fetch_time = AsyncMock(return_value=1234567890)

        with patch("keryxflow.exchange.okx.ccxt.okx", return_value=mock_exchange):
            await okx_client.connect()
            await okx_client.disconnect()

        assert not okx_client.is_connected
        mock_exchange.close.assert_awaited_once()

    async def test_disconnect_when_not_connected(self, okx_client):
        """Test disconnect when not connected doesn't raise."""
        await okx_client.disconnect()  # Should not raise

    async def test_ensure_connected_raises(self, okx_client):
        """Test _ensure_connected raises when not connected."""
        with pytest.raises(RuntimeError, match="Not connected"):
            okx_client._ensure_connected()

    async def test_get_ticker(self, okx_client):
        """Test get_ticker returns normalized data."""
        mock_exchange = AsyncMock()
        mock_exchange.fetch_time = AsyncMock(return_value=1234567890)
        mock_exchange.fetch_ticker = AsyncMock(
            return_value={
                "symbol": "BTC/USDT",
                "last": 50000.0,
                "bid": 49999.0,
                "ask": 50001.0,
                "high": 51000.0,
                "low": 49000.0,
                "baseVolume": 1234.5,
                "quoteVolume": 61725000.0,
                "timestamp": 1234567890000,
                "datetime": "2024-01-01T00:00:00.000Z",
            }
        )

        with patch("keryxflow.exchange.okx.ccxt.okx", return_value=mock_exchange):
            await okx_client.connect()
            ticker = await okx_client.get_ticker("BTC/USDT")

        assert ticker["symbol"] == "BTC/USDT"
        assert ticker["last"] == 50000.0
        assert ticker["bid"] == 49999.0
        assert ticker["ask"] == 50001.0
        assert ticker["volume"] == 1234.5

    async def test_get_ohlcv(self, okx_client):
        """Test get_ohlcv returns candle data."""
        candles = [
            [1704067200000, 42000.0, 42500.0, 41800.0, 42200.0, 1000.0],
            [1704070800000, 42200.0, 42800.0, 42100.0, 42600.0, 1200.0],
        ]
        mock_exchange = AsyncMock()
        mock_exchange.fetch_time = AsyncMock(return_value=1234567890)
        mock_exchange.fetch_ohlcv = AsyncMock(return_value=candles)

        with patch("keryxflow.exchange.okx.ccxt.okx", return_value=mock_exchange):
            await okx_client.connect()
            result = await okx_client.get_ohlcv("BTC/USDT", "1h", limit=2)

        assert result == candles
        mock_exchange.fetch_ohlcv.assert_awaited_once_with("BTC/USDT", "1h", since=None, limit=2)

    async def test_get_balance(self, okx_client):
        """Test get_balance returns normalized data."""
        mock_exchange = AsyncMock()
        mock_exchange.fetch_time = AsyncMock(return_value=1234567890)
        mock_exchange.fetch_balance = AsyncMock(
            return_value={
                "total": {"USDT": 10000.0, "BTC": 0.1},
                "free": {"USDT": 9000.0, "BTC": 0.05},
                "used": {"USDT": 1000.0, "BTC": 0.05},
            }
        )

        with patch("keryxflow.exchange.okx.ccxt.okx", return_value=mock_exchange):
            await okx_client.connect()
            balance = await okx_client.get_balance()

        assert balance["total"]["USDT"] == 10000.0
        assert balance["free"]["BTC"] == 0.05

    async def test_get_order_book(self, okx_client):
        """Test get_order_book returns normalized data."""
        mock_exchange = AsyncMock()
        mock_exchange.fetch_time = AsyncMock(return_value=1234567890)
        mock_exchange.fetch_order_book = AsyncMock(
            return_value={
                "bids": [[49999.0, 1.0], [49998.0, 2.0]],
                "asks": [[50001.0, 1.0], [50002.0, 2.0]],
                "timestamp": 1234567890000,
            }
        )

        with patch("keryxflow.exchange.okx.ccxt.okx", return_value=mock_exchange):
            await okx_client.connect()
            book = await okx_client.get_order_book("BTC/USDT", limit=2)

        assert book["symbol"] == "BTC/USDT"
        assert len(book["bids"]) == 2
        assert len(book["asks"]) == 2

    async def test_create_market_order(self, okx_client):
        """Test create_market_order."""
        mock_exchange = AsyncMock()
        mock_exchange.fetch_time = AsyncMock(return_value=1234567890)
        mock_exchange.create_market_order = AsyncMock(
            return_value={"id": "order123", "symbol": "BTC/USDT", "side": "buy"}
        )

        with patch("keryxflow.exchange.okx.ccxt.okx", return_value=mock_exchange):
            await okx_client.connect()
            result = await okx_client.create_market_order("BTC/USDT", "buy", 0.1)

        assert result["id"] == "order123"
        mock_exchange.create_market_order.assert_awaited_once_with("BTC/USDT", "buy", 0.1)

    async def test_create_limit_order(self, okx_client):
        """Test create_limit_order."""
        mock_exchange = AsyncMock()
        mock_exchange.fetch_time = AsyncMock(return_value=1234567890)
        mock_exchange.create_limit_order = AsyncMock(
            return_value={"id": "order456", "symbol": "BTC/USDT", "side": "sell"}
        )

        with patch("keryxflow.exchange.okx.ccxt.okx", return_value=mock_exchange):
            await okx_client.connect()
            result = await okx_client.create_limit_order("BTC/USDT", "sell", 0.1, 55000.0)

        assert result["id"] == "order456"
        mock_exchange.create_limit_order.assert_awaited_once_with("BTC/USDT", "sell", 0.1, 55000.0)

    async def test_cancel_order(self, okx_client):
        """Test cancel_order."""
        mock_exchange = AsyncMock()
        mock_exchange.fetch_time = AsyncMock(return_value=1234567890)
        mock_exchange.cancel_order = AsyncMock(return_value={"id": "order123"})

        with patch("keryxflow.exchange.okx.ccxt.okx", return_value=mock_exchange):
            await okx_client.connect()
            result = await okx_client.cancel_order("order123", "BTC/USDT")

        assert result["id"] == "order123"
        mock_exchange.cancel_order.assert_awaited_once_with("order123", "BTC/USDT")

    async def test_get_order(self, okx_client):
        """Test get_order."""
        mock_exchange = AsyncMock()
        mock_exchange.fetch_time = AsyncMock(return_value=1234567890)
        mock_exchange.fetch_order = AsyncMock(return_value={"id": "order123", "status": "closed"})

        with patch("keryxflow.exchange.okx.ccxt.okx", return_value=mock_exchange):
            await okx_client.connect()
            result = await okx_client.get_order("order123", "BTC/USDT")

        assert result["status"] == "closed"

    async def test_get_open_orders(self, okx_client):
        """Test get_open_orders."""
        mock_exchange = AsyncMock()
        mock_exchange.fetch_time = AsyncMock(return_value=1234567890)
        mock_exchange.fetch_open_orders = AsyncMock(
            return_value=[
                {"id": "order1", "status": "open"},
                {"id": "order2", "status": "open"},
            ]
        )

        with patch("keryxflow.exchange.okx.ccxt.okx", return_value=mock_exchange):
            await okx_client.connect()
            result = await okx_client.get_open_orders("BTC/USDT")

        assert len(result) == 2
        assert result[0]["id"] == "order1"
        mock_exchange.fetch_open_orders.assert_awaited_once_with("BTC/USDT")

    async def test_sandbox_mode_disabled(self):
        """Test client without sandbox mode."""
        client = OKXClient(sandbox=False)
        mock_exchange = AsyncMock()
        mock_exchange.fetch_time = AsyncMock(return_value=1234567890)

        with patch("keryxflow.exchange.okx.ccxt.okx", return_value=mock_exchange):
            await client.connect()

        mock_exchange.set_sandbox_mode.assert_not_called()
        await client.disconnect()

    async def test_start_stop_price_feed(self, okx_client):
        """Test starting and stopping the price feed."""
        mock_exchange = AsyncMock()
        mock_exchange.fetch_time = AsyncMock(return_value=1234567890)
        mock_exchange.fetch_ticker = AsyncMock(
            return_value={
                "symbol": "BTC/USDT",
                "last": 50000.0,
                "bid": 49999.0,
                "ask": 50001.0,
                "high": 51000.0,
                "low": 49000.0,
                "baseVolume": 1234.5,
                "quoteVolume": 61725000.0,
                "timestamp": 1234567890000,
                "datetime": "2024-01-01T00:00:00.000Z",
            }
        )

        with patch("keryxflow.exchange.okx.ccxt.okx", return_value=mock_exchange):
            await okx_client.connect()
            await okx_client.start_price_feed(symbols=["BTC/USDT"], interval=0.1)

            assert okx_client._running is True
            assert okx_client._price_task is not None

            await okx_client.stop_price_feed()

            assert okx_client._running is False
            assert okx_client._price_task is None

        await okx_client.disconnect()


class TestOKXExchangeFactory:
    """Tests for exchange factory function with OKX."""

    def test_factory_returns_okx(self):
        """Test factory returns OKX client when exchange=okx."""
        import keryxflow.exchange.okx as okx_module
        from keryxflow.exchange import get_exchange_adapter

        okx_module._okx_client = None

        with patch("keryxflow.config.get_settings") as mock_settings:
            mock_system = type("System", (), {"exchange": "okx"})()
            mock_settings.return_value = type("Settings", (), {"system": mock_system})()
            adapter = get_exchange_adapter(sandbox=True)
            assert isinstance(adapter, OKXClient)
