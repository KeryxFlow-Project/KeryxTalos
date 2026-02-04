"""Paper trading engine for simulated order execution."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlmodel import select

from keryxflow.config import get_settings
from keryxflow.core.database import get_session, initialize_paper_balance
from keryxflow.core.events import EventType, get_event_bus, order_event
from keryxflow.core.logging import LogMessages, get_logger
from keryxflow.core.models import (
    PaperBalance,
    Position,
    Trade,
    TradeSide,
    TradeStatus,
)

logger = get_logger(__name__)


class PaperTradingEngine:
    """
    Simulates order execution for paper trading.

    Maintains virtual balances and positions, persisting
    state to the database for crash recovery.
    """

    def __init__(self, initial_balance: float = 10000.0, slippage_pct: float = 0.001):
        """
        Initialize the paper trading engine.

        Args:
            initial_balance: Starting balance in base currency (USDT)
            slippage_pct: Simulated slippage percentage (0.001 = 0.1%)
        """
        self.settings = get_settings()
        self.event_bus = get_event_bus()
        self.initial_balance = initial_balance
        self.slippage_pct = slippage_pct
        self._prices: dict[str, float] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize paper trading state from database."""
        if self._initialized:
            return

        async for session in get_session():
            # Initialize base currency balance
            await initialize_paper_balance(
                session,
                currency=self.settings.system.base_currency,
                amount=self.initial_balance,
            )
            self._initialized = True
            logger.info(
                "paper_trading_initialized",
                balance=self.initial_balance,
                currency=self.settings.system.base_currency,
            )

    def update_price(self, symbol: str, price: float) -> None:
        """
        Update the current price for a symbol.

        Args:
            symbol: Trading pair
            price: Current price
        """
        self._prices[symbol] = price

    def get_price(self, symbol: str) -> float | None:
        """
        Get the current price for a symbol.

        Args:
            symbol: Trading pair

        Returns:
            Current price or None if not available
        """
        return self._prices.get(symbol)

    def _apply_slippage(self, price: float, side: str) -> float:
        """
        Apply slippage to a price.

        Args:
            price: Original price
            side: "buy" or "sell"

        Returns:
            Price with slippage applied
        """
        if side == "buy":
            return price * (1 + self.slippage_pct)
        else:
            return price * (1 - self.slippage_pct)

    def _get_base_quote(self, symbol: str) -> tuple[str, str]:
        """
        Extract base and quote currencies from symbol.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")

        Returns:
            Tuple of (base, quote) currencies
        """
        parts = symbol.split("/")
        return parts[0], parts[1]

    async def get_balance(self, currency: str | None = None) -> dict[str, dict[str, float]]:
        """
        Get current paper trading balance.

        Args:
            currency: Specific currency or None for all

        Returns:
            Balance dict with total, free, and used amounts
        """
        await self.initialize()

        async for session in get_session():
            if currency:
                result = await session.execute(
                    select(PaperBalance).where(PaperBalance.currency == currency)
                )
                balance = result.scalar_one_or_none()
                if balance:
                    return {
                        "total": {currency: balance.total},
                        "free": {currency: balance.free},
                        "used": {currency: balance.used},
                    }
                return {
                    "total": {currency: 0.0},
                    "free": {currency: 0.0},
                    "used": {currency: 0.0},
                }

            result = await session.execute(select(PaperBalance))
            balances = result.scalars().all()

            total = {}
            free = {}
            used = {}

            for b in balances:
                total[b.currency] = b.total
                free[b.currency] = b.free
                used[b.currency] = b.used

            return {"total": total, "free": free, "used": used}

    async def _get_or_create_balance(
        self, session: Any, currency: str
    ) -> PaperBalance:
        """Get or create a balance record."""
        result = await session.execute(
            select(PaperBalance).where(PaperBalance.currency == currency)
        )
        balance = result.scalar_one_or_none()

        if balance is None:
            balance = PaperBalance(currency=currency, total=0.0, free=0.0, used=0.0)
            session.add(balance)
            await session.flush()

        return balance

    async def execute_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float | None = None,
    ) -> dict[str, Any]:
        """
        Execute a simulated market order.

        Args:
            symbol: Trading pair
            side: "buy" or "sell"
            amount: Amount of base currency to trade
            price: Override price (uses current price if None)

        Returns:
            Order result dict
        """
        await self.initialize()

        # Get execution price
        if price is None:
            price = self.get_price(symbol)
            if price is None:
                raise ValueError(f"No price available for {symbol}")

        # Apply slippage
        exec_price = self._apply_slippage(price, side)
        base, quote = self._get_base_quote(symbol)
        cost = amount * exec_price

        order_id = str(uuid.uuid4())[:8]

        async for session in get_session():
            if side == "buy":
                # Check quote balance
                quote_balance = await self._get_or_create_balance(session, quote)
                if quote_balance.free < cost:
                    raise ValueError(
                        f"Insufficient {quote} balance: {quote_balance.free:.2f} < {cost:.2f}"
                    )

                # Deduct quote, add base
                quote_balance.free -= cost
                quote_balance.total -= cost

                base_balance = await self._get_or_create_balance(session, base)
                base_balance.free += amount
                base_balance.total += amount

            else:  # sell
                # Check base balance
                base_balance = await self._get_or_create_balance(session, base)
                if base_balance.free < amount:
                    raise ValueError(
                        f"Insufficient {base} balance: {base_balance.free:.6f} < {amount:.6f}"
                    )

                # Deduct base, add quote
                base_balance.free -= amount
                base_balance.total -= amount

                quote_balance = await self._get_or_create_balance(session, quote)
                quote_balance.free += cost
                quote_balance.total += cost

            # Update timestamps
            base_balance.updated_at = datetime.now(UTC)
            quote_balance.updated_at = datetime.now(UTC)

            # Create trade record
            trade = Trade(
                symbol=symbol,
                side=TradeSide(side),
                quantity=amount,
                entry_price=exec_price,
                status=TradeStatus.CLOSED,
                is_paper=True,
                opened_at=datetime.now(UTC),
                closed_at=datetime.now(UTC),
            )
            session.add(trade)

            await session.commit()

        # Create order result
        order_result = {
            "id": order_id,
            "symbol": symbol,
            "type": "market",
            "side": side,
            "amount": amount,
            "price": exec_price,
            "cost": cost,
            "filled": amount,
            "remaining": 0.0,
            "status": "closed",
            "timestamp": datetime.now(UTC).isoformat(),
        }

        # Publish event
        await self.event_bus.publish(
            order_event(
                EventType.ORDER_FILLED,
                symbol=symbol,
                side=side,
                quantity=amount,
                price=exec_price,
                order_id=order_id,
            )
        )

        msg = LogMessages.order_filled(symbol, side, amount, exec_price)
        logger.info(msg.technical)

        return order_result

    async def open_position(
        self,
        symbol: str,
        side: str,
        amount: float,
        entry_price: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> Position:
        """
        Open a new position.

        Args:
            symbol: Trading pair
            side: "buy" or "sell"
            amount: Position size
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price

        Returns:
            Created Position object
        """
        await self.initialize()

        # Execute the entry order
        await self.execute_market_order(symbol, side, amount, entry_price)

        async for session in get_session():
            # Check for existing position
            result = await session.execute(
                select(Position).where(Position.symbol == symbol)
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing position (averaging in)
                total_cost = (existing.entry_price * existing.quantity) + (
                    entry_price * amount
                )
                total_qty = existing.quantity + amount
                existing.entry_price = total_cost / total_qty
                existing.quantity = total_qty
                existing.stop_loss = stop_loss or existing.stop_loss
                existing.take_profit = take_profit or existing.take_profit
                existing.updated_at = datetime.now(UTC)
                position = existing
            else:
                # Get the trade we just created
                result = await session.execute(
                    select(Trade)
                    .where(Trade.symbol == symbol)
                    .order_by(Trade.created_at.desc())
                    .limit(1)
                )
                trade = result.scalar_one()

                # Create new position
                position = Position(
                    symbol=symbol,
                    side=TradeSide(side),
                    quantity=amount,
                    entry_price=entry_price,
                    current_price=entry_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    trade_id=trade.id,
                )
                session.add(position)

            await session.commit()
            await session.refresh(position)

        logger.info(
            "position_opened",
            symbol=symbol,
            side=side,
            quantity=amount,
            entry_price=entry_price,
        )

        return position

    async def close_position(
        self,
        symbol: str,
        price: float | None = None,
    ) -> dict[str, Any] | None:
        """
        Close an existing position.

        Args:
            symbol: Trading pair
            price: Exit price (uses current price if None)

        Returns:
            Position close result or None if no position
        """
        await self.initialize()

        if price is None:
            price = self.get_price(symbol)
            if price is None:
                raise ValueError(f"No price available for {symbol}")

        async for session in get_session():
            result = await session.execute(
                select(Position).where(Position.symbol == symbol)
            )
            position = result.scalar_one_or_none()

            if not position:
                return None

            # Calculate PnL
            if position.side == TradeSide.BUY:
                pnl = (price - position.entry_price) * position.quantity
                close_side = "sell"
            else:
                pnl = (position.entry_price - price) * position.quantity
                close_side = "buy"

            pnl_pct = (pnl / (position.entry_price * position.quantity)) * 100

            # Execute close order
            await self.execute_market_order(
                symbol, close_side, position.quantity, price
            )

            # Update trade record
            result = await session.execute(
                select(Trade).where(Trade.id == position.trade_id)
            )
            trade = result.scalar_one_or_none()
            if trade:
                trade.exit_price = price
                trade.pnl = pnl
                trade.pnl_percentage = pnl_pct
                trade.status = TradeStatus.CLOSED
                trade.closed_at = datetime.now(UTC)

            # Delete position
            await session.delete(position)
            await session.commit()

        result = {
            "symbol": symbol,
            "side": position.side.value,
            "quantity": position.quantity,
            "entry_price": position.entry_price,
            "exit_price": price,
            "pnl": pnl,
            "pnl_percentage": pnl_pct,
        }

        logger.info(
            "position_closed",
            symbol=symbol,
            pnl=f"{pnl:+.2f}",
            pnl_pct=f"{pnl_pct:+.2f}%",
        )

        return result

    async def get_positions(self) -> list[Position]:
        """Get all open positions."""
        await self.initialize()

        async for session in get_session():
            result = await session.execute(select(Position))
            return list(result.scalars().all())
        return []

    async def get_position(self, symbol: str) -> Position | None:
        """Get position for a specific symbol."""
        await self.initialize()

        async for session in get_session():
            result = await session.execute(
                select(Position).where(Position.symbol == symbol)
            )
            return result.scalar_one_or_none()
        return None

    async def update_position_prices(self) -> None:
        """Update all positions with current prices."""
        async for session in get_session():
            result = await session.execute(select(Position))
            positions = result.scalars().all()

            for position in positions:
                price = self.get_price(position.symbol)
                if price:
                    position.current_price = price

                    if position.side == TradeSide.BUY:
                        pnl = (price - position.entry_price) * position.quantity
                    else:
                        pnl = (position.entry_price - price) * position.quantity

                    position.unrealized_pnl = pnl
                    position.unrealized_pnl_percentage = (
                        pnl / (position.entry_price * position.quantity)
                    ) * 100
                    position.updated_at = datetime.now(UTC)

            await session.commit()

    async def close_all_positions(self) -> list[dict[str, Any]]:
        """
        Close all open positions (panic mode).

        Returns:
            List of close results
        """
        results = []
        positions = await self.get_positions()

        for position in positions:
            result = await self.close_position(position.symbol)
            if result:
                results.append(result)

        logger.warning("all_positions_closed", count=len(results))
        return results


# Global instance
_paper_engine: PaperTradingEngine | None = None


def get_paper_engine(
    initial_balance: float = 10000.0,
    slippage_pct: float = 0.001,
) -> PaperTradingEngine:
    """Get the global paper trading engine instance."""
    global _paper_engine
    if _paper_engine is None:
        _paper_engine = PaperTradingEngine(
            initial_balance=initial_balance,
            slippage_pct=slippage_pct,
        )
    return _paper_engine


def set_paper_engine(engine: PaperTradingEngine) -> None:
    """Set the global paper trading engine instance."""
    global _paper_engine
    _paper_engine = engine
