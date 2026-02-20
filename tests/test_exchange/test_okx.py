"""Tests for OKX exchange adapter."""

from unittest.mock import AsyncMock, patch

import pytest

from keryxflow.exchange.adapter import ExchangeAdapter
from keryxflow.exchange.okx import OKXAdapter, get_okx_client


class TestOKXAdapter:
    """Tests for OKXAdapter."""

    def test_inherits_from_exchange_adapter(self):
        """Test that OKXAdapter inherits from ExchangeAdapter."""
        assert issubclass(OKXAdapter, ExchangeAdapter)

    def test_initial_state(self):
        """Test initial state of adapter."""
        adapter = OKXAdapter(sandbox=True)

        assert adapter._sandbox is True
        assert adapter._running is False
        assert adapter._exchange is None
        assert adapter._price_task is None
        assert adapter.is_connected is False

    def test_initial_state_live(self):
        """Test initial state with sandbox=False."""
        adapter = OKXAdapter(sandbox=False)

        assert adapter._sandbox is False

    async def test_connect_success_with_demo_header(self):
        """Test successful connection with demo trading header."""
        adapter = OKXAdapter(sandbox=True)

        with patch("keryxflow.exchange.okx.ccxt") as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock(return_value=1234567890)
            mock_ccxt.okx.return_value = mock_exchange

            result = await adapter.connect()

            assert result is True
            assert adapter.is_connected is True
            # Verify demo trading header is set via config
            call_args = mock_ccxt.okx.call_args
            config = call_args[0][0]
            assert config["headers"]["x-simulated-trading"] == "1"

    async def test_connect_live_no_demo_header(self):
        """Test live connection without demo header."""
        adapter = OKXAdapter(sandbox=False)

        with patch("keryxflow.exchange.okx.ccxt") as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock(return_value=1234567890)
            mock_ccxt.okx.return_value = mock_exchange

            result = await adapter.connect()

            assert result is True
            # Verify no demo header for live mode
            call_args = mock_ccxt.okx.call_args
            config = call_args[0][0]
            assert "headers" not in config

    async def test_connect_network_error(self):
        """Test connection with network error."""
        import ccxt as real_ccxt

        adapter = OKXAdapter(sandbox=True)

        with patch("keryxflow.exchange.okx.ccxt") as mock_ccxt:
            # Keep the real exception classes
            mock_ccxt.NetworkError = real_ccxt.NetworkError
            mock_ccxt.ExchangeError = real_ccxt.ExchangeError

            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock(
                side_effect=real_ccxt.NetworkError("Network error")
            )
            mock_ccxt.okx.return_value = mock_exchange

            result = await adapter.connect()

            assert result is False
            assert adapter.is_connected is False

    async def test_connect_exchange_error(self):
        """Test connection with exchange error."""
        import ccxt as real_ccxt

        adapter = OKXAdapter(sandbox=True)

        with patch("keryxflow.exchange.okx.ccxt") as mock_ccxt:
            # Keep the real exception classes
            mock_ccxt.NetworkError = real_ccxt.NetworkError
            mock_ccxt.ExchangeError = real_ccxt.ExchangeError

            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock(
                side_effect=real_ccxt.ExchangeError("Exchange error")
            )
            mock_ccxt.okx.return_value = mock_exchange

            result = await adapter.connect()

            assert result is False

    async def test_disconnect(self):
        """Test disconnection."""
        adapter = OKXAdapter(sandbox=True)

        with patch("keryxflow.exchange.okx.ccxt") as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock()
            mock_exchange.close = AsyncMock()
            mock_ccxt.okx.return_value = mock_exchange

            await adapter.connect()
            await adapter.disconnect()

            assert adapter.is_connected is False
            mock_exchange.close.assert_called_once()

    async def test_ensure_connected_raises(self):
        """Test _ensure_connected raises when not connected."""
        adapter = OKXAdapter(sandbox=True)

        with pytest.raises(RuntimeError, match="Not connected to exchange"):
            adapter._ensure_connected()

    async def test_get_ticker(self):
        """Test getting ticker data."""
        adapter = OKXAdapter(sandbox=True)

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

        with patch("keryxflow.exchange.okx.ccxt") as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock()
            mock_exchange.fetch_ticker = AsyncMock(return_value=mock_ticker)
            mock_ccxt.okx.return_value = mock_exchange

            await adapter.connect()
            ticker = await adapter.get_ticker("BTC/USDT")

            assert ticker["symbol"] == "BTC/USDT"
            assert ticker["last"] == 50000.0
            assert ticker["volume"] == 1000.0

    async def test_get_ohlcv(self):
        """Test getting OHLCV data."""
        adapter = OKXAdapter(sandbox=True)

        mock_ohlcv = [
            [1704067200000, 42000.0, 42500.0, 41800.0, 42200.0, 1000.0],
            [1704070800000, 42200.0, 42800.0, 42100.0, 42600.0, 1200.0],
        ]

        with patch("keryxflow.exchange.okx.ccxt") as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock()
            mock_exchange.fetch_ohlcv = AsyncMock(return_value=mock_ohlcv)
            mock_ccxt.okx.return_value = mock_exchange

            await adapter.connect()
            ohlcv = await adapter.get_ohlcv("BTC/USDT", "1h", 100)

            assert len(ohlcv) == 2
            mock_exchange.fetch_ohlcv.assert_called_once_with(
                "BTC/USDT", "1h", since=None, limit=100
            )

    async def test_get_balance(self):
        """Test getting account balance."""
        adapter = OKXAdapter(sandbox=True)

        mock_balance = {
            "total": {"BTC": 1.0, "USDT": 10000.0},
            "free": {"BTC": 0.5, "USDT": 9000.0},
            "used": {"BTC": 0.5, "USDT": 1000.0},
        }

        with patch("keryxflow.exchange.okx.ccxt") as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock()
            mock_exchange.fetch_balance = AsyncMock(return_value=mock_balance)
            mock_ccxt.okx.return_value = mock_exchange

            await adapter.connect()
            balance = await adapter.get_balance()

            assert balance["total"]["BTC"] == 1.0
            assert balance["free"]["USDT"] == 9000.0

    async def test_get_order_book(self):
        """Test getting order book."""
        adapter = OKXAdapter(sandbox=True)

        mock_order_book = {
            "bids": [[49990.0, 1.0], [49980.0, 2.0], [49970.0, 3.0]],
            "asks": [[50010.0, 1.0], [50020.0, 2.0], [50030.0, 3.0]],
            "timestamp": 1234567890000,
        }

        with patch("keryxflow.exchange.okx.ccxt") as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock()
            mock_exchange.fetch_order_book = AsyncMock(return_value=mock_order_book)
            mock_ccxt.okx.return_value = mock_exchange

            await adapter.connect()
            order_book = await adapter.get_order_book("BTC/USDT", limit=2)

            assert order_book["symbol"] == "BTC/USDT"
            assert len(order_book["bids"]) == 2

    async def test_create_market_order_with_tdmode(self):
        """Test creating a market order with cash trade mode."""
        adapter = OKXAdapter(sandbox=True)

        mock_order = {
            "id": "order123",
            "symbol": "BTC/USDT",
            "side": "buy",
            "amount": 0.1,
            "price": 50000.0,
            "status": "closed",
        }

        with patch("keryxflow.exchange.okx.ccxt") as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock()
            mock_exchange.create_market_order = AsyncMock(return_value=mock_order)
            mock_ccxt.okx.return_value = mock_exchange

            await adapter.connect()
            order = await adapter.create_market_order("BTC/USDT", "buy", 0.1)

            assert order["id"] == "order123"
            # Verify tdMode: cash is passed
            mock_exchange.create_market_order.assert_called_once_with(
                "BTC/USDT", "buy", 0.1, params={"tdMode": "cash"}
            )

    async def test_create_limit_order_with_tdmode(self):
        """Test creating a limit order with cash trade mode."""
        adapter = OKXAdapter(sandbox=True)

        mock_order = {
            "id": "order456",
            "symbol": "BTC/USDT",
            "side": "sell",
            "amount": 0.1,
            "price": 55000.0,
            "status": "open",
        }

        with patch("keryxflow.exchange.okx.ccxt") as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock()
            mock_exchange.create_limit_order = AsyncMock(return_value=mock_order)
            mock_ccxt.okx.return_value = mock_exchange

            await adapter.connect()
            order = await adapter.create_limit_order("BTC/USDT", "sell", 0.1, 55000.0)

            assert order["id"] == "order456"
            # Verify tdMode: cash is passed
            mock_exchange.create_limit_order.assert_called_once_with(
                "BTC/USDT", "sell", 0.1, 55000.0, params={"tdMode": "cash"}
            )

    async def test_cancel_order(self):
        """Test cancelling an order."""
        adapter = OKXAdapter(sandbox=True)

        mock_result = {"id": "order123", "status": "cancelled"}

        with patch("keryxflow.exchange.okx.ccxt") as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock()
            mock_exchange.cancel_order = AsyncMock(return_value=mock_result)
            mock_ccxt.okx.return_value = mock_exchange

            await adapter.connect()
            result = await adapter.cancel_order("order123", "BTC/USDT")

            assert result["status"] == "cancelled"

    async def test_get_order(self):
        """Test getting order status."""
        adapter = OKXAdapter(sandbox=True)

        mock_order = {
            "id": "order123",
            "status": "closed",
            "filled": 0.1,
        }

        with patch("keryxflow.exchange.okx.ccxt") as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock()
            mock_exchange.fetch_order = AsyncMock(return_value=mock_order)
            mock_ccxt.okx.return_value = mock_exchange

            await adapter.connect()
            order = await adapter.get_order("order123", "BTC/USDT")

            assert order["status"] == "closed"

    async def test_get_open_orders(self):
        """Test getting open orders."""
        adapter = OKXAdapter(sandbox=True)

        mock_orders = [
            {"id": "order1", "status": "open"},
            {"id": "order2", "status": "open"},
        ]

        with patch("keryxflow.exchange.okx.ccxt") as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock()
            mock_exchange.fetch_open_orders = AsyncMock(return_value=mock_orders)
            mock_ccxt.okx.return_value = mock_exchange

            await adapter.connect()
            orders = await adapter.get_open_orders("BTC/USDT")

            assert len(orders) == 2

    async def test_start_price_feed(self):
        """Test starting price feed."""
        adapter = OKXAdapter(sandbox=True)

        with patch("keryxflow.exchange.okx.ccxt") as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock()
            mock_ccxt.okx.return_value = mock_exchange

            await adapter.connect()
            await adapter.start_price_feed(["BTC/USDT"], interval=1.0)

            assert adapter._running is True
            assert adapter._price_task is not None

            # Clean up
            await adapter.stop_price_feed()

    async def test_stop_price_feed(self):
        """Test stopping price feed."""
        adapter = OKXAdapter(sandbox=True)

        with patch("keryxflow.exchange.okx.ccxt") as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock()
            mock_ccxt.okx.return_value = mock_exchange

            await adapter.connect()
            await adapter.start_price_feed(["BTC/USDT"], interval=1.0)
            await adapter.stop_price_feed()

            assert adapter._running is False
            assert adapter._price_task is None

    async def test_execute_market_order_protocol(self):
        """Test OrderExecutor protocol's execute_market_order."""
        adapter = OKXAdapter(sandbox=True)

        mock_order = {
            "id": "order123",
            "symbol": "BTC/USDT",
            "side": "buy",
            "amount": 0.1,
            "price": 50000.0,
            "status": "closed",
        }

        with patch("keryxflow.exchange.okx.ccxt") as mock_ccxt:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock()
            mock_exchange.create_market_order = AsyncMock(return_value=mock_order)
            mock_ccxt.okx.return_value = mock_exchange

            await adapter.connect()
            order = await adapter.execute_market_order("BTC/USDT", "buy", 0.1)

            assert order["id"] == "order123"

    def test_update_price_noop(self):
        """Test that update_price is a no-op for live exchanges."""
        adapter = OKXAdapter(sandbox=True)
        # Should not raise
        adapter.update_price("BTC/USDT", 50000.0)

    def test_get_price_returns_none(self):
        """Test that get_price returns None for live exchanges."""
        adapter = OKXAdapter(sandbox=True)
        assert adapter.get_price("BTC/USDT") is None


class TestOKXCredentials:
    """Tests for OKX credential handling."""

    async def test_passphrase_passed_as_password(self):
        """Test that OKX passphrase is passed as 'password' in CCXT config."""
        adapter = OKXAdapter(sandbox=True)

        with (
            patch("keryxflow.exchange.okx.ccxt") as mock_ccxt,
            patch("keryxflow.exchange.okx.get_settings") as mock_settings,
        ):
            # Mock settings with OKX credentials
            mock_settings_obj = mock_settings.return_value
            mock_settings_obj.has_okx_credentials = True
            mock_settings_obj.okx_api_key.get_secret_value.return_value = "test_key"
            mock_settings_obj.okx_api_secret.get_secret_value.return_value = "test_secret"
            mock_settings_obj.okx_passphrase.get_secret_value.return_value = "test_passphrase"

            mock_exchange = AsyncMock()
            mock_exchange.fetch_time = AsyncMock()
            mock_ccxt.okx.return_value = mock_exchange

            adapter.settings = mock_settings_obj
            await adapter.connect()

            # Verify passphrase is passed as 'password'
            call_args = mock_ccxt.okx.call_args
            config = call_args[0][0]
            assert config["apiKey"] == "test_key"
            assert config["secret"] == "test_secret"
            assert config["password"] == "test_passphrase"


class TestGetOKXClient:
    """Tests for get_okx_client singleton."""

    def test_returns_okx_adapter(self):
        """Test that it returns an OKXAdapter instance."""
        import keryxflow.exchange.okx as okx_module

        okx_module._okx_client = None

        client = get_okx_client(sandbox=True)
        assert isinstance(client, OKXAdapter)

    def test_returns_same_instance(self):
        """Test singleton pattern."""
        import keryxflow.exchange.okx as okx_module

        okx_module._okx_client = None

        client1 = get_okx_client(sandbox=True)
        client2 = get_okx_client(sandbox=True)

        assert client1 is client2
