"""Tests for trailing stop manager — 100% coverage required per safety rules."""

import pytest

from keryxflow.aegis.trailing import TrailingStopManager, get_trailing_stop_manager


@pytest.fixture
def manager() -> TrailingStopManager:
    """Create a fresh trailing stop manager for each test."""
    return TrailingStopManager()


class TestStartStopTracking:
    """Tests for start/stop tracking lifecycle."""

    def test_start_tracking_long(self, manager: TrailingStopManager) -> None:
        manager.start_tracking("BTC/USDT", "buy", 50000.0, trail_pct=0.02, activation_pct=0.01)
        assert manager.is_tracking("BTC/USDT")
        state = manager.get_all_states()["BTC/USDT"]
        assert state.side == "buy"
        assert state.entry_price == 50000.0
        assert state.peak_price == 50000.0
        assert state.activated is False
        assert state.current_stop is None

    def test_start_tracking_short(self, manager: TrailingStopManager) -> None:
        manager.start_tracking("ETH/USDT", "sell", 3000.0, trail_pct=0.03, activation_pct=0.01)
        assert manager.is_tracking("ETH/USDT")
        state = manager.get_all_states()["ETH/USDT"]
        assert state.side == "sell"
        assert state.entry_price == 3000.0
        assert state.peak_price == 3000.0

    def test_stop_tracking(self, manager: TrailingStopManager) -> None:
        manager.start_tracking("BTC/USDT", "buy", 50000.0)
        manager.stop_tracking("BTC/USDT")
        assert not manager.is_tracking("BTC/USDT")

    def test_stop_tracking_nonexistent(self, manager: TrailingStopManager) -> None:
        """Stopping tracking for a symbol not tracked should not raise."""
        manager.stop_tracking("NONEXISTENT")

    def test_stop_tracking_all(self, manager: TrailingStopManager) -> None:
        manager.start_tracking("BTC/USDT", "buy", 50000.0)
        manager.start_tracking("ETH/USDT", "sell", 3000.0)
        assert len(manager.get_all_states()) == 2
        manager.stop_tracking_all()
        assert len(manager.get_all_states()) == 0

    def test_is_tracking_false_by_default(self, manager: TrailingStopManager) -> None:
        assert not manager.is_tracking("BTC/USDT")


class TestUpdatePriceLong:
    """Tests for update_price on long positions."""

    def test_no_activation_below_threshold(self, manager: TrailingStopManager) -> None:
        manager.start_tracking("BTC/USDT", "buy", 50000.0, trail_pct=0.02, activation_pct=0.01)
        # Price rises 0.5% — below 1% activation threshold
        manager.update_price("BTC/USDT", 50250.0)
        state = manager.get_all_states()["BTC/USDT"]
        assert not state.activated
        assert state.current_stop is None

    def test_activation_at_threshold(self, manager: TrailingStopManager) -> None:
        manager.start_tracking("BTC/USDT", "buy", 50000.0, trail_pct=0.02, activation_pct=0.01)
        # Price rises exactly 1%
        manager.update_price("BTC/USDT", 50500.0)
        state = manager.get_all_states()["BTC/USDT"]
        assert state.activated
        assert state.peak_price == 50500.0
        assert state.current_stop == pytest.approx(50500.0 * 0.98)

    def test_peak_updates_on_higher_price(self, manager: TrailingStopManager) -> None:
        manager.start_tracking("BTC/USDT", "buy", 50000.0, trail_pct=0.02, activation_pct=0.01)
        manager.update_price("BTC/USDT", 51000.0)  # Activate
        manager.update_price("BTC/USDT", 52000.0)  # Higher peak
        state = manager.get_all_states()["BTC/USDT"]
        assert state.peak_price == 52000.0
        assert state.current_stop == pytest.approx(52000.0 * 0.98)

    def test_peak_does_not_update_on_lower_price(self, manager: TrailingStopManager) -> None:
        manager.start_tracking("BTC/USDT", "buy", 50000.0, trail_pct=0.02, activation_pct=0.01)
        manager.update_price("BTC/USDT", 52000.0)  # Activate + peak
        manager.update_price("BTC/USDT", 51000.0)  # Lower — peak stays
        state = manager.get_all_states()["BTC/USDT"]
        assert state.peak_price == 52000.0
        assert state.current_stop == pytest.approx(52000.0 * 0.98)

    def test_update_price_nonexistent_symbol(self, manager: TrailingStopManager) -> None:
        """Updating price for untracked symbol should not raise."""
        manager.update_price("NONEXISTENT", 100.0)

    def test_zero_activation_pct(self, manager: TrailingStopManager) -> None:
        """With 0 activation, trailing should activate immediately on any non-negative price."""
        manager.start_tracking("BTC/USDT", "buy", 50000.0, trail_pct=0.02, activation_pct=0.0)
        manager.update_price("BTC/USDT", 50000.0)
        state = manager.get_all_states()["BTC/USDT"]
        assert state.activated
        assert state.current_stop == pytest.approx(50000.0 * 0.98)


class TestUpdatePriceShort:
    """Tests for update_price on short positions."""

    def test_no_activation_below_threshold(self, manager: TrailingStopManager) -> None:
        manager.start_tracking("BTC/USDT", "sell", 50000.0, trail_pct=0.02, activation_pct=0.01)
        # Price drops 0.5% — below 1% activation threshold
        manager.update_price("BTC/USDT", 49750.0)
        state = manager.get_all_states()["BTC/USDT"]
        assert not state.activated

    def test_activation_at_threshold(self, manager: TrailingStopManager) -> None:
        manager.start_tracking("BTC/USDT", "sell", 50000.0, trail_pct=0.02, activation_pct=0.01)
        # Price drops 1%
        manager.update_price("BTC/USDT", 49500.0)
        state = manager.get_all_states()["BTC/USDT"]
        assert state.activated
        assert state.peak_price == 49500.0  # Trough for short
        assert state.current_stop == pytest.approx(49500.0 * 1.02)

    def test_trough_updates_on_lower_price(self, manager: TrailingStopManager) -> None:
        manager.start_tracking("BTC/USDT", "sell", 50000.0, trail_pct=0.02, activation_pct=0.01)
        manager.update_price("BTC/USDT", 49000.0)  # Activate
        manager.update_price("BTC/USDT", 48000.0)  # Lower trough
        state = manager.get_all_states()["BTC/USDT"]
        assert state.peak_price == 48000.0
        assert state.current_stop == pytest.approx(48000.0 * 1.02)

    def test_trough_does_not_update_on_higher_price(self, manager: TrailingStopManager) -> None:
        manager.start_tracking("BTC/USDT", "sell", 50000.0, trail_pct=0.02, activation_pct=0.01)
        manager.update_price("BTC/USDT", 49000.0)  # Activate + trough
        manager.update_price("BTC/USDT", 49500.0)  # Higher — trough stays
        state = manager.get_all_states()["BTC/USDT"]
        assert state.peak_price == 49000.0


class TestShouldTriggerStop:
    """Tests for should_trigger_stop."""

    def test_no_trigger_before_activation(self, manager: TrailingStopManager) -> None:
        manager.start_tracking("BTC/USDT", "buy", 50000.0, trail_pct=0.02, activation_pct=0.01)
        assert not manager.should_trigger_stop("BTC/USDT", 49000.0)

    def test_trigger_long_at_stop_level(self, manager: TrailingStopManager) -> None:
        manager.start_tracking("BTC/USDT", "buy", 50000.0, trail_pct=0.02, activation_pct=0.01)
        manager.update_price("BTC/USDT", 52000.0)  # Activate, peak=52000
        # Stop level = 52000 * 0.98 = 50960
        assert not manager.should_trigger_stop("BTC/USDT", 51000.0)
        assert manager.should_trigger_stop("BTC/USDT", 50960.0)
        assert manager.should_trigger_stop("BTC/USDT", 50000.0)

    def test_trigger_short_at_stop_level(self, manager: TrailingStopManager) -> None:
        manager.start_tracking("BTC/USDT", "sell", 50000.0, trail_pct=0.02, activation_pct=0.01)
        manager.update_price("BTC/USDT", 48000.0)  # Activate, trough=48000
        # Stop level = 48000 * 1.02 = 48960
        assert not manager.should_trigger_stop("BTC/USDT", 48500.0)
        assert manager.should_trigger_stop("BTC/USDT", 48960.0)
        assert manager.should_trigger_stop("BTC/USDT", 50000.0)

    def test_no_trigger_nonexistent_symbol(self, manager: TrailingStopManager) -> None:
        assert not manager.should_trigger_stop("NONEXISTENT", 100.0)

    def test_no_trigger_not_activated(self, manager: TrailingStopManager) -> None:
        manager.start_tracking("BTC/USDT", "buy", 50000.0, trail_pct=0.02, activation_pct=0.05)
        manager.update_price("BTC/USDT", 50100.0)  # Only 0.2% up
        assert not manager.should_trigger_stop("BTC/USDT", 49000.0)


class TestGetStopPrice:
    """Tests for get_stop_price."""

    def test_returns_none_when_not_tracking(self, manager: TrailingStopManager) -> None:
        assert manager.get_stop_price("BTC/USDT") is None

    def test_returns_none_before_activation(self, manager: TrailingStopManager) -> None:
        manager.start_tracking("BTC/USDT", "buy", 50000.0, trail_pct=0.02, activation_pct=0.01)
        assert manager.get_stop_price("BTC/USDT") is None

    def test_returns_stop_after_activation(self, manager: TrailingStopManager) -> None:
        manager.start_tracking("BTC/USDT", "buy", 50000.0, trail_pct=0.02, activation_pct=0.01)
        manager.update_price("BTC/USDT", 51000.0)
        assert manager.get_stop_price("BTC/USDT") == pytest.approx(51000.0 * 0.98)


class TestGetAllStates:
    """Tests for get_all_states."""

    def test_returns_empty_dict_initially(self, manager: TrailingStopManager) -> None:
        assert manager.get_all_states() == {}

    def test_returns_copy(self, manager: TrailingStopManager) -> None:
        manager.start_tracking("BTC/USDT", "buy", 50000.0)
        states = manager.get_all_states()
        states.clear()
        assert manager.is_tracking("BTC/USDT")


class TestSingleton:
    """Tests for the singleton pattern."""

    def test_get_trailing_stop_manager_returns_instance(self) -> None:
        mgr = get_trailing_stop_manager()
        assert isinstance(mgr, TrailingStopManager)

    def test_get_trailing_stop_manager_returns_same_instance(self) -> None:
        mgr1 = get_trailing_stop_manager()
        mgr2 = get_trailing_stop_manager()
        assert mgr1 is mgr2


class TestTrailingScenario:
    """End-to-end trailing stop scenarios."""

    def test_long_position_full_lifecycle(self, manager: TrailingStopManager) -> None:
        """Long: enter → rise → trail activates → price drops → stop triggers."""
        manager.start_tracking("BTC/USDT", "buy", 50000.0, trail_pct=0.02, activation_pct=0.01)

        # Price rises but below activation
        manager.update_price("BTC/USDT", 50400.0)
        assert not manager.should_trigger_stop("BTC/USDT", 50400.0)

        # Price rises to activate (1% up from 50000 = 50500)
        manager.update_price("BTC/USDT", 50600.0)
        assert manager.get_stop_price("BTC/USDT") == pytest.approx(50600.0 * 0.98)

        # Price rises more — stop ratchets up
        manager.update_price("BTC/USDT", 52000.0)
        stop = manager.get_stop_price("BTC/USDT")
        assert stop == pytest.approx(52000.0 * 0.98)

        # Price pulls back but still above stop
        manager.update_price("BTC/USDT", 51500.0)
        assert not manager.should_trigger_stop("BTC/USDT", 51500.0)
        # Stop stays at 52000 peak
        assert manager.get_stop_price("BTC/USDT") == pytest.approx(52000.0 * 0.98)

        # Price drops to stop level
        stop_price = 52000.0 * 0.98  # 50960
        assert manager.should_trigger_stop("BTC/USDT", stop_price)

    def test_short_position_full_lifecycle(self, manager: TrailingStopManager) -> None:
        """Short: enter → drop → trail activates → price rises → stop triggers."""
        manager.start_tracking("BTC/USDT", "sell", 50000.0, trail_pct=0.02, activation_pct=0.01)

        # Price drops but below activation
        manager.update_price("BTC/USDT", 49600.0)
        assert not manager.should_trigger_stop("BTC/USDT", 49600.0)

        # Price drops to activate (1% down from 50000 = 49500)
        manager.update_price("BTC/USDT", 49400.0)
        assert manager.get_stop_price("BTC/USDT") == pytest.approx(49400.0 * 1.02)

        # Price drops more — stop ratchets down
        manager.update_price("BTC/USDT", 48000.0)
        stop = manager.get_stop_price("BTC/USDT")
        assert stop == pytest.approx(48000.0 * 1.02)

        # Price bounces but still below stop
        manager.update_price("BTC/USDT", 48500.0)
        assert not manager.should_trigger_stop("BTC/USDT", 48500.0)

        # Price rises to stop level
        stop_price = 48000.0 * 1.02  # 48960
        assert manager.should_trigger_stop("BTC/USDT", stop_price)

    def test_multiple_symbols(self, manager: TrailingStopManager) -> None:
        """Track multiple symbols independently."""
        manager.start_tracking("BTC/USDT", "buy", 50000.0, trail_pct=0.02, activation_pct=0.01)
        manager.start_tracking("ETH/USDT", "sell", 3000.0, trail_pct=0.03, activation_pct=0.01)

        # Update BTC
        manager.update_price("BTC/USDT", 52000.0)
        assert manager.get_stop_price("BTC/USDT") == pytest.approx(52000.0 * 0.98)

        # ETH not affected
        assert manager.get_stop_price("ETH/USDT") is None

        # Update ETH
        manager.update_price("ETH/USDT", 2950.0)
        assert manager.get_stop_price("ETH/USDT") == pytest.approx(2950.0 * 1.03)

        # BTC not affected by ETH update
        assert manager.get_stop_price("BTC/USDT") == pytest.approx(52000.0 * 0.98)

    def test_replace_tracking(self, manager: TrailingStopManager) -> None:
        """Starting tracking for an already-tracked symbol replaces state."""
        manager.start_tracking("BTC/USDT", "buy", 50000.0)
        manager.update_price("BTC/USDT", 52000.0)  # Activate
        manager.start_tracking("BTC/USDT", "sell", 52000.0)  # Replace
        state = manager.get_all_states()["BTC/USDT"]
        assert state.side == "sell"
        assert state.entry_price == 52000.0
        assert state.activated is False
