"""Repository for trade persistence."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlmodel import col, select

from keryxflow.core.database import get_session_factory
from keryxflow.core.logging import get_logger
from keryxflow.core.models import DailyStats, Trade, TradeStatus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class TradeRepository:
    """Repository for trade CRUD operations."""

    def __init__(self, session: "AsyncSession | None" = None):
        """Initialize repository.

        Args:
            session: Optional async session. If not provided, creates new session per operation.
        """
        self._injected_session = session

    @asynccontextmanager
    async def _get_session(self) -> AsyncGenerator["AsyncSession", None]:
        """Get database session as async context manager."""
        if self._injected_session:
            yield self._injected_session
        else:
            async_session = get_session_factory()
            async with async_session() as session:
                yield session

    async def create_trade(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        is_paper: bool = True,
        notes: str | None = None,
    ) -> Trade:
        """Create a new trade record.

        Args:
            symbol: Trading pair
            side: Trade side (buy/sell)
            quantity: Trade quantity
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            is_paper: Whether this is a paper trade
            notes: Optional notes

        Returns:
            Created trade
        """
        from keryxflow.core.models import TradeSide

        trade = Trade(
            symbol=symbol,
            side=TradeSide.BUY if side == "buy" else TradeSide.SELL,
            quantity=quantity,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            status=TradeStatus.OPEN,
            is_paper=is_paper,
            notes=notes,
            opened_at=datetime.now(UTC),
        )

        async with self._get_session() as session:
            session.add(trade)
            await session.commit()
            await session.refresh(trade)

        logger.info(
            "trade_created",
            trade_id=trade.id,
            symbol=symbol,
            is_paper=is_paper,
        )

        return trade

    async def close_trade(
        self,
        trade_id: int,
        exit_price: float,
        pnl: float,
        pnl_percentage: float,
    ) -> Trade | None:
        """Close a trade.

        Args:
            trade_id: Trade ID
            exit_price: Exit price
            pnl: Realized PnL
            pnl_percentage: PnL percentage

        Returns:
            Updated trade or None if not found
        """
        async with self._get_session() as session:
            statement = select(Trade).where(Trade.id == trade_id)
            result = await session.execute(statement)
            trade = result.scalar_one_or_none()

            if not trade:
                return None

            trade.exit_price = exit_price
            trade.pnl = pnl
            trade.pnl_percentage = pnl_percentage
            trade.status = TradeStatus.CLOSED
            trade.closed_at = datetime.now(UTC)

            await session.commit()
            await session.refresh(trade)

        logger.info(
            "trade_closed",
            trade_id=trade_id,
            pnl=pnl,
        )

        return trade

    async def get_trade(self, trade_id: int) -> Trade | None:
        """Get a trade by ID.

        Args:
            trade_id: Trade ID

        Returns:
            Trade or None if not found
        """
        async with self._get_session() as session:
            statement = select(Trade).where(Trade.id == trade_id)
            result = await session.execute(statement)
            return result.scalar_one_or_none()

    async def get_open_trades(self, symbol: str | None = None) -> list[Trade]:
        """Get all open trades.

        Args:
            symbol: Optional symbol filter

        Returns:
            List of open trades
        """
        async with self._get_session() as session:
            statement = select(Trade).where(Trade.status == TradeStatus.OPEN)

            if symbol:
                statement = statement.where(Trade.symbol == symbol)

            result = await session.execute(statement)
            return list(result.scalars().all())

    async def get_trades_by_date(
        self,
        start_date: datetime,
        end_date: datetime | None = None,
        is_paper: bool | None = None,
    ) -> list[Trade]:
        """Get trades within a date range.

        Args:
            start_date: Start date
            end_date: End date (defaults to now)
            is_paper: Filter by paper/live

        Returns:
            List of trades
        """
        async with self._get_session() as session:
            if end_date is None:
                end_date = datetime.now(UTC)

            statement = select(Trade).where(
                Trade.created_at >= start_date,
                Trade.created_at <= end_date,
            )

            if is_paper is not None:
                statement = statement.where(Trade.is_paper == is_paper)

            statement = statement.order_by(col(Trade.created_at).desc())

            result = await session.execute(statement)
            return list(result.scalars().all())

    async def get_recent_trades(self, limit: int = 50) -> list[Trade]:
        """Get the most recent trades.

        Args:
            limit: Maximum number of trades to return

        Returns:
            List of trades ordered by created_at descending
        """
        async with self._get_session() as session:
            statement = select(Trade).order_by(col(Trade.created_at).desc()).limit(limit)
            result = await session.execute(statement)
            return list(result.scalars().all())

    async def count_paper_trades(self) -> int:
        """Count total paper trades.

        Returns:
            Number of paper trades
        """
        async with self._get_session() as session:
            statement = select(Trade).where(Trade.is_paper == True)  # noqa: E712
            result = await session.execute(statement)
            return len(list(result.scalars().all()))

    async def get_daily_stats(self, date: str) -> DailyStats | None:
        """Get daily stats for a date.

        Args:
            date: Date in YYYY-MM-DD format

        Returns:
            DailyStats or None
        """
        async with self._get_session() as session:
            statement = select(DailyStats).where(DailyStats.date == date)
            result = await session.execute(statement)
            return result.scalar_one_or_none()

    async def update_daily_stats(
        self,
        date: str,
        starting_balance: float,
        ending_balance: float,
        pnl: float,
        total_trades: int,
        winning_trades: int,
        losing_trades: int,
        max_drawdown: float = 0.0,
    ) -> DailyStats:
        """Update or create daily stats.

        Args:
            date: Date in YYYY-MM-DD format
            starting_balance: Starting balance
            ending_balance: Ending balance
            pnl: Day's PnL
            total_trades: Total trades
            winning_trades: Winning trades
            losing_trades: Losing trades
            max_drawdown: Maximum drawdown

        Returns:
            Updated or created DailyStats
        """
        async with self._get_session() as session:
            # Check for existing
            statement = select(DailyStats).where(DailyStats.date == date)
            result = await session.execute(statement)
            existing = result.scalar_one_or_none()

            if existing:
                existing.ending_balance = ending_balance
                existing.pnl = pnl
                existing.pnl_percentage = (
                    (pnl / starting_balance) * 100 if starting_balance > 0 else 0
                )
                existing.total_trades = total_trades
                existing.winning_trades = winning_trades
                existing.losing_trades = losing_trades
                existing.max_drawdown = max_drawdown
                existing.updated_at = datetime.now(UTC)
                await session.commit()
                await session.refresh(existing)
                return existing
            else:
                stats = DailyStats(
                    date=date,
                    starting_balance=starting_balance,
                    ending_balance=ending_balance,
                    pnl=pnl,
                    pnl_percentage=((pnl / starting_balance) * 100 if starting_balance > 0 else 0),
                    total_trades=total_trades,
                    winning_trades=winning_trades,
                    losing_trades=losing_trades,
                    max_drawdown=max_drawdown,
                )
                session.add(stats)
                await session.commit()
                await session.refresh(stats)
                return stats


# Global instance
_repository: TradeRepository | None = None


def get_trade_repository() -> TradeRepository:
    """Get global trade repository instance."""
    global _repository
    if _repository is None:
        _repository = TradeRepository()
    return _repository
