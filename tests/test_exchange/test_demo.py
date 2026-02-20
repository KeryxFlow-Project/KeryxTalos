"""Tests for demo mode integration."""

import os

import pytest


class TestDemoModeFactory:
    """Test that get_exchange_client returns the correct client based on demo_mode."""

    def test_get_client_returns_demo_when_demo_mode_true(self):
        """get_exchange_client() returns DemoExchangeClient when demo_mode=True."""
        os.environ["KERYXFLOW_DEMO_MODE"] = "true"

        from keryxflow.exchange.client import get_exchange_client
        from keryxflow.exchange.demo import DemoExchangeClient

        client = get_exchange_client()
        assert isinstance(client, DemoExchangeClient)

    def test_get_client_returns_exchange_when_demo_mode_false(self):
        """get_exchange_client() returns ExchangeClient when demo_mode is not set."""
        os.environ.pop("KERYXFLOW_DEMO_MODE", None)

        from keryxflow.exchange.client import ExchangeClient, get_exchange_client

        client = get_exchange_client()
        assert isinstance(client, ExchangeClient)


class TestDemoExchangeClient:
    """Test DemoExchangeClient basic functionality."""

    @pytest.fixture
    def demo_client(self):
        os.environ["KERYXFLOW_DEMO_MODE"] = "true"
        from keryxflow.exchange.demo import DemoExchangeClient

        return DemoExchangeClient()

    @pytest.mark.asyncio
    async def test_connect_succeeds(self, demo_client):
        result = await demo_client.connect()
        assert result is True
        assert demo_client.is_connected is True

    @pytest.mark.asyncio
    async def test_disconnect(self, demo_client):
        await demo_client.connect()
        await demo_client.disconnect()
        assert demo_client.is_connected is False

    @pytest.mark.asyncio
    async def test_get_ticker_returns_expected_shape(self, demo_client):
        ticker = await demo_client.get_ticker("BTC/USDT")
        assert ticker["symbol"] == "BTC/USDT"
        assert isinstance(ticker["last"], float)
        assert isinstance(ticker["bid"], float)
        assert isinstance(ticker["ask"], float)
        assert ticker["bid"] < ticker["ask"]

    @pytest.mark.asyncio
    async def test_get_ohlcv_returns_correct_count(self, demo_client):
        candles = await demo_client.get_ohlcv("BTC/USDT", timeframe="1h", limit=50)
        assert len(candles) == 50
        # Each candle should be [timestamp, open, high, low, close, volume]
        for candle in candles:
            assert len(candle) == 6
            _ts, o, h, low, c, _v = candle
            assert h >= o and h >= c  # high is the highest
            assert low <= o and low <= c  # low is the lowest

    @pytest.mark.asyncio
    async def test_get_balance(self, demo_client):
        balance = await demo_client.get_balance()
        assert "total" in balance
        assert "free" in balance
        assert "used" in balance
        assert balance["total"]["USDT"] == 10000.0

    @pytest.mark.asyncio
    async def test_create_market_order(self, demo_client):
        order = await demo_client.create_market_order("BTC/USDT", "buy", 0.1)
        assert order["symbol"] == "BTC/USDT"
        assert order["side"] == "buy"
        assert order["status"] == "closed"
        assert order["filled"] == 0.1

    @pytest.mark.asyncio
    async def test_get_order_book(self, demo_client):
        book = await demo_client.get_order_book("BTC/USDT", limit=5)
        assert book["symbol"] == "BTC/USDT"
        assert len(book["bids"]) == 5
        assert len(book["asks"]) == 5
