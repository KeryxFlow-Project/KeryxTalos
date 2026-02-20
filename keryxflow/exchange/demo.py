"""Demo exchange client with synthetic market data."""

import math
import uuid
from datetime import UTC, datetime
from typing import Any

from keryxflow.core.logging import get_logger

logger = get_logger(__name__)

# Fixed base timestamp: 2024-01-01 00:00 UTC
_BASE_TIMESTAMP_MS = 1704067200000
_ONE_HOUR_MS = 3600000

_BASE_PRICE = 42000.0
_AMPLITUDE = _BASE_PRICE * 0.02  # 2% = 840
_CYCLE_PERIOD = 24  # 24h sine wave cycle


class DemoExchangeClient:
    """Exchange client that returns fully synthetic data for demo/testing purposes.

    Provides hardcoded BTC/USDT ticker data, a fake USDT balance,
    and programmatically generated OHLCV candles using a sine wave pattern.
    No exchange connectivity required.
    """

    def __init__(self) -> None:
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

    async def fetch_ticker(self, symbol: str = "BTC/USDT") -> dict[str, Any]:
        """Return hardcoded ticker data."""
        logger.debug("demo_fetch_ticker", symbol=symbol)
        return {**self._ticker, "symbol": symbol}

    async def fetch_balance(self) -> dict[str, Any]:
        """Return a fake balance of 10000 USDT."""
        logger.debug("demo_fetch_balance")
        return {
            "total": {"USDT": 10000.0},
            "free": {"USDT": 10000.0},
            "used": {"USDT": 0.0},
        }

    async def fetch_ohlcv(
        self,
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
        limit: int = 100,
    ) -> list[list[float]]:
        """Return pre-generated OHLCV candles."""
        logger.debug("demo_fetch_ohlcv", symbol=symbol, timeframe=timeframe, limit=limit)
        return self._candles[-limit:]

    async def create_order(
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
        return {
            "id": order_id,
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "amount": amount,
            "price": price or _BASE_PRICE,
            "status": "filled",
            "timestamp": int(datetime.now(tz=UTC).timestamp() * 1000),
        }

    async def cancel_order(self, order_id: str, symbol: str = "BTC/USDT") -> dict[str, Any]:
        """Return a success cancellation dict."""
        logger.info("demo_cancel_order", order_id=order_id, symbol=symbol)
        return {"id": order_id, "status": "canceled"}

    async def fetch_open_orders(self, symbol: str = "BTC/USDT") -> list[dict[str, Any]]:
        """Return an empty list of open orders."""
        logger.debug("demo_fetch_open_orders", symbol=symbol)
        return []

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


# Global singleton
_demo_client: DemoExchangeClient | None = None


def get_demo_client() -> DemoExchangeClient:
    """Get the global demo exchange client instance."""
    global _demo_client
    if _demo_client is None:
        _demo_client = DemoExchangeClient()
    return _demo_client
