"""Abstract base class for exchange adapters."""

from abc import ABC, abstractmethod
from typing import Any


class ExchangeAdapter(ABC):
    """
    Abstract base class for exchange adapters.

    Defines the contract all exchange adapters must implement for
    connectivity, market data, and order execution.
    """

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected to exchange."""
        ...

    @abstractmethod
    async def connect(self) -> bool:
        """
        Connect to the exchange.

        Returns:
            True if connection successful, False otherwise
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the exchange."""
        ...

    @abstractmethod
    async def get_ticker(self, symbol: str) -> dict[str, Any]:
        """
        Get current ticker for a symbol.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")

        Returns:
            Ticker data with last price, bid, ask, volume, etc.
        """
        ...

    @abstractmethod
    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 100,
        since: int | None = None,
    ) -> list[list[float]]:
        """
        Get OHLCV (candlestick) data.

        Args:
            symbol: Trading pair
            timeframe: Candle timeframe (1m, 5m, 15m, 1h, 4h, 1d)
            limit: Number of candles to fetch
            since: Timestamp in milliseconds for start time (optional)

        Returns:
            List of [timestamp, open, high, low, close, volume]
        """
        ...

    @abstractmethod
    async def get_balance(self) -> dict[str, dict[str, float]]:
        """
        Get account balance.

        Returns:
            Balance dict with total, free, and used amounts per currency
        """
        ...

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
        ...

    @abstractmethod
    async def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
    ) -> dict[str, Any]:
        """
        Create a market order.

        Args:
            symbol: Trading pair
            side: "buy" or "sell"
            amount: Amount to trade

        Returns:
            Order result
        """
        ...

    @abstractmethod
    async def create_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
    ) -> dict[str, Any]:
        """
        Create a limit order.

        Args:
            symbol: Trading pair
            side: "buy" or "sell"
            amount: Amount to trade
            price: Limit price

        Returns:
            Order result
        """
        ...

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
        ...

    @abstractmethod
    async def get_order(self, order_id: str, symbol: str) -> dict[str, Any]:
        """
        Get order status.

        Args:
            order_id: Order ID
            symbol: Trading pair

        Returns:
            Order details
        """
        ...

    @abstractmethod
    async def get_open_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        """
        Get open orders.

        Args:
            symbol: Optional symbol to filter by

        Returns:
            List of open orders
        """
        ...

    @abstractmethod
    async def start_price_feed(
        self,
        symbols: list[str] | None = None,
        interval: float = 1.0,
    ) -> None:
        """
        Start streaming price updates.

        Args:
            symbols: List of symbols to watch (default from settings)
            interval: Update interval in seconds
        """
        ...

    @abstractmethod
    async def stop_price_feed(self) -> None:
        """Stop the price feed."""
        ...

    def _ensure_connected(self) -> None:
        """Raise error if not connected."""
        if not self.is_connected:
            raise RuntimeError("Not connected to exchange. Call connect() first.")

    # OrderExecutor protocol implementation - concrete methods
    async def execute_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float | None = None,  # noqa: ARG002
    ) -> dict[str, Any]:
        """
        Execute a market order (OrderExecutor protocol).

        Args:
            symbol: Trading pair
            side: "buy" or "sell"
            amount: Amount to trade
            price: Ignored for market orders

        Returns:
            Order result
        """
        return await self.create_market_order(symbol, side, amount)

    def update_price(self, symbol: str, price: float) -> None:  # noqa: B027
        """
        Update price for a symbol (OrderExecutor protocol).

        Note: This is a no-op for live exchange adapters since
        prices come from the exchange itself.

        Args:
            symbol: Trading pair
            price: Current price
        """
        # No-op for live exchanges - prices come from exchange
        _ = symbol, price  # Explicitly acknowledge unused args

    def get_price(self, symbol: str) -> float | None:
        """
        Get cached price for a symbol (OrderExecutor protocol).

        Note: For live exchanges, use get_ticker() instead.
        This method exists for OrderExecutor protocol compatibility.

        Args:
            symbol: Trading pair

        Returns:
            None - use get_ticker() for live prices
        """
        # For live exchanges, prices should be fetched via get_ticker()
        _ = symbol  # Explicitly acknowledge unused arg
        return None
