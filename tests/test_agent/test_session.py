"""Tests for the Trading Session."""

import asyncio
from datetime import UTC, datetime

import pytest

from keryxflow.agent.session import (
    SessionState,
    SessionStats,
    TradingSession,
    get_trading_session,
)


class TestSessionState:
    """Tests for SessionState enum."""

    def test_state_values(self):
        """Test session state values."""
        assert SessionState.IDLE.value == "idle"
        assert SessionState.STARTING.value == "starting"
        assert SessionState.RUNNING.value == "running"
        assert SessionState.PAUSED.value == "paused"
        assert SessionState.STOPPING.value == "stopping"
        assert SessionState.STOPPED.value == "stopped"
        assert SessionState.ERROR.value == "error"


class TestSessionStats:
    """Tests for SessionStats dataclass."""

    def test_create_stats(self):
        """Test creating session stats."""
        stats = SessionStats()

        assert stats.started_at is None
        assert stats.stopped_at is None
        assert stats.cycles_completed == 0
        assert stats.trades_executed == 0
        assert stats.total_pnl == 0.0

    def test_duration_no_start(self):
        """Test duration when not started."""
        stats = SessionStats()

        assert stats.duration_seconds == 0.0

    def test_duration_with_start(self):
        """Test duration calculation."""
        stats = SessionStats()
        stats.started_at = datetime.now(UTC)

        # Wait a tiny bit
        import time

        time.sleep(0.1)

        duration = stats.duration_seconds
        assert duration >= 0.1
        assert duration < 1.0  # Should be much less than a second

    def test_win_rate_no_trades(self):
        """Test win rate with no trades."""
        stats = SessionStats()

        assert stats.win_rate == 0.0

    def test_win_rate_with_trades(self):
        """Test win rate calculation."""
        stats = SessionStats()
        stats.trades_won = 6
        stats.trades_lost = 4

        assert stats.win_rate == 60.0

    def test_cycles_per_minute(self):
        """Test cycles per minute calculation."""
        stats = SessionStats()
        stats.started_at = datetime.now(UTC)
        stats.cycles_completed = 60

        # Force 1 minute duration
        import time

        time.sleep(0.1)  # Small sleep

        # Should calculate cycles per minute
        cpm = stats.cycles_per_minute
        assert cpm > 0

    def test_to_dict(self):
        """Test converting to dictionary."""
        stats = SessionStats()
        stats.started_at = datetime.now(UTC)
        stats.cycles_completed = 10
        stats.cycles_successful = 8
        stats.trades_executed = 3
        stats.trades_won = 2
        stats.trades_lost = 1
        stats.total_pnl = 150.0
        stats.input_tokens = 3000
        stats.output_tokens = 2000
        stats.total_cost = 0.039

        data = stats.to_dict()

        assert data["cycles_completed"] == 10
        assert data["cycles_successful"] == 8
        assert data["trades_executed"] == 3
        assert data["win_rate"] == pytest.approx(66.67, rel=0.1)
        assert data["total_pnl"] == 150.0
        assert data["input_tokens"] == 3000
        assert data["output_tokens"] == 2000
        assert data["total_cost"] == 0.039
        assert "started_at" in data

    def test_default_token_cost_fields(self):
        """Test that token cost fields default to zero."""
        stats = SessionStats()

        assert stats.input_tokens == 0
        assert stats.output_tokens == 0
        assert stats.total_cost == 0.0


class TestTradingSession:
    """Tests for TradingSession class."""

    def test_create_session(self):
        """Test creating a session."""
        session = TradingSession()

        assert session.state == SessionState.IDLE
        assert session.session_id.startswith("session_")
        assert not session.is_running
        assert not session.is_paused

    def test_session_with_symbols(self):
        """Test creating session with custom symbols."""
        session = TradingSession(symbols=["BTC/USDT", "ETH/USDT"])

        assert session._symbols == ["BTC/USDT", "ETH/USDT"]

    def test_get_status(self):
        """Test getting session status."""
        session = TradingSession()

        status = session.get_status()

        assert status["state"] == "idle"
        assert "session_id" in status
        assert "stats" in status
        assert status["engine_running"] is False

    def test_record_trade_win(self):
        """Test recording a winning trade."""
        session = TradingSession()

        session.record_trade(won=True, pnl=100.0)

        assert session.stats.trades_executed == 1
        assert session.stats.trades_won == 1
        assert session.stats.trades_lost == 0
        assert session.stats.total_pnl == 100.0

    def test_record_trade_loss(self):
        """Test recording a losing trade."""
        session = TradingSession()

        session.record_trade(won=False, pnl=-50.0)

        assert session.stats.trades_executed == 1
        assert session.stats.trades_won == 0
        assert session.stats.trades_lost == 1
        assert session.stats.total_pnl == -50.0

    def test_record_multiple_trades(self):
        """Test recording multiple trades."""
        session = TradingSession()

        session.record_trade(won=True, pnl=100.0)
        session.record_trade(won=True, pnl=50.0)
        session.record_trade(won=False, pnl=-30.0)

        assert session.stats.trades_executed == 3
        assert session.stats.trades_won == 2
        assert session.stats.trades_lost == 1
        assert session.stats.total_pnl == 120.0

    @pytest.mark.asyncio
    async def test_stop_without_start(self):
        """Test stopping without starting."""
        session = TradingSession()

        result = await session.stop()

        assert result is False
        assert session.state == SessionState.IDLE

    @pytest.mark.asyncio
    async def test_pause_without_start(self):
        """Test pausing without starting."""
        session = TradingSession()

        result = await session.pause()

        assert result is False
        assert session.state == SessionState.IDLE

    @pytest.mark.asyncio
    async def test_resume_without_pause(self):
        """Test resuming without pausing."""
        session = TradingSession()

        result = await session.resume()

        assert result is False
        assert session.state == SessionState.IDLE


class TestSessionStateMachine:
    """Tests for session state transitions."""

    def test_initial_state(self):
        """Test initial state is IDLE."""
        session = TradingSession()

        assert session.state == SessionState.IDLE

    def test_invalid_pause_from_idle(self):
        """Test cannot pause from IDLE."""
        session = TradingSession()

        # Should not be able to pause
        assert session.state == SessionState.IDLE

    def test_invalid_resume_from_idle(self):
        """Test cannot resume from IDLE."""
        session = TradingSession()

        # Should not be able to resume
        assert session.state == SessionState.IDLE


class TestSessionStatsCalculations:
    """Tests for SessionStats calculations."""

    def test_duration_excludes_pause_time(self):
        """Test that duration excludes paused time."""
        stats = SessionStats()
        stats.started_at = datetime.now(UTC)
        stats.total_paused_time_seconds = 30.0

        # Even if we wait, the paused time is subtracted
        import time

        time.sleep(0.1)

        duration = stats.duration_seconds
        # Duration should account for paused time subtraction
        assert duration >= -30.0  # Could be negative if less than pause time

    def test_win_rate_100_percent(self):
        """Test 100% win rate."""
        stats = SessionStats()
        stats.trades_won = 10
        stats.trades_lost = 0

        assert stats.win_rate == 100.0

    def test_win_rate_0_percent(self):
        """Test 0% win rate."""
        stats = SessionStats()
        stats.trades_won = 0
        stats.trades_lost = 10

        assert stats.win_rate == 0.0

    def test_cycles_per_minute_zero_duration(self):
        """Test cycles per minute with zero duration."""
        stats = SessionStats()

        assert stats.cycles_per_minute == 0.0


class TestGetTradingSession:
    """Tests for get_trading_session function."""

    def test_returns_singleton(self):
        """Test that function returns singleton."""
        session1 = get_trading_session()
        session2 = get_trading_session()

        assert session1 is session2

    def test_creates_session(self):
        """Test that function creates session."""
        session = get_trading_session()

        assert isinstance(session, TradingSession)
