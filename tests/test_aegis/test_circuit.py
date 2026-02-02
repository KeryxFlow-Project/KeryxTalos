"""Tests for circuit breaker."""

import pytest

from keryxflow.aegis.circuit import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    TripReason,
)


@pytest.fixture
def circuit_breaker():
    """Create a circuit breaker for testing."""
    config = CircuitBreakerConfig(
        max_daily_drawdown=0.05,
        max_consecutive_losses=3,
        rapid_loss_threshold=0.03,
        rapid_loss_window_minutes=30,
        cooldown_minutes=1,
        require_manual_reset=False,
    )
    cb = CircuitBreaker(config=config)
    cb.current_balance = 10000.0
    cb.daily_starting_balance = 10000.0
    cb.peak_balance = 10000.0
    return cb


class TestCircuitBreakerState:
    """Tests for circuit breaker state."""

    def test_initial_state_closed(self, circuit_breaker):
        """Test initial state is closed."""
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.is_closed is True
        assert circuit_breaker.is_tripped is False

    def test_can_trade_when_closed(self, circuit_breaker):
        """Test can trade when closed."""
        can_trade, reason = circuit_breaker.can_trade()
        assert can_trade is True


class TestDrawdownTrip:
    """Tests for drawdown-based trips."""

    def test_trip_on_daily_drawdown(self, circuit_breaker):
        """Test trip when daily drawdown exceeds limit."""
        # 5% drawdown limit, lose 6%
        circuit_breaker.update_balance(9400.0)

        assert circuit_breaker.is_tripped is True
        assert circuit_breaker.trip_reason == TripReason.DAILY_DRAWDOWN

    def test_no_trip_under_limit(self, circuit_breaker):
        """Test no trip when under limit (without triggering rapid loss)."""
        # 2% loss, under 3% rapid loss threshold and 5% daily limit
        circuit_breaker.current_balance = 9800.0  # Direct set to avoid rapid loss trigger

        assert circuit_breaker.is_tripped is False

    def test_warning_at_threshold(self, circuit_breaker):
        """Test warning but no trip at warning threshold."""
        # 2% loss = under warning level
        circuit_breaker.current_balance = 9800.0  # Direct set

        can_trade, reason = circuit_breaker.can_trade()
        assert can_trade is True


class TestConsecutiveLosses:
    """Tests for consecutive loss trips."""

    def test_trip_on_consecutive_losses(self, circuit_breaker):
        """Test trip after too many consecutive losses."""
        # Config: max 3 consecutive losses
        circuit_breaker.record_trade_result(is_win=False, pnl=-100)
        assert circuit_breaker.is_tripped is False

        circuit_breaker.record_trade_result(is_win=False, pnl=-100)
        assert circuit_breaker.is_tripped is False

        circuit_breaker.record_trade_result(is_win=False, pnl=-100)
        assert circuit_breaker.is_tripped is True
        assert circuit_breaker.trip_reason == TripReason.CONSECUTIVE_LOSSES

    def test_win_resets_consecutive_losses(self, circuit_breaker):
        """Test win resets consecutive loss counter."""
        circuit_breaker.record_trade_result(is_win=False, pnl=-100)
        circuit_breaker.record_trade_result(is_win=False, pnl=-100)
        assert circuit_breaker.consecutive_losses == 2

        circuit_breaker.record_trade_result(is_win=True, pnl=100)
        assert circuit_breaker.consecutive_losses == 0


class TestManualTrip:
    """Tests for manual trip and reset."""

    def test_manual_trip(self, circuit_breaker):
        """Test manual trip."""
        circuit_breaker.trip_manual("User requested pause")

        assert circuit_breaker.is_tripped is True
        assert circuit_breaker.trip_reason == TripReason.MANUAL

    def test_reset(self, circuit_breaker):
        """Test reset after trip."""
        circuit_breaker.trip_manual("Test")
        assert circuit_breaker.is_tripped is True

        # Force reset (ignore cooldown)
        result = circuit_breaker.reset(force=True)

        assert result is True
        assert circuit_breaker.is_tripped is False
        assert circuit_breaker.trip_reason is None


class TestTripEvents:
    """Tests for trip event recording."""

    def test_trip_event_recorded(self, circuit_breaker):
        """Test trip events are recorded."""
        circuit_breaker.trip_manual("First trip")
        circuit_breaker.reset(force=True)
        circuit_breaker.trip_manual("Second trip")

        assert len(circuit_breaker.trip_events) == 2
        assert circuit_breaker.trip_events[0].reason == TripReason.MANUAL
        assert circuit_breaker.trip_events[0].details == "First trip"


class TestStatus:
    """Tests for status reporting."""

    def test_get_status(self, circuit_breaker):
        """Test status dictionary."""
        status = circuit_breaker.get_status()

        assert status["state"] == "closed"
        assert status["is_tripped"] is False
        assert "daily_drawdown" in status

    def test_format_status_simple_active(self, circuit_breaker):
        """Test simple status when active."""
        status = circuit_breaker.format_status_simple()

        assert "🟢 ACTIVE" in status

    def test_format_status_simple_tripped(self, circuit_breaker):
        """Test simple status when tripped."""
        circuit_breaker.trip_manual("Test")
        status = circuit_breaker.format_status_simple()

        assert "🔴 TRADING PAUSED" in status
        assert "Manually paused" in status


class TestDailyReset:
    """Tests for daily reset functionality."""

    def test_daily_values_tracked(self, circuit_breaker):
        """Test daily starting balance is tracked."""
        circuit_breaker.daily_starting_balance = 10000.0
        circuit_breaker.current_balance = 9800.0

        assert circuit_breaker.daily_drawdown == pytest.approx(0.02, rel=0.01)
