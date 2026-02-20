"""Tests for Kraken exchange adapter."""

from unittest.mock import AsyncMock, patch

import pytest

from keryxflow.exchange.adapter import ExchangeAdapter
from keryxflow.exchange.kraken import KrakenAdapter, get_kraken_client


class TestKrakenAdapter:
    """Tests for KrakenAdapter."""

    def test_inherits_from_exchange_adapter(self):
        """Test that KrakenAdapter inherits from ExchangeAdapter."""
        assert issubclass(KrakenAdapter, ExchangeAdapter)

    def test_initial_state(self):
        """Test initial state of adapter."""
        adapter = KrakenAdapter(sandbox=True)

        assert adapter._sandbox is True
        assert adapter._running is False
        assert adapter._exchange is None
        assert adapter._price_task is None
        assert adapter.is_connected is False

    def test_initial_state_live(self):
        """Test initial state with sandbox=False."""
        adapter = KrakenAdapter(sandbox=False)

        assert adapter._sandbox is False

    async def test_connect_success(self):
        """Test successful connection."""
        adapter = KrakenAdapter(sandbox=True)

        with patch("keryxflow.exchange.kraken.ccxt") as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock(return_value=1234567890)
            mock_ccxt.kraken.return_value = mock_exchange

            result = await adapter.connect()

            assert result is True
            assert adapter.is_connected is True
            mock_exchange.set_sandbox_mode.assert_called_once_with(True)
            mock_exchange.fetch_time.assert_called_once()

    async def test_connect_network_error(self):
        """Test connection with network error."""
        import ccxt as real_ccxt

        adapter = KrakenAdapter(sandbox=True)

        with patch("keryxflow.exchange.kraken.ccxt") as mock_ccxt:
            # Keep the real exception classes
            mock_ccxt.NetworkError = real_ccxt.NetworkError
            mock_ccxt.ExchangeError = real_ccxt.ExchangeError

            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock(
                side_effect=real_ccxt.NetworkError("Network error")
            )
            mock_ccxt.kraken.return_value = mock_exchange

            result = await adapter.connect()

            assert result is False
            assert adapter.is_connected is False

    async def test_connect_exchange_error(self):
        """Test connection with exchange error."""
        import ccxt as real_ccxt

        adapter = KrakenAdapter(sandbox=True)

        with patch("keryxflow.exchange.kraken.ccxt") as mock_ccxt:
            # Keep the real exception classes
            mock_ccxt.NetworkError = real_ccxt.NetworkError
            mock_ccxt.ExchangeError = real_ccxt.ExchangeError

            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock(
                side_effect=real_ccxt.ExchangeError("Exchange error")
            )
            mock_ccxt.kraken.return_value = mock_exchange

            result = await adapter.connect()

            assert result is False

    async def test_disconnect(self):
        """Test disconnection."""
        adapter = KrakenAdapter(sandbox=True)

        with patch("keryxflow.exchange.kraken.ccxt") as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock()
            mock_exchange.close = AsyncMock()
            mock_ccxt.kraken.return_value = mock_exchange

            await adapter.connect()
            await adapter.disconnect()

            assert adapter.is_connected is False
            mock_exchange.close.assert_called_once()

    async def test_ensure_connected_raises(self):
        """Test _ensure_connected raises when not connected."""
        adapter = KrakenAdapter(sandbox=True)

        with pytest.raises(RuntimeError, match="Not connected to exchange"):
            adapter._ensure_connected()

    async def test_get_ticker(self):
        """Test getting ticker data."""
        adapter = KrakenAdapter(sandbox=True)

        mock_ticker = {
            "symbol": "BTC/USDT",
            "last": 50000.0,
            "bid": 49990.0,
            "ask": 50010.0,
            "high": 51000.0,
            "low": 49000.0,
            "baseVolume": 1000.0,
            "quoteVolume": 50000000.0,
            "timestamp": 1234567890000,
            "datetime": "2024-01-01T00:00:00.000Z",
        }

        with patch("keryxflow.exchange.kraken.ccxt") as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock()
            mock_exchange.fetch_ticker = AsyncMock(return_value=mock_ticker)
            mock_ccxt.kraken.return_value = mock_exchange

            await adapter.connect()
            ticker = await adapter.get_ticker("BTC/USDT")

            assert ticker["symbol"] == "BTC/USDT"
            assert ticker["last"] == 50000.0
            assert ticker["bid"] == 49990.0
            assert ticker["ask"] == 50010.0
            assert ticker["volume"] == 1000.0

    async def test_get_ohlcv(self):
        """Test getting OHLCV data."""
        adapter = KrakenAdapter(sandbox=True)

        mock_ohlcv = [
            [1704067200000, 42000.0, 42500.0, 41800.0, 42200.0, 1000.0],
            [1704070800000, 42200.0, 42800.0, 42100.0, 42600.0, 1200.0],
        ]

        with patch("keryxflow.exchange.kraken.ccxt") as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock()
            mock_exchange.fetch_ohlcv = AsyncMock(return_value=mock_ohlcv)
            mock_ccxt.kraken.return_value = mock_exchange

            await adapter.connect()
            ohlcv = await adapter.get_ohlcv("BTC/USDT", "1h", 100)

            assert len(ohlcv) == 2
            assert ohlcv[0][4] == 42200.0  # Close price
            mock_exchange.fetch_ohlcv.assert_called_once_with(
                "BTC/USDT", "1h", since=None, limit=100
            )

    async def test_get_balance(self):
        """Test getting account balance."""
        adapter = KrakenAdapter(sandbox=True)

        mock_balance = {
            "total": {"BTC": 1.0, "USDT": 10000.0},
            "free": {"BTC": 0.5, "USDT": 9000.0},
            "used": {"BTC": 0.5, "USDT": 1000.0},
        }

        with patch("keryxflow.exchange.kraken.ccxt") as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock()
            mock_exchange.fetch_balance = AsyncMock(return_value=mock_balance)
            mock_ccxt.kraken.return_value = mock_exchange

            await adapter.connect()
            balance = await adapter.get_balance()

            assert balance["total"]["BTC"] == 1.0
            assert balance["free"]["USDT"] == 9000.0
            assert balance["used"]["BTC"] == 0.5

    async def test_get_order_book(self):
        """Test getting order book."""
        adapter = KrakenAdapter(sandbox=True)

        mock_order_book = {
            "bids": [[49990.0, 1.0], [49980.0, 2.0], [49970.0, 3.0]],
            "asks": [[50010.0, 1.0], [50020.0, 2.0], [50030.0, 3.0]],
            "timestamp": 1234567890000,
        }

        with patch("keryxflow.exchange.kraken.ccxt") as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock()
            mock_exchange.fetch_order_book = AsyncMock(return_value=mock_order_book)
            mock_ccxt.kraken.return_value = mock_exchange

            await adapter.connect()
            order_book = await adapter.get_order_book("BTC/USDT", limit=2)

            assert order_book["symbol"] == "BTC/USDT"
            assert len(order_book["bids"]) == 2
            assert len(order_book["asks"]) == 2
            assert order_book["bids"][0][0] == 49990.0

    async def test_create_market_order(self):
        """Test creating a market order."""
        adapter = KrakenAdapter(sandbox=True)

        mock_order = {
            "id": "order123",
            "symbol": "BTC/USDT",
            "side": "buy",
            "amount": 0.1,
            "price": 50000.0,
            "status": "closed",
        }

        with patch("keryxflow.exchange.kraken.ccxt") as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock()
            mock_exchange.create_market_order = AsyncMock(return_value=mock_order)
            mock_ccxt.kraken.return_value = mock_exchange

            await adapter.connect()
            order = await adapter.create_market_order("BTC/USDT", "buy", 0.1)

            assert order["id"] == "order123"
            assert order["side"] == "buy"
            mock_exchange.create_market_order.assert_called_once_with("BTC/USDT", "buy", 0.1)

    async def test_create_limit_order(self):
        """Test creating a limit order."""
        adapter = KrakenAdapter(sandbox=True)

        mock_order = {
            "id": "order456",
            "symbol": "BTC/USDT",
            "side": "sell",
            "amount": 0.1,
            "price": 55000.0,
            "status": "open",
        }

        with patch("keryxflow.exchange.kraken.ccxt") as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock()
            mock_exchange.create_limit_order = AsyncMock(return_value=mock_order)
            mock_ccxt.kraken.return_value = mock_exchange

            await adapter.connect()
            order = await adapter.create_limit_order("BTC/USDT", "sell", 0.1, 55000.0)

            assert order["id"] == "order456"
            assert order["price"] == 55000.0
            mock_exchange.create_limit_order.assert_called_once_with(
                "BTC/USDT", "sell", 0.1, 55000.0
            )

    async def test_cancel_order(self):
        """Test cancelling an order."""
        adapter = KrakenAdapter(sandbox=True)

        mock_result = {"id": "order123", "status": "cancelled"}

        with patch("keryxflow.exchange.kraken.ccxt") as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock()
            mock_exchange.cancel_order = AsyncMock(return_value=mock_result)
            mock_ccxt.kraken.return_value = mock_exchange

            await adapter.connect()
            result = await adapter.cancel_order("order123", "BTC/USDT")

            assert result["status"] == "cancelled"
            mock_exchange.cancel_order.assert_called_once_with("order123", "BTC/USDT")

    async def test_get_order(self):
        """Test getting order status."""
        adapter = KrakenAdapter(sandbox=True)

        mock_order = {
            "id": "order123",
            "status": "closed",
            "filled": 0.1,
        }

        with patch("keryxflow.exchange.kraken.ccxt") as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock()
            mock_exchange.fetch_order = AsyncMock(return_value=mock_order)
            mock_ccxt.kraken.return_value = mock_exchange

            await adapter.connect()
            order = await adapter.get_order("order123", "BTC/USDT")

            assert order["status"] == "closed"
            mock_exchange.fetch_order.assert_called_once_with("order123", "BTC/USDT")

    async def test_get_open_orders(self):
        """Test getting open orders."""
        adapter = KrakenAdapter(sandbox=True)

        mock_orders = [
            {"id": "order1", "status": "open"},
            {"id": "order2", "status": "open"},
        ]

        with patch("keryxflow.exchange.kraken.ccxt") as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock()
            mock_exchange.fetch_open_orders = AsyncMock(return_value=mock_orders)
            mock_ccxt.kraken.return_value = mock_exchange

            await adapter.connect()
            orders = await adapter.get_open_orders("BTC/USDT")

            assert len(orders) == 2
            mock_exchange.fetch_open_orders.assert_called_once_with("BTC/USDT")

    async def test_start_price_feed(self):
        """Test starting price feed."""
        adapter = KrakenAdapter(sandbox=True)

        with patch("keryxflow.exchange.kraken.ccxt") as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock()
            mock_ccxt.kraken.return_value = mock_exchange

            await adapter.connect()
            await adapter.start_price_feed(["BTC/USDT"], interval=1.0)

            assert adapter._running is True
            assert adapter._price_task is not None

            # Clean up
            await adapter.stop_price_feed()

    async def test_stop_price_feed(self):
        """Test stopping price feed."""
        adapter = KrakenAdapter(sandbox=True)

        with patch("keryxflow.exchange.kraken.ccxt") as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock()
            mock_ccxt.kraken.return_value = mock_exchange

            await adapter.connect()
            await adapter.start_price_feed(["BTC/USDT"], interval=1.0)
            await adapter.stop_price_feed()

            assert adapter._running is False
            assert adapter._price_task is None

    async def test_execute_market_order_protocol(self):
        """Test OrderExecutor protocol's execute_market_order."""
        adapter = KrakenAdapter(sandbox=True)

        mock_order = {
            "id": "order123",
            "symbol": "BTC/USDT",
            "side": "buy",
            "amount": 0.1,
            "price": 50000.0,
            "status": "closed",
        }

        with patch("keryxflow.exchange.kraken.ccxt") as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock()
            mock_exchange.create_market_order = AsyncMock(return_value=mock_order)
            mock_ccxt.kraken.return_value = mock_exchange

            await adapter.connect()
            # Use the OrderExecutor protocol method
            order = await adapter.execute_market_order("BTC/USDT", "buy", 0.1)

            assert order["id"] == "order123"

    def test_update_price_noop(self):
        """Test that update_price is a no-op for live exchanges."""
        adapter = KrakenAdapter(sandbox=True)
        # Should not raise
        adapter.update_price("BTC/USDT", 50000.0)

    def test_get_price_returns_none(self):
        """Test that get_price returns None for live exchanges."""
        adapter = KrakenAdapter(sandbox=True)
        assert adapter.get_price("BTC/USDT") is None


class TestGetKrakenClient:
    """Tests for get_kraken_client singleton."""

    def test_returns_kraken_adapter(self):
        """Test that it returns a KrakenAdapter instance."""
        # Reset singleton
        import keryxflow.exchange.kraken as kraken_module

        kraken_module._kraken_client = None

        client = get_kraken_client(sandbox=True)
        assert isinstance(client, KrakenAdapter)

    def test_returns_same_instance(self):
        """Test singleton pattern."""
        import keryxflow.exchange.kraken as kraken_module

        kraken_module._kraken_client = None

        client1 = get_kraken_client(sandbox=True)
        client2 = get_kraken_client(sandbox=True)

        assert client1 is client2
