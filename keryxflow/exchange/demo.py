"""Demo exchange client with synthetic market data."""

import math
import uuid
from datetime import UTC, datetime
from typing import Any

from keryxflow.core.logging import get_logger
from keryxflow.exchange.adapter import ExchangeAdapter

logger = get_logger(__name__)

# Fixed base timestamp: 2024-01-01 00:00 UTC
_BASE_TIMESTAMP_MS = 1704067200000
_ONE_HOUR_MS = 3600000

_BASE_PRICE = 42000.0
_AMPLITUDE = _BASE_PRICE * 0.02  # 2% = 840
_CYCLE_PERIOD = 24  # 24h sine wave cycle


class DemoExchangeClient(ExchangeAdapter):
    """Exchange client that returns fully synthetic data for demo/testing purposes.

    Provides hardcoded BTC/USDT ticker data, a fake USDT balance,
    and programmatically generated OHLCV candles using a sine wave pattern.
    No exchange connectivity required.
    """

    def __init__(self) -> None:
        self._connected: bool = False
        self._ticker: dict[str, Any] = {
            "symbol": "BTC/USDT",
            "last": 42000.0,
            "bid": 41990.0,
            "ask": 42010.0,
            "high": 42840.0,
            "low": 41160.0,
            "volume": 15000.0,
            "quote_volume": 630000000.0,
            "timestamp": _BASE_TIMESTAMP_MS,
            "datetime": datetime.fromtimestamp(_BASE_TIMESTAMP_MS / 1000, tz=UTC).isoformat(),
        }
        self._candles: list[list[float]] = self._generate_candles()
        self._orders: dict[str, dict[str, Any]] = {}
        logger.info("demo_client_initialized", candles=len(self._candles))

    def _generate_candles(self) -> list[list[float]]:
        """Generate 100 deterministic 1h candles using a sine wave."""
        candles: list[list[float]] = []
        prev_close = _BASE_PRICE

        for i in range(100):
            timestamp = _BASE_TIMESTAMP_MS + i * _ONE_HOUR_MS
            close = _BASE_PRICE + _AMPLITUDE * math.sin(2 * math.pi * i / _CYCLE_PERIOD)
            open_ = prev_close
            high = max(open_, close) + _AMPLITUDE * 0.05
            low = min(open_, close) - _AMPLITUDE * 0.05
            volume = 500.0 + 200.0 * abs(math.sin(i))

            candles.append([timestamp, open_, high, low, close, volume])
            prev_close = close

        return candles

    # --- ExchangeAdapter interface ---

    async def connect(self) -> bool:
        """Simulate connection (always succeeds)."""
        self._connected = True
        logger.info("demo_client_connected")
        return True

    async def disconnect(self) -> None:
        """Simulate disconnection."""
        self._connected = False
        logger.info("demo_client_disconnected")

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected

    async def get_ticker(self, symbol: str = "BTC/USDT") -> dict[str, Any]:
        """Return hardcoded ticker data."""
        logger.debug("demo_fetch_ticker", symbol=symbol)
        return {**self._ticker, "symbol": symbol}

    async def get_balance(self) -> dict[str, Any]:
        """Return a fake balance of 10000 USDT."""
        logger.debug("demo_fetch_balance")
        return {
            "total": {"USDT": 10000.0},
            "free": {"USDT": 10000.0},
            "used": {"USDT": 0.0},
        }

    async def get_ohlcv(
        self,
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
        limit: int = 100,
        since: int | None = None,  # noqa: ARG002
    ) -> list[list[float]]:
        """Return pre-generated OHLCV candles."""
        logger.debug("demo_fetch_ohlcv", symbol=symbol, timeframe=timeframe, limit=limit)
        return self._candles[-limit:]

    async def get_order_book(self, symbol: str = "BTC/USDT", limit: int = 10) -> dict[str, Any]:
        """Return a synthetic order book with 10 levels and 0.1% spread."""
        mid = _BASE_PRICE
        spread_pct = 0.001  # 0.1%
        half_spread = mid * spread_pct / 2

        bids: list[list[float]] = []
        asks: list[list[float]] = []
        for i in range(limit):
            step = mid * 0.0005 * i  # 0.05% between levels
            bid_price = round(mid - half_spread - step, 2)
            ask_price = round(mid + half_spread + step, 2)
            bid_vol = round(0.5 + 0.1 * i, 4)
            ask_vol = round(0.5 + 0.1 * i, 4)
            bids.append([bid_price, bid_vol])
            asks.append([ask_price, ask_vol])

        return {
            "symbol": symbol,
            "bids": bids,
            "asks": asks,
            "timestamp": int(datetime.now(tz=UTC).timestamp() * 1000),
        }

    async def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
    ) -> dict[str, Any]:
        """Create a simulated market order (immediately filled)."""
        return await self._create_order(symbol, side, "market", amount, price=None)

    async def create_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
    ) -> dict[str, Any]:
        """Create a simulated limit order (immediately filled)."""
        return await self._create_order(symbol, side, "limit", amount, price=price)

    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price: float | None = None,
    ) -> dict[str, Any]:
        """Unified order placement."""
        if order_type == "market":
            return await self.create_market_order(symbol, side, amount)
        elif order_type == "limit":
            if price is None:
                raise ValueError("Price is required for limit orders")
            return await self.create_limit_order(symbol, side, amount, price)
        else:
            raise ValueError(f"Unsupported order type: {order_type}")

    async def cancel_order(self, order_id: str, symbol: str = "BTC/USDT") -> dict[str, Any]:
        """Return a success cancellation dict."""
        logger.info("demo_cancel_order", order_id=order_id, symbol=symbol)
        return {"id": order_id, "status": "canceled"}

    async def get_order(self, order_id: str, symbol: str = "BTC/USDT") -> dict[str, Any]:
        """Return stored order or a default filled order."""
        if order_id in self._orders:
            return self._orders[order_id]
        return {
            "id": order_id,
            "symbol": symbol,
            "status": "filled",
        }

    async def get_open_orders(self, symbol: str = "BTC/USDT") -> list[dict[str, Any]]:
        """Return an empty list of open orders."""
        logger.debug("demo_fetch_open_orders", symbol=symbol)
        return []

    async def start_price_feed(
        self,
        symbols: list[str] | None = None,
        interval: float = 1.0,
    ) -> None:
        """No-op for demo client."""
        logger.debug("demo_start_price_feed", symbols=symbols, interval=interval)

    async def stop_price_feed(self) -> None:
        """No-op for demo client."""
        logger.debug("demo_stop_price_feed")

    # --- Internal helpers ---

    async def _create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price: float | None = None,
    ) -> dict[str, Any]:
        """Log the order and return a fake order dict."""
        order_id = str(uuid.uuid4())
        logger.info(
            "demo_create_order",
            order_id=order_id,
            symbol=symbol,
            side=side,
            type=order_type,
            amount=amount,
            price=price,
        )
        order = {
            "id": order_id,
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "amount": amount,
            "price": price or _BASE_PRICE,
            "status": "filled",
            "timestamp": int(datetime.now(tz=UTC).timestamp() * 1000),
        }
        self._orders[order_id] = order
        return order


# Global singleton
_demo_client: DemoExchangeClient | None = None


def get_demo_client() -> DemoExchangeClient:
    """Get the global demo exchange client instance."""
    global _demo_client
    if _demo_client is None:
        _demo_client = DemoExchangeClient()
    return _demo_client
