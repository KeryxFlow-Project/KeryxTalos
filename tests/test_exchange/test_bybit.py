"""Tests for Bybit exchange client and exchange factory."""

from unittest.mock import AsyncMock, patch

import pytest

from keryxflow.exchange.adapter import ExchangeAdapter
from keryxflow.exchange.bybit import BybitClient


@pytest.fixture
def bybit_client():
    """Create a BybitClient instance for testing."""
    return BybitClient(sandbox=True)


class TestBybitClient:
    """Tests for BybitClient."""

    def test_inherits_from_adapter(self):
        """Test BybitClient implements ExchangeAdapter."""
        assert issubclass(BybitClient, ExchangeAdapter)

    def test_initial_state(self, bybit_client):
        """Test initial state of client."""
        assert not bybit_client.is_connected
        assert not bybit_client._running
        assert bybit_client._sandbox is True

    async def test_connect_success(self, bybit_client):
        """Test successful connection."""
        mock_exchange = AsyncMock()
        mock_exchange.fetch_time = AsyncMock(return_value=1234567890)

        with patch("keryxflow.exchange.bybit.ccxt.bybit", return_value=mock_exchange):
            result = await bybit_client.connect()

        assert result is True
        assert bybit_client.is_connected
        mock_exchange.set_sandbox_mode.assert_called_once_with(True)
        mock_exchange.fetch_time.assert_awaited_once()

    async def test_connect_network_error(self, bybit_client):
        """Test connection with network error."""
        import ccxt.async_support as ccxt_async

        mock_exchange = AsyncMock()
        mock_exchange.fetch_time = AsyncMock(side_effect=ccxt_async.NetworkError("timeout"))

        with patch("keryxflow.exchange.bybit.ccxt.bybit", return_value=mock_exchange):
            result = await bybit_client.connect()

        assert result is False

    async def test_connect_exchange_error(self, bybit_client):
        """Test connection with exchange error."""
        import ccxt.async_support as ccxt_async

        mock_exchange = AsyncMock()
        mock_exchange.fetch_time = AsyncMock(side_effect=ccxt_async.ExchangeError("auth failed"))

        with patch("keryxflow.exchange.bybit.ccxt.bybit", return_value=mock_exchange):
            result = await bybit_client.connect()

        assert result is False

    async def test_disconnect(self, bybit_client):
        """Test disconnect."""
        mock_exchange = AsyncMock()
        mock_exchange.fetch_time = AsyncMock(return_value=1234567890)

        with patch("keryxflow.exchange.bybit.ccxt.bybit", return_value=mock_exchange):
            await bybit_client.connect()
            await bybit_client.disconnect()

        assert not bybit_client.is_connected
        mock_exchange.close.assert_awaited_once()

    async def test_disconnect_when_not_connected(self, bybit_client):
        """Test disconnect when not connected doesn't raise."""
        await bybit_client.disconnect()  # Should not raise

    async def test_ensure_connected_raises(self, bybit_client):
        """Test _ensure_connected raises when not connected."""
        with pytest.raises(RuntimeError, match="Not connected"):
            bybit_client._ensure_connected()

    async def test_get_ticker(self, bybit_client):
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

        with patch("keryxflow.exchange.bybit.ccxt.bybit", return_value=mock_exchange):
            await bybit_client.connect()
            ticker = await bybit_client.get_ticker("BTC/USDT")

        assert ticker["symbol"] == "BTC/USDT"
        assert ticker["last"] == 50000.0
        assert ticker["bid"] == 49999.0
        assert ticker["ask"] == 50001.0
        assert ticker["volume"] == 1234.5

    async def test_get_ohlcv(self, bybit_client):
        """Test get_ohlcv returns candle data directly (no sandbox workaround)."""
        candles = [
            [1704067200000, 42000.0, 42500.0, 41800.0, 42200.0, 1000.0],
            [1704070800000, 42200.0, 42800.0, 42100.0, 42600.0, 1200.0],
        ]
        mock_exchange = AsyncMock()
        mock_exchange.fetch_time = AsyncMock(return_value=1234567890)
        mock_exchange.fetch_ohlcv = AsyncMock(return_value=candles)

        with patch("keryxflow.exchange.bybit.ccxt.bybit", return_value=mock_exchange):
            await bybit_client.connect()
            result = await bybit_client.get_ohlcv("BTC/USDT", "1h", limit=2)

        assert result == candles
        mock_exchange.fetch_ohlcv.assert_awaited_once_with("BTC/USDT", "1h", since=None, limit=2)

    async def test_get_balance(self, bybit_client):
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

        with patch("keryxflow.exchange.bybit.ccxt.bybit", return_value=mock_exchange):
            await bybit_client.connect()
            balance = await bybit_client.get_balance()

        assert balance["total"]["USDT"] == 10000.0
        assert balance["free"]["BTC"] == 0.05

    async def test_get_order_book(self, bybit_client):
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

        with patch("keryxflow.exchange.bybit.ccxt.bybit", return_value=mock_exchange):
            await bybit_client.connect()
            book = await bybit_client.get_order_book("BTC/USDT", limit=2)

        assert book["symbol"] == "BTC/USDT"
        assert len(book["bids"]) == 2
        assert len(book["asks"]) == 2

    async def test_create_market_order(self, bybit_client):
        """Test create_market_order."""
        mock_exchange = AsyncMock()
        mock_exchange.fetch_time = AsyncMock(return_value=1234567890)
        mock_exchange.create_market_order = AsyncMock(
            return_value={"id": "order123", "symbol": "BTC/USDT", "side": "buy"}
        )

        with patch("keryxflow.exchange.bybit.ccxt.bybit", return_value=mock_exchange):
            await bybit_client.connect()
            result = await bybit_client.create_market_order("BTC/USDT", "buy", 0.1)

        assert result["id"] == "order123"
        mock_exchange.create_market_order.assert_awaited_once_with("BTC/USDT", "buy", 0.1)

    async def test_create_limit_order(self, bybit_client):
        """Test create_limit_order."""
        mock_exchange = AsyncMock()
        mock_exchange.fetch_time = AsyncMock(return_value=1234567890)
        mock_exchange.create_limit_order = AsyncMock(
            return_value={"id": "order456", "symbol": "BTC/USDT", "side": "sell"}
        )

        with patch("keryxflow.exchange.bybit.ccxt.bybit", return_value=mock_exchange):
            await bybit_client.connect()
            result = await bybit_client.create_limit_order("BTC/USDT", "sell", 0.1, 55000.0)

        assert result["id"] == "order456"
        mock_exchange.create_limit_order.assert_awaited_once_with("BTC/USDT", "sell", 0.1, 55000.0)

    async def test_cancel_order(self, bybit_client):
        """Test cancel_order."""
        mock_exchange = AsyncMock()
        mock_exchange.fetch_time = AsyncMock(return_value=1234567890)
        mock_exchange.cancel_order = AsyncMock(return_value={"id": "order123"})

        with patch("keryxflow.exchange.bybit.ccxt.bybit", return_value=mock_exchange):
            await bybit_client.connect()
            result = await bybit_client.cancel_order("order123", "BTC/USDT")

        assert result["id"] == "order123"
        mock_exchange.cancel_order.assert_awaited_once_with("order123", "BTC/USDT")

    async def test_get_order(self, bybit_client):
        """Test get_order."""
        mock_exchange = AsyncMock()
        mock_exchange.fetch_time = AsyncMock(return_value=1234567890)
        mock_exchange.fetch_order = AsyncMock(return_value={"id": "order123", "status": "closed"})

        with patch("keryxflow.exchange.bybit.ccxt.bybit", return_value=mock_exchange):
            await bybit_client.connect()
            result = await bybit_client.get_order("order123", "BTC/USDT")

        assert result["status"] == "closed"

    async def test_sandbox_mode_disabled(self):
        """Test client without sandbox mode."""
        client = BybitClient(sandbox=False)
        mock_exchange = AsyncMock()
        mock_exchange.fetch_time = AsyncMock(return_value=1234567890)

        with patch("keryxflow.exchange.bybit.ccxt.bybit", return_value=mock_exchange):
            await client.connect()

        mock_exchange.set_sandbox_mode.assert_not_called()
        await client.disconnect()

    async def test_start_stop_price_feed(self, bybit_client):
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

        with patch("keryxflow.exchange.bybit.ccxt.bybit", return_value=mock_exchange):
            await bybit_client.connect()
            await bybit_client.start_price_feed(symbols=["BTC/USDT"], interval=0.1)

            assert bybit_client._running is True
            assert bybit_client._price_task is not None

            await bybit_client.stop_price_feed()

            assert bybit_client._running is False
            assert bybit_client._price_task is None

        await bybit_client.disconnect()


class TestExchangeFactory:
    """Tests for exchange factory function."""

    def test_factory_returns_binance_by_default(self):
        """Test factory returns Binance client when exchange=binance."""
        from keryxflow.exchange import get_exchange_adapter
        from keryxflow.exchange.client import ExchangeClient

        adapter = get_exchange_adapter(sandbox=True)
        assert isinstance(adapter, ExchangeClient)

    def test_factory_returns_bybit(self):
        """Test factory returns Bybit client when exchange=bybit."""

        # Reset bybit singleton
        import keryxflow.exchange.bybit as bybit_module
        from keryxflow.exchange import get_exchange_adapter

        bybit_module._bybit_client = None

        # Mock settings to return 'bybit' for exchange
        with patch("keryxflow.config.get_settings") as mock_settings:
            mock_system = type("System", (), {"exchange": "bybit", "mode": "paper"})()
            mock_settings.return_value = type("Settings", (), {"system": mock_system})()
            adapter = get_exchange_adapter(sandbox=True)
            assert isinstance(adapter, BybitClient)

    def test_factory_raises_for_unknown_exchange(self):
        """Test factory raises ValueError for unsupported exchange."""
        from keryxflow.exchange import get_exchange_adapter

        with patch("keryxflow.config.get_settings") as mock_settings:
            mock_system = type(
                "System", (), {"exchange": "unsupported_exchange", "mode": "paper"}
            )()
            mock_settings.return_value = type("Settings", (), {"system": mock_system})()
            with pytest.raises(ValueError, match="Unsupported exchange"):
                get_exchange_adapter()

    def test_adapter_abc_cannot_instantiate(self):
        """Test ExchangeAdapter ABC cannot be directly instantiated."""
        with pytest.raises(TypeError):
            ExchangeAdapter()
