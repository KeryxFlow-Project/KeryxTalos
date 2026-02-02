"""Tests for trade repository."""

from datetime import UTC, datetime, timedelta

import pytest

from keryxflow.core.models import TradeSide, TradeStatus
from keryxflow.core.repository import TradeRepository


class TestTradeRepository:
    """Tests for TradeRepository class."""

    @pytest.fixture
    async def repo(self, db_session):
        """Create repository with test session."""
        return TradeRepository(session=db_session)

    @pytest.mark.asyncio
    async def test_create_trade(self, repo):
        """Test creating a trade."""
        trade = await repo.create_trade(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.1,
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
            is_paper=True,
        )

        assert trade.id is not None
        assert trade.symbol == "BTC/USDT"
        assert trade.side == TradeSide.BUY
        assert trade.quantity == 0.1
        assert trade.entry_price == 50000.0
        assert trade.status == TradeStatus.OPEN
        assert trade.is_paper is True

    @pytest.mark.asyncio
    async def test_create_live_trade(self, repo):
        """Test creating a live trade."""
        trade = await repo.create_trade(
            symbol="ETH/USDT",
            side="sell",
            quantity=1.0,
            entry_price=3000.0,
            is_paper=False,
        )

        assert trade.is_paper is False
        assert trade.side == TradeSide.SELL

    @pytest.mark.asyncio
    async def test_close_trade(self, repo):
        """Test closing a trade."""
        # Create trade
        trade = await repo.create_trade(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.1,
            entry_price=50000.0,
            is_paper=True,
        )

        # Close trade
        closed = await repo.close_trade(
            trade_id=trade.id,
            exit_price=51000.0,
            pnl=100.0,
            pnl_percentage=2.0,
        )

        assert closed is not None
        assert closed.status == TradeStatus.CLOSED
        assert closed.exit_price == 51000.0
        assert closed.pnl == 100.0
        assert closed.closed_at is not None

    @pytest.mark.asyncio
    async def test_close_nonexistent_trade(self, repo):
        """Test closing a nonexistent trade."""
        result = await repo.close_trade(
            trade_id=99999,
            exit_price=51000.0,
            pnl=100.0,
            pnl_percentage=2.0,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_trade(self, repo):
        """Test getting a trade by ID."""
        trade = await repo.create_trade(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.1,
            entry_price=50000.0,
            is_paper=True,
        )

        fetched = await repo.get_trade(trade.id)

        assert fetched is not None
        assert fetched.id == trade.id

    @pytest.mark.asyncio
    async def test_get_nonexistent_trade(self, repo):
        """Test getting a nonexistent trade."""
        result = await repo.get_trade(99999)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_open_trades(self, repo):
        """Test getting open trades."""
        # Create trades
        await repo.create_trade(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.1,
            entry_price=50000.0,
            is_paper=True,
        )
        await repo.create_trade(
            symbol="ETH/USDT",
            side="buy",
            quantity=1.0,
            entry_price=3000.0,
            is_paper=True,
        )

        open_trades = await repo.get_open_trades()

        assert len(open_trades) >= 2

    @pytest.mark.asyncio
    async def test_get_open_trades_by_symbol(self, repo):
        """Test getting open trades filtered by symbol."""
        await repo.create_trade(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.1,
            entry_price=50000.0,
            is_paper=True,
        )
        await repo.create_trade(
            symbol="ETH/USDT",
            side="buy",
            quantity=1.0,
            entry_price=3000.0,
            is_paper=True,
        )

        btc_trades = await repo.get_open_trades(symbol="BTC/USDT")

        assert all(t.symbol == "BTC/USDT" for t in btc_trades)

    @pytest.mark.asyncio
    async def test_count_paper_trades(self, repo):
        """Test counting paper trades."""
        # Create paper trade
        await repo.create_trade(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.1,
            entry_price=50000.0,
            is_paper=True,
        )

        count = await repo.count_paper_trades()

        assert count >= 1

    @pytest.mark.asyncio
    async def test_get_trades_by_date(self, repo):
        """Test getting trades by date range."""
        # Create trade
        await repo.create_trade(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.1,
            entry_price=50000.0,
            is_paper=True,
        )

        start = datetime.now(UTC) - timedelta(hours=1)
        trades = await repo.get_trades_by_date(start_date=start)

        assert len(trades) >= 1


class TestDailyStats:
    """Tests for daily stats methods."""

    @pytest.fixture
    async def repo(self, db_session):
        """Create repository with test session."""
        return TradeRepository(session=db_session)

    @pytest.mark.asyncio
    async def test_update_daily_stats_create(self, repo):
        """Test creating daily stats."""
        stats = await repo.update_daily_stats(
            date="2026-02-01",
            starting_balance=10000.0,
            ending_balance=10500.0,
            pnl=500.0,
            total_trades=5,
            winning_trades=3,
            losing_trades=2,
        )

        assert stats.date == "2026-02-01"
        assert stats.pnl == 500.0
        assert stats.total_trades == 5

    @pytest.mark.asyncio
    async def test_update_daily_stats_update(self, repo):
        """Test updating existing daily stats."""
        # Create initial
        await repo.update_daily_stats(
            date="2026-02-02",
            starting_balance=10000.0,
            ending_balance=10200.0,
            pnl=200.0,
            total_trades=2,
            winning_trades=2,
            losing_trades=0,
        )

        # Update
        stats = await repo.update_daily_stats(
            date="2026-02-02",
            starting_balance=10000.0,
            ending_balance=10500.0,
            pnl=500.0,
            total_trades=5,
            winning_trades=4,
            losing_trades=1,
        )

        assert stats.pnl == 500.0
        assert stats.total_trades == 5

    @pytest.mark.asyncio
    async def test_get_daily_stats(self, repo):
        """Test getting daily stats."""
        await repo.update_daily_stats(
            date="2026-02-03",
            starting_balance=10000.0,
            ending_balance=10100.0,
            pnl=100.0,
            total_trades=1,
            winning_trades=1,
            losing_trades=0,
        )

        stats = await repo.get_daily_stats("2026-02-03")

        assert stats is not None
        assert stats.pnl == 100.0

    @pytest.mark.asyncio
    async def test_get_nonexistent_daily_stats(self, repo):
        """Test getting nonexistent daily stats."""
        stats = await repo.get_daily_stats("1999-01-01")
        assert stats is None
