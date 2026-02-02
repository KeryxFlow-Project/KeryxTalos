"""Order management abstraction over paper and live trading."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol

from keryxflow.config import get_settings
from keryxflow.core.events import EventType, get_event_bus, order_event
from keryxflow.core.logging import LogMessages, get_logger
from keryxflow.exchange.client import ExchangeClient, get_exchange_client
from keryxflow.exchange.paper import PaperTradingEngine, get_paper_engine

logger = get_logger(__name__)


class OrderType(str, Enum):
    """Order type."""

    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class OrderStatus(str, Enum):
    """Order status."""

    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Order:
    """Represents a trading order."""

    id: str
    symbol: str
    order_type: OrderType
    side: str  # "buy" or "sell"
    amount: float
    price: float | None = None
    stop_price: float | None = None
    status: OrderStatus = OrderStatus.PENDING
    filled: float = 0.0
    remaining: float = 0.0
    cost: float = 0.0
    average_price: float = 0.0
    created_at: datetime | None = None
    updated_at: datetime | None = None
    is_paper: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "type": self.order_type.value,
            "side": self.side,
            "amount": self.amount,
            "price": self.price,
            "stop_price": self.stop_price,
            "status": self.status.value,
            "filled": self.filled,
            "remaining": self.remaining,
            "cost": self.cost,
            "average_price": self.average_price,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_paper": self.is_paper,
        }


class OrderExecutor(Protocol):
    """Protocol for order execution."""

    async def execute_market_order(
        self, symbol: str, side: str, amount: float, price: float | None = None
    ) -> dict[str, Any]: ...

    def update_price(self, symbol: str, price: float) -> None: ...

    def get_price(self, symbol: str) -> float | None: ...


class OrderManager:
    """
    Unified order management for paper and live trading.

    Abstracts the execution layer and provides a consistent interface
    for placing, tracking, and managing orders.
    """

    def __init__(self):
        """Initialize the order manager."""
        self.settings = get_settings()
        self.event_bus = get_event_bus()
        self._paper_engine: PaperTradingEngine | None = None
        self._exchange_client: ExchangeClient | None = None
        self._pending_orders: dict[str, Order] = {}

    @property
    def is_paper_mode(self) -> bool:
        """Check if running in paper mode."""
        return self.settings.is_paper_mode

    @property
    def executor(self) -> OrderExecutor:
        """Get the appropriate executor based on mode."""
        if self.is_paper_mode:
            if self._paper_engine is None:
                self._paper_engine = get_paper_engine()
            return self._paper_engine
        else:
            if self._exchange_client is None:
                self._exchange_client = get_exchange_client(sandbox=False)
            return self._exchange_client

    async def initialize(self) -> None:
        """Initialize the order manager."""
        if self.is_paper_mode:
            engine = get_paper_engine()
            await engine.initialize()
            logger.info("order_manager_initialized", mode="paper")
        else:
            client = get_exchange_client(sandbox=False)
            await client.connect()
            logger.info("order_manager_initialized", mode="live")

    def update_price(self, symbol: str, price: float) -> None:
        """
        Update price for a symbol.

        Args:
            symbol: Trading pair
            price: Current price
        """
        if self.is_paper_mode and self._paper_engine:
            self._paper_engine.update_price(symbol, price)

    async def place_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
    ) -> Order:
        """
        Place a market order.

        Args:
            symbol: Trading pair
            side: "buy" or "sell"
            amount: Amount to trade

        Returns:
            Order object with execution details
        """
        # Publish order requested event
        await self.event_bus.publish(
            order_event(
                EventType.ORDER_REQUESTED,
                symbol=symbol,
                side=side,
                quantity=amount,
                price=0.0,
            )
        )

        try:
            result = await self.executor.execute_market_order(symbol, side, amount)

            order = Order(
                id=result["id"],
                symbol=symbol,
                order_type=OrderType.MARKET,
                side=side,
                amount=amount,
                price=result.get("price"),
                status=OrderStatus.FILLED,
                filled=result.get("filled", amount),
                remaining=result.get("remaining", 0.0),
                cost=result.get("cost", 0.0),
                average_price=result.get("price", 0.0),
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                is_paper=self.is_paper_mode,
            )

            msg = LogMessages.order_filled(symbol, side, amount, order.average_price)
            logger.info(msg.technical)

            return order

        except Exception as e:
            msg = LogMessages.order_rejected(
                symbol,
                reason="Order failed",
                technical_reason=str(e),
            )
            logger.error(msg.technical)
            raise

    async def place_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
    ) -> Order:
        """
        Place a limit order.

        Args:
            symbol: Trading pair
            side: "buy" or "sell"
            amount: Amount to trade
            price: Limit price

        Returns:
            Order object
        """
        if self.is_paper_mode:
            # For paper trading, execute immediately at limit price
            # (simplified - real limit orders wait for price)
            current_price = self.executor.get_price(symbol)

            if current_price is None:
                raise ValueError(f"No price available for {symbol}")

            # Check if limit would be filled
            can_fill = (
                (side == "buy" and current_price <= price)
                or (side == "sell" and current_price >= price)
            )

            if can_fill:
                return await self.place_market_order(symbol, side, amount)
            else:
                # Create pending order
                order = Order(
                    id=f"limit_{symbol}_{datetime.now(UTC).timestamp()}",
                    symbol=symbol,
                    order_type=OrderType.LIMIT,
                    side=side,
                    amount=amount,
                    price=price,
                    status=OrderStatus.OPEN,
                    remaining=amount,
                    created_at=datetime.now(UTC),
                    is_paper=True,
                )
                self._pending_orders[order.id] = order
                logger.info(
                    "limit_order_placed",
                    order_id=order.id,
                    symbol=symbol,
                    side=side,
                    amount=amount,
                    price=price,
                )
                return order
        else:
            # Live trading
            assert self._exchange_client is not None
            result = await self._exchange_client.create_limit_order(
                symbol, side, amount, price
            )
            return Order(
                id=result["id"],
                symbol=symbol,
                order_type=OrderType.LIMIT,
                side=side,
                amount=amount,
                price=price,
                status=OrderStatus.OPEN,
                remaining=amount,
                created_at=datetime.utcnow(),
                is_paper=False,
            )

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """
        Cancel an order.

        Args:
            order_id: Order ID
            symbol: Trading pair

        Returns:
            True if cancelled successfully
        """
        if order_id in self._pending_orders:
            del self._pending_orders[order_id]
            logger.info("order_cancelled", order_id=order_id)
            return True

        if not self.is_paper_mode and self._exchange_client:
            try:
                await self._exchange_client.cancel_order(order_id, symbol)
                return True
            except Exception as e:
                logger.error("cancel_order_failed", order_id=order_id, error=str(e))
                return False

        return False

    async def check_pending_orders(self) -> list[Order]:
        """
        Check and fill any pending limit orders.

        Returns:
            List of filled orders
        """
        filled = []

        for order_id, order in list(self._pending_orders.items()):
            current_price = self.executor.get_price(order.symbol)
            if current_price is None:
                continue

            should_fill = (
                (order.side == "buy" and current_price <= (order.price or 0))
                or (order.side == "sell" and current_price >= (order.price or 0))
            )

            if should_fill:
                # Execute the order
                try:
                    result = await self.executor.execute_market_order(
                        order.symbol,
                        order.side,
                        order.amount,
                        order.price,
                    )
                    order.status = OrderStatus.FILLED
                    order.filled = order.amount
                    order.remaining = 0.0
                    order.average_price = result.get("price", order.price or 0)
                    order.updated_at = datetime.now(UTC)
                    filled.append(order)
                    del self._pending_orders[order_id]

                    logger.info(
                        "limit_order_filled",
                        order_id=order_id,
                        symbol=order.symbol,
                        price=order.average_price,
                    )
                except Exception as e:
                    logger.error(
                        "limit_order_fill_failed",
                        order_id=order_id,
                        error=str(e),
                    )

        return filled

    def get_pending_orders(self) -> list[Order]:
        """Get all pending orders."""
        return list(self._pending_orders.values())

    async def get_balance(self) -> dict[str, dict[str, float]]:
        """
        Get current balance.

        Returns:
            Balance dict
        """
        if self.is_paper_mode:
            engine = get_paper_engine()
            return await engine.get_balance()
        else:
            client = get_exchange_client()
            return await client.get_balance()

    async def sync_balance_from_exchange(self) -> dict[str, float]:
        """
        Sync balance from exchange (live mode only).

        Returns:
            Dict with free balances per currency
        """
        if self.is_paper_mode:
            balance = await self.get_balance()
            return balance.get("free", {})

        client = get_exchange_client()
        balance = await client.get_balance()
        return balance.get("free", {})

    async def get_open_orders(self, _symbol: str | None = None) -> list[Order]:
        """
        Get open orders from exchange.

        Args:
            symbol: Optional symbol to filter by

        Returns:
            List of open orders
        """
        if self.is_paper_mode:
            return self.get_pending_orders()

        # Live mode - fetch from exchange
        if self._exchange_client is None:
            self._exchange_client = get_exchange_client(sandbox=False)

        try:
            # This would fetch real open orders from exchange
            # For now, return pending orders tracked locally
            return self.get_pending_orders()
        except Exception as e:
            logger.error("fetch_open_orders_failed", error=str(e))
            return []


# Global instance
_order_manager: OrderManager | None = None


def get_order_manager() -> OrderManager:
    """Get the global order manager instance."""
    global _order_manager
    if _order_manager is None:
        _order_manager = OrderManager()
    return _order_manager
