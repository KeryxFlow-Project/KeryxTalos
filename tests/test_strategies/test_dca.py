"""Tests for DCA bot strategy."""

import pytest

from keryxflow.strategies.dca import DCAStrategy


def test_safety_order_prices_arithmetic():
    """Verify prices decrease by deviation_pct with step_multiplier=1.0."""
    strategy = DCAStrategy(deviation_pct=0.01, safety_order_count=3, step_multiplier=1.0)
    base_price = 1000.0
    prices = strategy.safety_order_prices(base_price)

    assert len(prices) == 3
    assert prices[0] == pytest.approx(990.0)  # 1000 * (1 - 0.01)
    assert prices[1] == pytest.approx(980.0)  # 1000 * (1 - 0.02)
    assert prices[2] == pytest.approx(970.0)  # 1000 * (1 - 0.03)


def test_safety_order_prices_with_step_multiplier():
    """Verify step_multiplier widens gaps between safety orders."""
    strategy = DCAStrategy(deviation_pct=0.01, safety_order_count=3, step_multiplier=2.0)
    base_price = 1000.0
    prices = strategy.safety_order_prices(base_price)

    # gap_0 = 0.01 * 2^0 = 0.01, cumulative = 0.01
    # gap_1 = 0.01 * 2^1 = 0.02, cumulative = 0.03
    # gap_2 = 0.01 * 2^2 = 0.04, cumulative = 0.07
    assert len(prices) == 3
    assert prices[0] == pytest.approx(990.0)  # 1000 * (1 - 0.01)
    assert prices[1] == pytest.approx(970.0)  # 1000 * (1 - 0.03)
    assert prices[2] == pytest.approx(930.0)  # 1000 * (1 - 0.07)


def test_safety_order_sizes_with_martingale():
    """Verify size_multiplier increases sizes for each subsequent order."""
    strategy = DCAStrategy(safety_order_size=50.0, safety_order_count=4, size_multiplier=2.0)
    sizes = strategy.safety_order_sizes()

    assert len(sizes) == 4
    assert sizes[0] == pytest.approx(50.0)
    assert sizes[1] == pytest.approx(100.0)
    assert sizes[2] == pytest.approx(200.0)
    assert sizes[3] == pytest.approx(400.0)


def test_average_entry_calculation():
    """Weighted average from multiple fills."""
    strategy = DCAStrategy()
    fills = [
        (1000.0, 1.0),  # bought 1 at 1000
        (900.0, 2.0),  # bought 2 at 900
    ]
    avg = strategy.average_entry(fills)

    # (1000*1 + 900*2) / (1+2) = 2800/3 ≈ 933.33
    assert avg == pytest.approx(2800.0 / 3.0)


def test_take_profit_price():
    """Verify take profit calculation from avg entry."""
    strategy = DCAStrategy(take_profit_pct=0.02)
    avg_entry = 950.0
    tp = strategy.take_profit_price(avg_entry)

    assert tp == pytest.approx(950.0 * 1.02)


def test_should_place_safety_order():
    """Returns True when price drops enough to trigger next safety order."""
    strategy = DCAStrategy(deviation_pct=0.01, safety_order_count=3, step_multiplier=1.0)
    base_price = 1000.0

    # First SO triggers at 990.0; price at 989 should trigger
    assert strategy.should_place_safety_order(989.0, base_price, 0) is True
    # Price at 991 should NOT trigger
    assert strategy.should_place_safety_order(991.0, base_price, 0) is False
    # Second SO triggers at 980.0; price at 980 exactly should trigger
    assert strategy.should_place_safety_order(980.0, base_price, 1) is True


def test_should_not_place_when_all_filled():
    """Returns False when safety_orders_filled >= safety_order_count."""
    strategy = DCAStrategy(safety_order_count=3)

    assert strategy.should_place_safety_order(500.0, 1000.0, 3) is False
    assert strategy.should_place_safety_order(500.0, 1000.0, 5) is False


def test_required_capital():
    """Sum of base + all safety order sizes."""
    strategy = DCAStrategy(
        base_order_size=100.0,
        safety_order_size=50.0,
        safety_order_count=3,
        size_multiplier=2.0,
    )
    # base=100, SOs: 50 + 100 + 200 = 350, total = 450
    assert strategy.required_capital() == pytest.approx(450.0)


def test_default_values():
    """Verify sensible defaults."""
    strategy = DCAStrategy()

    assert strategy.base_order_size == 100.0
    assert strategy.safety_order_size == 50.0
    assert strategy.safety_order_count == 5
    assert strategy.deviation_pct == 0.01
    assert strategy.step_multiplier == 1.0
    assert strategy.size_multiplier == 1.0
    assert strategy.take_profit_pct == 0.01
