"""Tests for DemoExchangeClient and demo mode integration."""

import os

import pytest

from keryxflow.exchange.adapter import ExchangeAdapter
from keryxflow.exchange.demo import DemoExchangeClient, get_demo_client


class TestDemoExchangeClientInterface:
    """DemoExchangeClient implements ExchangeAdapter."""

    def test_is_subclass_of_exchange_adapter(self):
        assert issubclass(DemoExchangeClient, ExchangeAdapter)

    def test_instance_is_exchange_adapter(self):
        client = DemoExchangeClient()
        assert isinstance(client, ExchangeAdapter)


class TestDemoSingleton:
    """get_demo_client singleton behavior."""

    def test_returns_same_instance(self):
        c1 = get_demo_client()
        c2 = get_demo_client()
        assert c1 is c2

    def test_returns_demo_exchange_client(self):
        client = get_demo_client()
        assert isinstance(client, DemoExchangeClient)


class TestDemoConnectDisconnect:
    """Connection lifecycle."""

    async def test_connect(self):
        client = DemoExchangeClient()
        assert not client.is_connected
        result = await client.connect()
        assert result is True
        assert client.is_connected

    async def test_disconnect(self):
        client = DemoExchangeClient()
        await client.connect()
        await client.disconnect()
        assert not client.is_connected


class TestDemoTicker:
    """Ticker data."""

    async def test_get_ticker_returns_data(self):
        client = DemoExchangeClient()
        ticker = await client.get_ticker("BTC/USDT")
        assert ticker["symbol"] == "BTC/USDT"
        assert ticker["last"] == 42000.0
        assert "bid" in ticker
        assert "ask" in ticker

    async def test_get_ticker_uses_requested_symbol(self):
        client = DemoExchangeClient()
        ticker = await client.get_ticker("ETH/USDT")
        assert ticker["symbol"] == "ETH/USDT"


class TestDemoOHLCV:
    """OHLCV candle data."""

    async def test_get_ohlcv_returns_candles(self):
        client = DemoExchangeClient()
        candles = await client.get_ohlcv("BTC/USDT", "1h", limit=10)
        assert len(candles) == 10
        for candle in candles:
            assert len(candle) == 6  # [timestamp, open, high, low, close, volume]

    async def test_get_ohlcv_respects_limit(self):
        client = DemoExchangeClient()
        candles = await client.get_ohlcv("BTC/USDT", "1h", limit=5)
        assert len(candles) == 5


class TestDemoBalance:
    """Balance data."""

    async def test_get_balance(self):
        client = DemoExchangeClient()
        balance = await client.get_balance()
        assert balance["total"]["USDT"] == 10000.0
        assert balance["free"]["USDT"] == 10000.0


class TestDemoOrderBook:
    """Order book data."""

    async def test_get_order_book(self):
        client = DemoExchangeClient()
        book = await client.get_order_book("BTC/USDT", limit=5)
        assert len(book["bids"]) == 5
        assert len(book["asks"]) == 5
        assert book["symbol"] == "BTC/USDT"


class TestDemoOrders:
    """Order creation and management."""

    async def test_create_market_order(self):
        client = DemoExchangeClient()
        order = await client.create_market_order("BTC/USDT", "buy", 0.1)
        assert order["symbol"] == "BTC/USDT"
        assert order["side"] == "buy"
        assert order["type"] == "market"
        assert order["amount"] == 0.1
        assert order["status"] == "filled"

    async def test_create_limit_order(self):
        client = DemoExchangeClient()
        order = await client.create_limit_order("BTC/USDT", "sell", 0.5, 45000.0)
        assert order["symbol"] == "BTC/USDT"
        assert order["side"] == "sell"
        assert order["type"] == "limit"
        assert order["price"] == 45000.0
        assert order["status"] == "filled"

    async def test_place_order_market(self):
        client = DemoExchangeClient()
        order = await client.place_order("BTC/USDT", "buy", "market", 0.1)
        assert order["type"] == "market"
        assert order["status"] == "filled"

    async def test_place_order_limit(self):
        client = DemoExchangeClient()
        order = await client.place_order("BTC/USDT", "buy", "limit", 0.1, price=40000.0)
        assert order["type"] == "limit"
        assert order["price"] == 40000.0

    async def test_place_order_limit_requires_price(self):
        client = DemoExchangeClient()
        with pytest.raises(ValueError, match="Price is required"):
            await client.place_order("BTC/USDT", "buy", "limit", 0.1)

    async def test_place_order_unsupported_type(self):
        client = DemoExchangeClient()
        with pytest.raises(ValueError, match="Unsupported order type"):
            await client.place_order("BTC/USDT", "buy", "stop_limit", 0.1)

    async def test_cancel_order(self):
        client = DemoExchangeClient()
        result = await client.cancel_order("order-123", "BTC/USDT")
        assert result["id"] == "order-123"
        assert result["status"] == "canceled"

    async def test_get_order(self):
        client = DemoExchangeClient()
        order = await client.create_market_order("BTC/USDT", "buy", 0.1)
        retrieved = await client.get_order(order["id"], "BTC/USDT")
        assert retrieved["id"] == order["id"]
        assert retrieved["status"] == "filled"

    async def test_get_order_unknown(self):
        client = DemoExchangeClient()
        result = await client.get_order("unknown-id", "BTC/USDT")
        assert result["id"] == "unknown-id"
        assert result["status"] == "filled"

    async def test_get_open_orders(self):
        client = DemoExchangeClient()
        orders = await client.get_open_orders("BTC/USDT")
        assert orders == []


class TestDemoPriceFeed:
    """Price feed no-ops."""

    async def test_start_price_feed(self):
        client = DemoExchangeClient()
        await client.start_price_feed(["BTC/USDT"], interval=1.0)

    async def test_stop_price_feed(self):
        client = DemoExchangeClient()
        await client.stop_price_feed()


class TestDemoModeFactory:
    """Factory returns DemoExchangeClient when mode is 'demo'."""

    def test_factory_returns_demo_client_in_demo_mode(self):
        os.environ["KERYXFLOW_MODE"] = "demo"
        import keryxflow.config as config_module

        config_module._settings = None

        from keryxflow.exchange import get_exchange_adapter

        client = get_exchange_adapter(sandbox=False)
        assert isinstance(client, DemoExchangeClient)
