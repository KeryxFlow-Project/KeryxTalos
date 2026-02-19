"""Abstract exchange adapter interface."""

from abc import ABC, abstractmethod
from typing import Any


class ExchangeAdapter(ABC):
    """
    Abstract base class for exchange connectivity.

    All exchange implementations must inherit from this class
    and implement the required methods.
    """

    @abstractmethod
    async def connect(self) -> bool:
        """
        Connect to the exchange.

        Returns:
            True if connection successful, False otherwise
        """

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the exchange."""

    @abstractmethod
    async def get_balance(self) -> dict[str, dict[str, float]]:
        """
        Get account balance.

        Returns:
            Balance dict with total, free, and used amounts per currency
        """

    @abstractmethod
    async def get_ticker(self, symbol: str) -> dict[str, Any]:
        """
        Get current ticker for a symbol.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")

        Returns:
            Ticker data with last price, bid, ask, volume, etc.
        """

    @abstractmethod
    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 100,
    ) -> list[list[float]]:
        """
        Get OHLCV (candlestick) data.

        Args:
            symbol: Trading pair
            timeframe: Candle timeframe (1m, 5m, 15m, 1h, 4h, 1d)
            limit: Number of candles to fetch

        Returns:
            List of [timestamp, open, high, low, close, volume]
        """

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: str,
        type: str,
        amount: float,
        price: float | None = None,
    ) -> dict[str, Any]:
        """
        Place an order on the exchange.

        Args:
            symbol: Trading pair
            side: "buy" or "sell"
            type: "market" or "limit"
            amount: Amount to trade
            price: Limit price (required for limit orders)

        Returns:
            Order result
        """

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> dict[str, Any]:
        """
        Cancel an order.

        Args:
            order_id: Order ID to cancel
            symbol: Trading pair

        Returns:
            Cancellation result
        """

    @abstractmethod
    async def get_order_book(self, symbol: str, limit: int = 10) -> dict[str, Any]:
        """
        Get order book for a symbol.

        Args:
            symbol: Trading pair
            limit: Depth of order book

        Returns:
            Order book with bids and asks
        """

    @abstractmethod
    async def get_open_orders(self, symbol: str) -> list[dict[str, Any]]:
        """
        Get open orders for a symbol.

        Args:
            symbol: Trading pair

        Returns:
            List of open orders
        """
