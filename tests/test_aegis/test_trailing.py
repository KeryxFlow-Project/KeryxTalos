"""Tests for trailing stop manager."""

import asyncio

import pytest

from keryxflow.aegis.trailing import TrailingStopManager
from keryxflow.core.events import Event, EventType, get_event_bus


@pytest.fixture
def manager():
    """Create a trailing stop manager for testing."""
    mgr = TrailingStopManager(trailing_stop_pct=2.0, breakeven_trigger_pct=1.0)
    # Bypass __post_init__ config loading by setting values directly
    mgr.trailing_stop_pct = 2.0
    mgr.breakeven_trigger_pct = 1.0
    return mgr


class TestStopMovesUp:
    """Tests that the stop ratchets up with price."""

    def test_initial_stop_below_entry(self, manager):
        """Stop is set below entry price on start."""
        manager.start_tracking("BTC/USDT", entry_price=50000.0)
        stop = manager.get_stop_level("BTC/USDT")
        # 50000 * (1 - 2/100) = 49000
        assert stop == pytest.approx(49000.0)

    def test_stop_moves_up_with_higher_price(self, manager):
        """Stop moves up when price increases."""
        manager.start_tracking("BTC/USDT", entry_price=50000.0)
        manager.update_price("BTC/USDT", 52000.0)
        # 52000 * (1 - 0.02) = 50960
        assert manager.get_stop_level("BTC/USDT") == pytest.approx(50960.0)

    def test_stop_does_not_move_down(self, manager):
        """Stop never moves down when price drops."""
        manager.start_tracking("BTC/USDT", entry_price=50000.0)
        manager.update_price("BTC/USDT", 52000.0)
        stop_after_rise = manager.get_stop_level("BTC/USDT")

        manager.update_price("BTC/USDT", 51000.0)
        assert manager.get_stop_level("BTC/USDT") == stop_after_rise

    def test_stop_ratchets_up_incrementally(self, manager):
        """Stop ratchets up with each new high."""
        manager.start_tracking("BTC/USDT", entry_price=50000.0)

        manager.update_price("BTC/USDT", 51000.0)
        stop1 = manager.get_stop_level("BTC/USDT")

        manager.update_price("BTC/USDT", 53000.0)
        stop2 = manager.get_stop_level("BTC/USDT")

        assert stop2 > stop1

    def test_multiple_symbols_independent(self, manager):
        """Each symbol has independent trailing state."""
        manager.start_tracking("BTC/USDT", entry_price=50000.0)
        manager.start_tracking("ETH/USDT", entry_price=3000.0)

        manager.update_price("BTC/USDT", 55000.0)

        # ETH stop should be unchanged
        assert manager.get_stop_level("ETH/USDT") == pytest.approx(2940.0)
        # BTC stop should have moved
        assert manager.get_stop_level("BTC/USDT") == pytest.approx(53900.0)


class TestStopTrigger:
    """Tests that stop triggers correctly on price drops."""

    def test_trigger_when_price_below_stop(self, manager):
        """Stop triggers when price drops below stop level."""
        manager.start_tracking("BTC/USDT", entry_price=50000.0)
        # Stop at 49000
        assert manager.should_trigger_stop("BTC/USDT", 48000.0) is True

    def test_trigger_when_price_equals_stop(self, manager):
        """Stop triggers when price equals stop level."""
        manager.start_tracking("BTC/USDT", entry_price=50000.0)
        assert manager.should_trigger_stop("BTC/USDT", 49000.0) is True

    def test_no_trigger_when_price_above_stop(self, manager):
        """Stop does not trigger when price is above stop."""
        manager.start_tracking("BTC/USDT", entry_price=50000.0)
        assert manager.should_trigger_stop("BTC/USDT", 50000.0) is False

    def test_no_trigger_for_untracked_symbol(self, manager):
        """Returns False for symbols not being tracked."""
        assert manager.should_trigger_stop("BTC/USDT", 48000.0) is False

    def test_trigger_after_trailing(self, manager):
        """Stop triggers at the trailed level, not initial."""
        manager.start_tracking("BTC/USDT", entry_price=50000.0)
        manager.update_price("BTC/USDT", 55000.0)
        # New stop: 55000 * 0.98 = 53900
        assert manager.should_trigger_stop("BTC/USDT", 53800.0) is True
        assert manager.should_trigger_stop("BTC/USDT", 54000.0) is False


class TestBreakevenActivation:
    """Tests for break-even logic."""

    def test_breakeven_activates_at_threshold(self, manager):
        """Stop moves to entry when profit reaches threshold."""
        manager.start_tracking("BTC/USDT", entry_price=50000.0)
        # Initial stop: 49000
        # Breakeven trigger: 50000 * 1.01 = 50500
        manager.update_price("BTC/USDT", 50500.0)

        # Stop should be at entry (50000) since 50500 * 0.98 = 49490 < 50000
        assert manager.get_stop_level("BTC/USDT") == pytest.approx(50000.0)

    def test_breakeven_does_not_lower_stop(self, manager):
        """Breakeven doesn't lower stop if trailing already above entry."""
        manager.start_tracking("BTC/USDT", entry_price=50000.0)
        # Move price high enough that trailing stop > entry
        manager.update_price("BTC/USDT", 55000.0)
        # Stop: 55000 * 0.98 = 53900, already above entry (50000)
        stop_before = manager.get_stop_level("BTC/USDT")

        # Breakeven already activated since 55000 > 50500
        assert manager._positions["BTC/USDT"].breakeven_activated is True
        assert manager.get_stop_level("BTC/USDT") == stop_before

    def test_breakeven_not_activated_below_threshold(self, manager):
        """Breakeven does not activate below the threshold."""
        manager.start_tracking("BTC/USDT", entry_price=50000.0)
        manager.update_price("BTC/USDT", 50400.0)
        # 50400 < 50500 breakeven trigger
        assert manager._positions["BTC/USDT"].breakeven_activated is False

    def test_breakeven_flag_persists(self, manager):
        """Once breakeven activates, it stays activated."""
        manager.start_tracking("BTC/USDT", entry_price=50000.0)
        manager.update_price("BTC/USDT", 50600.0)
        assert manager._positions["BTC/USDT"].breakeven_activated is True

        # Price drops but breakeven stays
        manager.update_price("BTC/USDT", 50100.0)
        assert manager._positions["BTC/USDT"].breakeven_activated is True


class TestReset:
    """Tests for reset functionality."""

    def test_reset_clears_state(self, manager):
        """Reset removes all state for a symbol."""
        manager.start_tracking("BTC/USDT", entry_price=50000.0)
        manager.reset("BTC/USDT")
        assert manager.get_stop_level("BTC/USDT") is None

    def test_reset_untracked_is_noop(self, manager):
        """Reset on untracked symbol does nothing."""
        manager.reset("BTC/USDT")  # Should not raise

    def test_reset_one_symbol_keeps_others(self, manager):
        """Reset one symbol does not affect others."""
        manager.start_tracking("BTC/USDT", entry_price=50000.0)
        manager.start_tracking("ETH/USDT", entry_price=3000.0)

        manager.reset("BTC/USDT")

        assert manager.get_stop_level("BTC/USDT") is None
        assert manager.get_stop_level("ETH/USDT") is not None

    def test_should_trigger_returns_false_after_reset(self, manager):
        """After reset, should_trigger_stop returns False."""
        manager.start_tracking("BTC/USDT", entry_price=50000.0)
        manager.reset("BTC/USDT")
        assert manager.should_trigger_stop("BTC/USDT", 0.0) is False


class TestEventEmission:
    """Tests for event emission via event bus."""

    @pytest.fixture
    def captured_events(self):
        """Capture emitted events."""
        events: list[Event] = []

        async def handler(event: Event) -> None:
            events.append(event)

        bus = get_event_bus()
        bus.subscribe(EventType.STOP_LOSS_TRAILED, handler)
        bus.subscribe(EventType.STOP_LOSS_BREAKEVEN, handler)
        return events

    async def test_trailed_event_emitted(self, manager, captured_events):
        """STOP_LOSS_TRAILED event emitted when stop moves up."""
        manager.start_tracking("BTC/USDT", entry_price=50000.0)
        manager.update_price("BTC/USDT", 52000.0)

        # Allow async tasks to run
        await asyncio.sleep(0.05)

        trailed = [e for e in captured_events if e.type == EventType.STOP_LOSS_TRAILED]
        assert len(trailed) == 1
        assert trailed[0].data["symbol"] == "BTC/USDT"
        assert trailed[0].data["new_stop"] == pytest.approx(50960.0)

    async def test_breakeven_event_emitted(self, manager, captured_events):
        """STOP_LOSS_BREAKEVEN event emitted when stop moves to entry."""
        manager.start_tracking("BTC/USDT", entry_price=50000.0)
        manager.update_price("BTC/USDT", 50500.0)

        await asyncio.sleep(0.05)

        breakeven = [e for e in captured_events if e.type == EventType.STOP_LOSS_BREAKEVEN]
        assert len(breakeven) == 1
        assert breakeven[0].data["symbol"] == "BTC/USDT"
        assert breakeven[0].data["stop_level"] == pytest.approx(50000.0)
        assert breakeven[0].data["entry_price"] == pytest.approx(50000.0)

    async def test_no_event_when_stop_unchanged(self, manager, captured_events):
        """No event emitted when price drops (stop unchanged)."""
        manager.start_tracking("BTC/USDT", entry_price=50000.0)
        manager.update_price("BTC/USDT", 49500.0)

        await asyncio.sleep(0.05)

        assert len(captured_events) == 0

    async def test_no_duplicate_breakeven_event(self, manager, captured_events):
        """Breakeven event only emitted once."""
        manager.start_tracking("BTC/USDT", entry_price=50000.0)
        manager.update_price("BTC/USDT", 50600.0)
        await asyncio.sleep(0.05)

        manager.update_price("BTC/USDT", 50100.0)
        await asyncio.sleep(0.05)

        breakeven = [e for e in captured_events if e.type == EventType.STOP_LOSS_BREAKEVEN]
        assert len(breakeven) == 1
