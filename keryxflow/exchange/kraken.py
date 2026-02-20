"""CCXT async wrapper for Kraken exchange connectivity."""

import asyncio
import contextlib
from typing import Any

import ccxt.async_support as ccxt
from tenacity import retry, stop_after_attempt, wait_exponential

from keryxflow.config import get_settings
from keryxflow.core.events import get_event_bus, price_update_event
from keryxflow.core.logging import LogMessages, get_logger
from keryxflow.exchange.adapter import ExchangeAdapter

logger = get_logger(__name__)


class KrakenClient(ExchangeAdapter):
    """
    Async wrapper for Kraken exchange connectivity via CCXT.

    Handles connection, price feeds, and order execution with
    automatic retry and rate limiting.
    """

    def __init__(self, sandbox: bool = True):
        """Initialize the Kraken client.

        Args:
            sandbox: Whether to use sandbox/testnet mode
        """
        self.settings = get_settings()
        self.event_bus = get_event_bus()
        self._exchange: ccxt.kraken | None = None
        self._sandbox = sandbox
        self._running = False
        self._price_task: asyncio.Task | None = None

    async def connect(self) -> bool:
        """Connect to the exchange.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            config: dict[str, Any] = {
                "enableRateLimit": True,
                "options": {
                    "defaultType": "spot",
                    "adjustForTimeDifference": True,
                },
            }

            # Add API credentials if available
            if self.settings.has_kraken_credentials:
                config["apiKey"] = self.settings.kraken_api_key.get_secret_value()
                config["secret"] = self.settings.kraken_api_secret.get_secret_value()

            self._exchange = ccxt.kraken(config)

            # Enable sandbox mode if requested
            if self._sandbox:
                self._exchange.set_sandbox_mode(True)
                logger.info("exchange_sandbox_mode_enabled")

            # Test connection by fetching time
            await self._exchange.fetch_time()

            msg = LogMessages.connection_status("Kraken", "connected")
            logger.info(msg.technical)

            return True

        except ccxt.NetworkError as e:
            logger.error("exchange_network_error", error=str(e))
            return False
        except ccxt.ExchangeError as e:
            logger.error("exchange_error", error=str(e))
            return False
        except Exception as e:
            logger.error("exchange_connection_failed", error=str(e))
            return False

    async def disconnect(self) -> None:
        """Disconnect from the exchange."""
        await self.stop_price_feed()

        if self._exchange:
            await self._exchange.close()
            self._exchange = None

            msg = LogMessages.connection_status("Kraken", "disconnected")
            logger.info(msg.technical)

    @property
    def is_connected(self) -> bool:
        """Check if connected to exchange."""
        return self._exchange is not None

    def _ensure_connected(self) -> None:
        """Raise error if not connected."""
        if not self.is_connected:
            raise RuntimeError("Not connected to exchange. Call connect() first.")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def get_ticker(self, symbol: str) -> dict[str, Any]:
        """Get current ticker for a symbol.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")

        Returns:
            Ticker data with last price, bid, ask, volume, etc.
        """
        self._ensure_connected()
        assert self._exchange is not None

        ticker = await self._exchange.fetch_ticker(symbol)
        return {
            "symbol": ticker["symbol"],
            "last": ticker["last"],
            "bid": ticker["bid"],
            "ask": ticker["ask"],
            "high": ticker["high"],
            "low": ticker["low"],
            "volume": ticker["baseVolume"],
            "quote_volume": ticker["quoteVolume"],
            "timestamp": ticker["timestamp"],
            "datetime": ticker["datetime"],
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 100,
        since: int | None = None,
    ) -> list[list[float]]:
        """Get OHLCV (candlestick) data.

        Args:
            symbol: Trading pair
            timeframe: Candle timeframe (1m, 5m, 15m, 1h, 4h, 1d)
            limit: Number of candles to fetch
            since: Timestamp in milliseconds for start time (optional)

        Returns:
            List of [timestamp, open, high, low, close, volume]
        """
        self._ensure_connected()
        assert self._exchange is not None

        ohlcv = await self._exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)

        return ohlcv

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def get_balance(self) -> dict[str, dict[str, float]]:
        """Get account balance.

        Returns:
            Balance dict with total, free, and used amounts per currency
        """
        self._ensure_connected()
        assert self._exchange is not None

        balance = await self._exchange.fetch_balance()
        return {
            "total": balance["total"],
            "free": balance["free"],
            "used": balance["used"],
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def get_order_book(self, symbol: str, limit: int = 10) -> dict[str, Any]:
        """Get order book for a symbol.

        Args:
            symbol: Trading pair
            limit: Depth of order book

        Returns:
            Order book with bids and asks
        """
        self._ensure_connected()
        assert self._exchange is not None

        order_book = await self._exchange.fetch_order_book(symbol, limit)
        return {
            "symbol": symbol,
            "bids": order_book["bids"][:limit],
            "asks": order_book["asks"][:limit],
            "timestamp": order_book["timestamp"],
        }

    async def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
    ) -> dict[str, Any]:
        """Create a market order.

        Args:
            symbol: Trading pair
            side: "buy" or "sell"
            amount: Amount to trade

        Returns:
            Order result
        """
        self._ensure_connected()
        assert self._exchange is not None

        order = await self._exchange.create_market_order(symbol, side, amount)
        logger.info(
            "market_order_created",
            symbol=symbol,
            side=side,
            amount=amount,
            order_id=order["id"],
        )
        return order

    async def create_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
    ) -> dict[str, Any]:
        """Create a limit order.

        Args:
            symbol: Trading pair
            side: "buy" or "sell"
            amount: Amount to trade
            price: Limit price

        Returns:
            Order result
        """
        self._ensure_connected()
        assert self._exchange is not None

        order = await self._exchange.create_limit_order(symbol, side, amount, price)
        logger.info(
            "limit_order_created",
            symbol=symbol,
            side=side,
            amount=amount,
            price=price,
            order_id=order["id"],
        )
        return order

    async def cancel_order(self, order_id: str, symbol: str) -> dict[str, Any]:
        """Cancel an order.

        Args:
            order_id: Order ID to cancel
            symbol: Trading pair

        Returns:
            Cancellation result
        """
        self._ensure_connected()
        assert self._exchange is not None

        result = await self._exchange.cancel_order(order_id, symbol)
        logger.info("order_cancelled", order_id=order_id, symbol=symbol)
        return result

    async def get_order(self, order_id: str, symbol: str) -> dict[str, Any]:
        """Get order status.

        Args:
            order_id: Order ID
            symbol: Trading pair

        Returns:
            Order details
        """
        self._ensure_connected()
        assert self._exchange is not None

        return await self._exchange.fetch_order(order_id, symbol)

    async def get_open_orders(self, symbol: str) -> list[dict[str, Any]]:
        """Get open orders for a symbol.

        Args:
            symbol: Trading pair

        Returns:
            List of open orders
        """
        self._ensure_connected()
        assert self._exchange is not None

        return await self._exchange.fetch_open_orders(symbol)

    async def start_price_feed(
        self,
        symbols: list[str] | None = None,
        interval: float = 1.0,
    ) -> None:
        """Start streaming price updates.

        Args:
            symbols: List of symbols to watch (default from settings)
            interval: Update interval in seconds
        """
        if self._running:
            return

        if symbols is None:
            symbols = self.settings.system.symbols

        self._running = True
        self._price_task = asyncio.create_task(self._price_feed_loop(symbols, interval))
        logger.info("price_feed_started", symbols=symbols, interval=interval)

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

        logger.info("price_feed_stopped")

    async def _price_feed_loop(self, symbols: list[str], interval: float) -> None:
        """Internal price feed loop.

        Args:
            symbols: Symbols to watch
            interval: Update interval
        """
        while self._running:
            try:
                for symbol in symbols:
                    if not self._running:
                        break

                    try:
                        ticker = await self.get_ticker(symbol)
                        price = ticker["last"]
                        volume = ticker["volume"]

                        # Publish price update event
                        await self.event_bus.publish(price_update_event(symbol, price, volume))

                        msg = LogMessages.price_update(symbol, price)
                        logger.debug(msg.technical)

                    except Exception as e:
                        logger.warning(
                            "price_fetch_error",
                            symbol=symbol,
                            error=str(e),
                        )

                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("price_feed_error", error=str(e))
                await asyncio.sleep(interval)


# Global client instance
_kraken_client: KrakenClient | None = None


def get_kraken_client(sandbox: bool = True) -> KrakenClient:
    """Get the global Kraken client instance."""
    global _kraken_client
    if _kraken_client is None:
        _kraken_client = KrakenClient(sandbox=sandbox)
    return _kraken_client
