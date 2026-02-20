"""Demo exchange client with synthetic data for zero-dependency trading demos."""

import asyncio
import contextlib
import random
import time
import uuid
from typing import Any

from keryxflow.config import get_settings
from keryxflow.core.events import get_event_bus, price_update_event
from keryxflow.core.logging import get_logger

logger = get_logger(__name__)

# Default seed prices for common symbols
_DEFAULT_PRICES: dict[str, float] = {
    "BTC/USDT": 50000.0,
    "ETH/USDT": 3000.0,
    "SOL/USDT": 100.0,
    "BNB/USDT": 350.0,
}

_DEFAULT_FALLBACK_PRICE = 100.0


class DemoExchangeClient:
    """Exchange client returning synthetic data without network calls.

    Implements the same interface as ExchangeClient so it can be used
    as a drop-in replacement via the get_exchange_client() factory.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.event_bus = get_event_bus()
        self._connected = False
        self._running = False
        self._price_task: asyncio.Task[None] | None = None
        self._prices: dict[str, float] = {}
        self._orders: dict[str, dict[str, Any]] = {}
        self._order_counter = 0

    async def connect(self) -> bool:
        """Connect (always succeeds — no network needed)."""
        self._connected = True
        logger.info("demo_exchange_connected")
        return True

    async def disconnect(self) -> None:
        """Disconnect from the demo exchange."""
        await self.stop_price_feed()
        self._connected = False
        logger.info("demo_exchange_disconnected")

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected

    def _get_price(self, symbol: str) -> float:
        """Get current synthetic price for a symbol, initializing if needed."""
        if symbol not in self._prices:
            self._prices[symbol] = _DEFAULT_PRICES.get(symbol, _DEFAULT_FALLBACK_PRICE)
        return self._prices[symbol]

    def _tick_price(self, symbol: str) -> float:
        """Advance the price by a small random walk step."""
        price = self._get_price(symbol)
        price *= 1 + random.gauss(0, 0.001)
        price = max(price, 0.01)  # floor to prevent negative prices
        self._prices[symbol] = price
        return price

    async def get_ticker(self, symbol: str) -> dict[str, Any]:
        """Get synthetic ticker data."""
        price = self._tick_price(symbol)
        spread = price * 0.0005
        now_ms = int(time.time() * 1000)
        return {
            "symbol": symbol,
            "last": price,
            "bid": price - spread,
            "ask": price + spread,
            "high": price * 1.01,
            "low": price * 0.99,
            "volume": random.uniform(100, 5000),
            "quote_volume": random.uniform(1_000_000, 50_000_000),
            "timestamp": now_ms,
            "datetime": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        }

    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 100,
        since: int | None = None,
    ) -> list[list[float]]:
        """Generate synthetic OHLCV candles."""
        base_price = self._get_price(symbol)

        # Map timeframe to interval in ms
        tf_ms: dict[str, int] = {
            "1m": 60_000,
            "5m": 300_000,
            "15m": 900_000,
            "1h": 3_600_000,
            "4h": 14_400_000,
            "1d": 86_400_000,
        }
        interval = tf_ms.get(timeframe, 3_600_000)
        now_ms = int(time.time() * 1000)

        start_ts = since if since is not None else now_ms - limit * interval

        candles: list[list[float]] = []
        price = base_price * 0.98  # start slightly below current

        for i in range(limit):
            ts = start_ts + i * interval
            open_price = price
            # random walk within candle
            change1 = price * random.gauss(0, 0.005)
            change2 = price * random.gauss(0, 0.005)
            close_price = open_price + change1
            high_price = max(open_price, close_price) + abs(change2)
            low_price = min(open_price, close_price) - abs(change2)
            low_price = max(low_price, 0.01)
            volume = random.uniform(50, 2000)

            candles.append([ts, open_price, high_price, low_price, close_price, volume])
            price = close_price

        return candles

    async def get_balance(self) -> dict[str, dict[str, float]]:
        """Return a static demo balance."""
        return {
            "total": {"USDT": 10000.0, "BTC": 0.0, "ETH": 0.0},
            "free": {"USDT": 10000.0, "BTC": 0.0, "ETH": 0.0},
            "used": {"USDT": 0.0, "BTC": 0.0, "ETH": 0.0},
        }

    async def get_order_book(self, symbol: str, limit: int = 10) -> dict[str, Any]:
        """Return a synthetic order book around current price."""
        price = self._get_price(symbol)
        spread = price * 0.0005
        bids = [[price - spread * (i + 1), random.uniform(0.01, 1.0)] for i in range(limit)]
        asks = [[price + spread * (i + 1), random.uniform(0.01, 1.0)] for i in range(limit)]
        return {
            "symbol": symbol,
            "bids": bids,
            "asks": asks,
            "timestamp": int(time.time() * 1000),
        }

    async def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
    ) -> dict[str, Any]:
        """Simulate a market order fill at current synthetic price."""
        price = self._get_price(symbol)
        order_id = str(uuid.uuid4())[:8]
        order = {
            "id": order_id,
            "symbol": symbol,
            "type": "market",
            "side": side,
            "amount": amount,
            "price": price,
            "cost": price * amount,
            "status": "closed",
            "filled": amount,
            "remaining": 0.0,
            "timestamp": int(time.time() * 1000),
        }
        self._orders[order_id] = order
        logger.info(
            "demo_market_order",
            symbol=symbol,
            side=side,
            amount=amount,
            price=price,
            order_id=order_id,
        )
        return order

    async def create_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
    ) -> dict[str, Any]:
        """Simulate a limit order (stored as open, no fill matching)."""
        order_id = str(uuid.uuid4())[:8]
        order = {
            "id": order_id,
            "symbol": symbol,
            "type": "limit",
            "side": side,
            "amount": amount,
            "price": price,
            "cost": 0.0,
            "status": "open",
            "filled": 0.0,
            "remaining": amount,
            "timestamp": int(time.time() * 1000),
        }
        self._orders[order_id] = order
        logger.info(
            "demo_limit_order",
            symbol=symbol,
            side=side,
            amount=amount,
            price=price,
            order_id=order_id,
        )
        return order

    async def cancel_order(self, order_id: str, symbol: str) -> dict[str, Any]:
        """Cancel a demo order."""
        if order_id in self._orders:
            self._orders[order_id]["status"] = "canceled"
            logger.info("demo_order_cancelled", order_id=order_id, symbol=symbol)
            return self._orders[order_id]
        return {"id": order_id, "symbol": symbol, "status": "canceled"}

    async def get_order(self, order_id: str, symbol: str) -> dict[str, Any]:
        """Get order status."""
        if order_id in self._orders:
            return self._orders[order_id]
        return {"id": order_id, "symbol": symbol, "status": "unknown"}

    async def start_price_feed(
        self,
        symbols: list[str] | None = None,
        interval: float = 1.0,
    ) -> None:
        """Start synthetic price feed loop."""
        if self._running:
            return

        feed_symbols = symbols if symbols is not None else self.settings.system.symbols

        self._running = True
        self._price_task = asyncio.create_task(self._price_feed_loop(feed_symbols, interval))
        logger.info("demo_price_feed_started", symbols=symbols, interval=interval)

    async def stop_price_feed(self) -> None:
        """Stop the price feed."""
        if not self._running:
            return

        self._running = False

        if self._price_task:
            self._price_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._price_task
            self._price_task = None

        logger.info("demo_price_feed_stopped")

    async def _price_feed_loop(self, symbols: list[str], interval: float) -> None:
        """Internal price feed loop publishing synthetic price updates."""
        while self._running:
            try:
                for symbol in symbols:
                    if not self._running:
                        break
                    try:
                        ticker = await self.get_ticker(symbol)
                        await self.event_bus.publish(
                            price_update_event(symbol, ticker["last"], ticker["volume"])
                        )
                    except Exception as e:
                        logger.warning("demo_price_feed_error", symbol=symbol, error=str(e))

                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("demo_price_feed_loop_error", error=str(e))
                await asyncio.sleep(interval)
