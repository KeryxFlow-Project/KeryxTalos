"""Tests for ExchangeAdapter abstract interface and factory."""

from unittest.mock import AsyncMock, patch

import pytest

from keryxflow.exchange.adapter import ExchangeAdapter
from keryxflow.exchange.client import ExchangeClient, get_exchange_client


class TestExchangeAdapterABC:
    """Tests for the ExchangeAdapter abstract base class."""

    def test_cannot_instantiate_abc(self):
        """ExchangeAdapter cannot be instantiated directly."""
        with pytest.raises(TypeError, match="abstract"):
            ExchangeAdapter()

    def test_incomplete_subclass_cannot_instantiate(self):
        """A subclass missing abstract methods cannot be instantiated."""

        class IncompleteAdapter(ExchangeAdapter):
            async def connect(self) -> bool:
                return True

        with pytest.raises(TypeError, match="abstract"):
            IncompleteAdapter()

    def test_exchange_client_is_subclass(self):
        """ExchangeClient is a subclass of ExchangeAdapter."""
        assert issubclass(ExchangeClient, ExchangeAdapter)

    def test_exchange_client_is_instance(self):
        """An ExchangeClient instance is an instance of ExchangeAdapter."""
        client = ExchangeClient(sandbox=True)
        assert isinstance(client, ExchangeAdapter)


class TestExchangeClientPlaceOrder:
    """Tests for the new place_order unified method."""

    async def test_place_market_order_dispatches(self):
        """place_order with type='market' calls create_market_order."""
        client = ExchangeClient(sandbox=True)
        client.create_market_order = AsyncMock(return_value={"id": "123"})

        result = await client.place_order("BTC/USDT", "buy", "market", 0.1)

        client.create_market_order.assert_called_once_with("BTC/USDT", "buy", 0.1)
        assert result == {"id": "123"}

    async def test_place_limit_order_dispatches(self):
        """place_order with type='limit' calls create_limit_order."""
        client = ExchangeClient(sandbox=True)
        client.create_limit_order = AsyncMock(return_value={"id": "456"})

        result = await client.place_order("BTC/USDT", "buy", "limit", 0.1, price=50000.0)

        client.create_limit_order.assert_called_once_with("BTC/USDT", "buy", 0.1, 50000.0)
        assert result == {"id": "456"}

    async def test_place_limit_order_requires_price(self):
        """place_order with type='limit' raises ValueError if no price."""
        client = ExchangeClient(sandbox=True)

        with pytest.raises(ValueError, match="Price is required"):
            await client.place_order("BTC/USDT", "buy", "limit", 0.1)

    async def test_place_order_unsupported_type(self):
        """place_order raises ValueError for unsupported order types."""
        client = ExchangeClient(sandbox=True)

        with pytest.raises(ValueError, match="Unsupported order type"):
            await client.place_order("BTC/USDT", "buy", "stop_limit", 0.1)


class TestExchangeClientGetOpenOrders:
    """Tests for the new get_open_orders method."""

    async def test_get_open_orders_calls_ccxt(self):
        """get_open_orders wraps CCXT fetch_open_orders."""
        client = ExchangeClient(sandbox=True)
        mock_exchange = AsyncMock()
        mock_exchange.fetch_open_orders = AsyncMock(
            return_value=[{"id": "1", "symbol": "BTC/USDT"}]
        )
        client._exchange = mock_exchange

        result = await client.get_open_orders("BTC/USDT")

        mock_exchange.fetch_open_orders.assert_called_once_with("BTC/USDT")
        assert result == [{"id": "1", "symbol": "BTC/USDT"}]

    async def test_get_open_orders_requires_connection(self):
        """get_open_orders raises RuntimeError if not connected."""
        client = ExchangeClient(sandbox=True)

        with pytest.raises(RuntimeError, match="Not connected"):
            await client.get_open_orders("BTC/USDT")


class TestExchangeFactory:
    """Tests for the exchange client singleton factory."""

    def test_factory_returns_exchange_client_for_binance(self):
        """Factory returns ExchangeClient for 'binance' setting."""
        client = get_exchange_client(sandbox=True)
        assert isinstance(client, ExchangeClient)
        assert isinstance(client, ExchangeAdapter)

    def test_factory_raises_for_unsupported_exchange(self):
        """Factory raises ValueError for unsupported exchange names."""
        import keryxflow.exchange.client as client_module

        client_module._client = None

        with patch("keryxflow.exchange.client.get_settings") as mock_get_settings:
            mock_settings = mock_get_settings.return_value
            mock_settings.system.exchange = "kraken"

            with pytest.raises(ValueError, match="Unsupported exchange.*kraken"):
                get_exchange_client(sandbox=True)

        client_module._client = None

    def test_factory_returns_singleton(self):
        """Factory returns the same instance on subsequent calls."""
        client1 = get_exchange_client(sandbox=True)
        client2 = get_exchange_client(sandbox=True)
        assert client1 is client2
