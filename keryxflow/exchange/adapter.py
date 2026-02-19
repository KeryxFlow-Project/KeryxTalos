"""Abstract base class for exchange adapters."""

import abc
from typing import Any


class ExchangeAdapter(abc.ABC):
    """
    Abstract base class defining the exchange connectivity interface.

    All exchange implementations (Binance, Bybit, etc.) must implement
    this interface to be used interchangeably in the trading engine.
    """

    @abc.abstractmethod
    async def connect(self) -> bool:
        """Connect to the exchange.

        Returns:
            True if connection successful, False otherwise
        """

    @abc.abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the exchange."""

    @property
    @abc.abstractmethod
    def is_connected(self) -> bool:
        """Check if connected to exchange."""

    @abc.abstractmethod
    async def get_ticker(self, symbol: str) -> dict[str, Any]:
        """Get current ticker for a symbol.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")

        Returns:
            Ticker data with last price, bid, ask, volume, etc.
        """

    @abc.abstractmethod
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

    @abc.abstractmethod
    async def get_balance(self) -> dict[str, dict[str, float]]:
        """Get account balance.

        Returns:
            Balance dict with total, free, and used amounts per currency
        """

    @abc.abstractmethod
    async def get_order_book(self, symbol: str, limit: int = 10) -> dict[str, Any]:
        """Get order book for a symbol.

        Args:
            symbol: Trading pair
            limit: Depth of order book

        Returns:
            Order book with bids and asks
        """

    @abc.abstractmethod
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

    @abc.abstractmethod
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

    @abc.abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> dict[str, Any]:
        """Cancel an order.

        Args:
            order_id: Order ID to cancel
            symbol: Trading pair

        Returns:
            Cancellation result
        """

    @abc.abstractmethod
    async def get_order(self, order_id: str, symbol: str) -> dict[str, Any]:
        """Get order status.

        Args:
            order_id: Order ID
            symbol: Trading pair

        Returns:
            Order details
        """

    @abc.abstractmethod
    async def get_open_orders(self, symbol: str) -> list[dict[str, Any]]:
        """Get open orders for a symbol.

        Args:
            symbol: Trading pair

        Returns:
            List of open orders
        """

    @abc.abstractmethod
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

    @abc.abstractmethod
    async def stop_price_feed(self) -> None:
        """Stop the price feed."""
