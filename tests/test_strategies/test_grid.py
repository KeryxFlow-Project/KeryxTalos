"""Comprehensive tests for the Grid Trading Bot strategy."""

import pytest

from keryxflow.strategies.grid import (
    GridOrder,
    GridStrategy,
    GridType,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def arithmetic_grid() -> GridStrategy:
    """Create an arithmetic grid strategy."""
    return GridStrategy(
        symbol="BTC/USDT",
        upper_price=200.0,
        lower_price=100.0,
        grid_count=10,
        total_investment=1000.0,
        grid_type=GridType.ARITHMETIC,
    )


@pytest.fixture
def geometric_grid() -> GridStrategy:
    """Create a geometric grid strategy."""
    return GridStrategy(
        symbol="BTC/USDT",
        upper_price=200.0,
        lower_price=100.0,
        grid_count=10,
        total_investment=1000.0,
        grid_type=GridType.GEOMETRIC,
    )


# ---------------------------------------------------------------------------
# Construction / Validation
# ---------------------------------------------------------------------------


class TestGridStrategyCreation:
    """Tests for GridStrategy instantiation and validation."""

    def test_create_arithmetic_grid(self, arithmetic_grid: GridStrategy) -> None:
        assert arithmetic_grid.grid_type == GridType.ARITHMETIC
        assert arithmetic_grid.is_stopped is False
        assert arithmetic_grid.total_profit == 0.0
        assert arithmetic_grid.completed_cycles == 0

    def test_create_geometric_grid(self, geometric_grid: GridStrategy) -> None:
        assert geometric_grid.grid_type == GridType.GEOMETRIC

    def test_upper_must_exceed_lower(self) -> None:
        with pytest.raises(ValueError, match="upper_price must be greater"):
            GridStrategy(
                symbol="X",
                upper_price=100.0,
                lower_price=200.0,
                grid_count=5,
                total_investment=500.0,
            )

    def test_equal_upper_lower_raises(self) -> None:
        with pytest.raises(ValueError, match="upper_price must be greater"):
            GridStrategy(
                symbol="X",
                upper_price=100.0,
                lower_price=100.0,
                grid_count=5,
                total_investment=500.0,
            )

    def test_grid_count_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="grid_count must be at least 1"):
            GridStrategy(
                symbol="X",
                upper_price=200.0,
                lower_price=100.0,
                grid_count=0,
                total_investment=500.0,
            )

    def test_investment_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="total_investment must be positive"):
            GridStrategy(
                symbol="X",
                upper_price=200.0,
                lower_price=100.0,
                grid_count=5,
                total_investment=0.0,
            )


# ---------------------------------------------------------------------------
# Grid Level Calculation
# ---------------------------------------------------------------------------


class TestGridLevelCalculation:
    """Tests for calculate_grid_levels()."""

    def test_arithmetic_level_count(self, arithmetic_grid: GridStrategy) -> None:
        levels = arithmetic_grid.calculate_grid_levels()
        # grid_count + 1 levels (fence-post)
        assert len(levels) == 11

    def test_arithmetic_first_and_last(self, arithmetic_grid: GridStrategy) -> None:
        levels = arithmetic_grid.calculate_grid_levels()
        assert levels[0] == 100.0
        assert levels[-1] == 200.0

    def test_arithmetic_equal_spacing(self, arithmetic_grid: GridStrategy) -> None:
        levels = arithmetic_grid.calculate_grid_levels()
        step = (200.0 - 100.0) / 10
        for i in range(len(levels) - 1):
            assert abs(levels[i + 1] - levels[i] - step) < 1e-6

    def test_geometric_level_count(self, geometric_grid: GridStrategy) -> None:
        levels = geometric_grid.calculate_grid_levels()
        assert len(levels) == 11

    def test_geometric_first_and_last(self, geometric_grid: GridStrategy) -> None:
        levels = geometric_grid.calculate_grid_levels()
        assert levels[0] == 100.0
        assert abs(levels[-1] - 200.0) < 1e-6

    def test_geometric_equal_percentage_spacing(self, geometric_grid: GridStrategy) -> None:
        levels = geometric_grid.calculate_grid_levels()
        ratios = [levels[i + 1] / levels[i] for i in range(len(levels) - 1)]
        for r in ratios:
            assert abs(r - ratios[0]) < 1e-6

    def test_single_grid_interval(self) -> None:
        gs = GridStrategy(
            symbol="X",
            upper_price=200.0,
            lower_price=100.0,
            grid_count=1,
            total_investment=100.0,
        )
        levels = gs.calculate_grid_levels()
        assert len(levels) == 2
        assert levels[0] == 100.0
        assert levels[1] == 200.0

    def test_two_grid_intervals(self) -> None:
        gs = GridStrategy(
            symbol="X",
            upper_price=300.0,
            lower_price=100.0,
            grid_count=2,
            total_investment=200.0,
        )
        levels = gs.calculate_grid_levels()
        assert len(levels) == 3
        assert levels[0] == 100.0
        assert levels[1] == 200.0
        assert levels[2] == 300.0

    def test_geometric_known_values(self) -> None:
        """Geometric grid with ratio=2: 100 -> 200 in 1 step."""
        gs = GridStrategy(
            symbol="X",
            upper_price=400.0,
            lower_price=100.0,
            grid_count=2,
            total_investment=200.0,
            grid_type=GridType.GEOMETRIC,
        )
        levels = gs.calculate_grid_levels()
        assert len(levels) == 3
        assert levels[0] == 100.0
        assert abs(levels[1] - 200.0) < 1e-6  # 100 * (4)^(1/2) = 200
        assert abs(levels[2] - 400.0) < 1e-6

    def test_levels_are_sorted(self, arithmetic_grid: GridStrategy) -> None:
        levels = arithmetic_grid.calculate_grid_levels()
        assert levels == sorted(levels)

    def test_geometric_levels_are_sorted(self, geometric_grid: GridStrategy) -> None:
        levels = geometric_grid.calculate_grid_levels()
        assert levels == sorted(levels)


# ---------------------------------------------------------------------------
# Initial Order Generation
# ---------------------------------------------------------------------------


class TestInitialOrderGeneration:
    """Tests for generate_initial_orders()."""

    def test_buy_orders_below_sell_orders_above(self, arithmetic_grid: GridStrategy) -> None:
        orders = arithmetic_grid.generate_initial_orders(current_price=150.0)
        buys = [o for o in orders if o.side == "buy"]
        sells = [o for o in orders if o.side == "sell"]

        assert all(o.price < 150.0 for o in buys)
        assert all(o.price > 150.0 for o in sells)

    def test_no_order_at_current_price(self, arithmetic_grid: GridStrategy) -> None:
        # Price exactly on a grid level (150 is one of the arithmetic levels)
        orders = arithmetic_grid.generate_initial_orders(current_price=150.0)
        prices = [o.price for o in orders]
        assert 150.0 not in prices

    def test_correct_order_count(self, arithmetic_grid: GridStrategy) -> None:
        # With 11 levels and price at 150, levels 100-140 (5) are buys, 160-200 (5) are sells
        orders = arithmetic_grid.generate_initial_orders(current_price=150.0)
        assert len(orders) == 10  # 5 buys + 5 sells

    def test_quantity_calculation(self) -> None:
        gs = GridStrategy(
            symbol="X",
            upper_price=200.0,
            lower_price=100.0,
            grid_count=2,
            total_investment=200.0,
            grid_type=GridType.ARITHMETIC,
        )
        # Levels: 100, 150, 200. Capital per cell = 100.
        # Price at 150: buy at 100 (qty=100/100=1.0), sell at 200 (qty=100/150=0.666...)
        orders = gs.generate_initial_orders(current_price=150.0)
        buys = [o for o in orders if o.side == "buy"]
        sells = [o for o in orders if o.side == "sell"]

        assert len(buys) == 1
        assert buys[0].price == 100.0
        assert buys[0].quantity == 1.0  # 100/100

        assert len(sells) == 1
        assert sells[0].price == 200.0
        assert abs(sells[0].quantity - round(100.0 / 150.0, 8)) < 1e-8

    def test_price_at_lower_boundary(self, arithmetic_grid: GridStrategy) -> None:
        orders = arithmetic_grid.generate_initial_orders(current_price=100.0)
        # All levels above 100 should be sells, 100 is current price
        buys = [o for o in orders if o.side == "buy"]
        sells = [o for o in orders if o.side == "sell"]
        assert len(buys) == 0
        assert len(sells) == 10

    def test_price_at_upper_boundary(self, arithmetic_grid: GridStrategy) -> None:
        orders = arithmetic_grid.generate_initial_orders(current_price=200.0)
        buys = [o for o in orders if o.side == "buy"]
        sells = [o for o in orders if o.side == "sell"]
        assert len(buys) == 10
        assert len(sells) == 0

    def test_levels_initialized_after_generate(self, arithmetic_grid: GridStrategy) -> None:
        arithmetic_grid.generate_initial_orders(current_price=150.0)
        assert len(arithmetic_grid.levels) == 11
        assert arithmetic_grid._initialized is True

    def test_stopped_strategy_returns_empty(self, arithmetic_grid: GridStrategy) -> None:
        arithmetic_grid.is_stopped = True
        orders = arithmetic_grid.generate_initial_orders(current_price=150.0)
        assert orders == []

    def test_order_objects_are_grid_orders(self, arithmetic_grid: GridStrategy) -> None:
        orders = arithmetic_grid.generate_initial_orders(current_price=150.0)
        for order in orders:
            assert isinstance(order, GridOrder)
            assert order.quantity > 0
            assert order.side in ("buy", "sell")


# ---------------------------------------------------------------------------
# Order Fill Cycling
# ---------------------------------------------------------------------------


class TestOrderFillCycling:
    """Tests for on_order_filled()."""

    def test_buy_fill_creates_sell_above(self, arithmetic_grid: GridStrategy) -> None:
        arithmetic_grid.generate_initial_orders(current_price=150.0)

        # Buy filled at level 2 (price=120), should create sell at level 3 (price=130)
        counter = arithmetic_grid.on_order_filled(level_index=2, side="buy")

        assert counter is not None
        assert counter.side == "sell"
        assert counter.level_index == 3
        assert counter.price == 130.0

    def test_sell_fill_creates_buy_below(self, arithmetic_grid: GridStrategy) -> None:
        arithmetic_grid.generate_initial_orders(current_price=150.0)

        # Sell filled at level 7 (price=170), should create buy at level 6 (price=160)
        counter = arithmetic_grid.on_order_filled(level_index=7, side="sell")

        assert counter is not None
        assert counter.side == "buy"
        assert counter.level_index == 6
        assert counter.price == 160.0

    def test_buy_fill_at_top_boundary_no_counter(self, arithmetic_grid: GridStrategy) -> None:
        arithmetic_grid.generate_initial_orders(current_price=150.0)

        # Buy at the last level (index 10, price=200) - no sell above
        counter = arithmetic_grid.on_order_filled(level_index=10, side="buy")
        assert counter is None

    def test_sell_fill_at_bottom_boundary_no_counter(self, arithmetic_grid: GridStrategy) -> None:
        arithmetic_grid.generate_initial_orders(current_price=150.0)

        # Sell at the first level (index 0, price=100) - no buy below
        counter = arithmetic_grid.on_order_filled(level_index=0, side="sell")
        assert counter is None

    def test_sequential_cycle(self, arithmetic_grid: GridStrategy) -> None:
        """Simulate a full buy->sell cycle."""
        arithmetic_grid.generate_initial_orders(current_price=150.0)

        # Price drops to level 4 (140), buy fills
        sell_order = arithmetic_grid.on_order_filled(level_index=4, side="buy")
        assert sell_order is not None
        assert sell_order.side == "sell"
        assert sell_order.level_index == 5  # 150

        # Price rises back to level 5 (150), sell fills
        buy_order = arithmetic_grid.on_order_filled(level_index=5, side="sell")
        assert buy_order is not None
        assert buy_order.side == "buy"
        assert buy_order.level_index == 4  # 140

    def test_multiple_cycles_accumulate_profit(self, arithmetic_grid: GridStrategy) -> None:
        arithmetic_grid.generate_initial_orders(current_price=150.0)

        # Cycle 1: buy at 140, sell at 150
        arithmetic_grid.on_order_filled(level_index=4, side="buy")
        arithmetic_grid.on_order_filled(level_index=5, side="sell")

        assert arithmetic_grid.completed_cycles == 1
        assert arithmetic_grid.total_profit > 0

        # Cycle 2: buy at 140 again, sell at 150 again
        arithmetic_grid.on_order_filled(level_index=4, side="buy")
        arithmetic_grid.on_order_filled(level_index=5, side="sell")

        assert arithmetic_grid.completed_cycles == 2

    def test_stopped_strategy_returns_none(self, arithmetic_grid: GridStrategy) -> None:
        arithmetic_grid.generate_initial_orders(current_price=150.0)
        arithmetic_grid.is_stopped = True

        counter = arithmetic_grid.on_order_filled(level_index=2, side="buy")
        assert counter is None

    def test_invalid_level_index_returns_none(self, arithmetic_grid: GridStrategy) -> None:
        arithmetic_grid.generate_initial_orders(current_price=150.0)

        assert arithmetic_grid.on_order_filled(level_index=-1, side="buy") is None
        assert arithmetic_grid.on_order_filled(level_index=99, side="buy") is None

    def test_uninitialized_returns_none(self, arithmetic_grid: GridStrategy) -> None:
        # No generate_initial_orders called
        assert arithmetic_grid.on_order_filled(level_index=0, side="buy") is None


# ---------------------------------------------------------------------------
# Out-of-Range Behavior
# ---------------------------------------------------------------------------


class TestOutOfRangeBehavior:
    """Tests for check_price_in_range()."""

    def test_price_in_range(self, arithmetic_grid: GridStrategy) -> None:
        assert arithmetic_grid.check_price_in_range(150.0) is True
        assert arithmetic_grid.is_stopped is False

    def test_price_at_boundaries_is_in_range(self, arithmetic_grid: GridStrategy) -> None:
        assert arithmetic_grid.check_price_in_range(100.0) is True
        assert arithmetic_grid.check_price_in_range(200.0) is True

    def test_price_above_range_auto_stop(self, arithmetic_grid: GridStrategy) -> None:
        assert arithmetic_grid.check_price_in_range(201.0) is False
        assert arithmetic_grid.is_stopped is True

    def test_price_below_range_auto_stop(self, arithmetic_grid: GridStrategy) -> None:
        assert arithmetic_grid.check_price_in_range(99.0) is False
        assert arithmetic_grid.is_stopped is True

    def test_auto_stop_disabled(self) -> None:
        gs = GridStrategy(
            symbol="X",
            upper_price=200.0,
            lower_price=100.0,
            grid_count=5,
            total_investment=500.0,
            auto_stop_on_breakout=False,
        )

        assert gs.check_price_in_range(250.0) is False
        assert gs.is_stopped is False  # Should NOT stop

    def test_auto_stop_disabled_below(self) -> None:
        gs = GridStrategy(
            symbol="X",
            upper_price=200.0,
            lower_price=100.0,
            grid_count=5,
            total_investment=500.0,
            auto_stop_on_breakout=False,
        )

        assert gs.check_price_in_range(50.0) is False
        assert gs.is_stopped is False


# ---------------------------------------------------------------------------
# Profit Tracking
# ---------------------------------------------------------------------------


class TestProfitTracking:
    """Tests for profit tracking."""

    def test_no_profit_before_cycles(self, arithmetic_grid: GridStrategy) -> None:
        assert arithmetic_grid.total_profit == 0.0
        assert arithmetic_grid.get_profit_per_cycle() == 0.0

    def test_profit_after_sell_fill(self, arithmetic_grid: GridStrategy) -> None:
        arithmetic_grid.generate_initial_orders(current_price=150.0)

        # Buy at level 4 (140), sell at level 5 (150)
        arithmetic_grid.on_order_filled(level_index=4, side="buy")
        arithmetic_grid.on_order_filled(level_index=5, side="sell")

        # Profit = (150 - 140) * quantity
        # quantity = capital_per_cell / 140 = 100/140
        expected_quantity = round(100.0 / 140.0, 8)
        expected_profit = 10.0 * expected_quantity

        assert abs(arithmetic_grid.total_profit - expected_profit) < 1e-6
        assert arithmetic_grid.completed_cycles == 1

    def test_profit_per_cycle(self, arithmetic_grid: GridStrategy) -> None:
        arithmetic_grid.generate_initial_orders(current_price=150.0)

        # Two cycles at same levels
        for _ in range(2):
            arithmetic_grid.on_order_filled(level_index=4, side="buy")
            arithmetic_grid.on_order_filled(level_index=5, side="sell")

        per_cycle = arithmetic_grid.get_profit_per_cycle()
        assert per_cycle > 0
        assert abs(per_cycle - arithmetic_grid.total_profit / 2) < 1e-8

    def test_buy_fill_does_not_add_profit(self, arithmetic_grid: GridStrategy) -> None:
        arithmetic_grid.generate_initial_orders(current_price=150.0)

        arithmetic_grid.on_order_filled(level_index=4, side="buy")
        assert arithmetic_grid.total_profit == 0.0
        assert arithmetic_grid.completed_cycles == 0

    def test_geometric_grid_profit(self, geometric_grid: GridStrategy) -> None:
        """Geometric grid profit differs from arithmetic."""
        geometric_grid.generate_initial_orders(current_price=150.0)

        levels = geometric_grid.calculate_grid_levels()
        # Find a buy level below 150 and the sell level above it
        buy_idx = None
        for i, lvl in enumerate(levels):
            if lvl < 150.0:
                buy_idx = i

        assert buy_idx is not None
        geometric_grid.on_order_filled(level_index=buy_idx, side="buy")
        geometric_grid.on_order_filled(level_index=buy_idx + 1, side="sell")

        assert geometric_grid.total_profit > 0
        assert geometric_grid.completed_cycles == 1


# ---------------------------------------------------------------------------
# Status / Serialization
# ---------------------------------------------------------------------------


class TestGetStatus:
    """Tests for get_status()."""

    def test_status_before_init(self, arithmetic_grid: GridStrategy) -> None:
        status = arithmetic_grid.get_status()
        assert status["is_initialized"] is False
        assert status["is_stopped"] is False
        assert status["total_profit"] == 0.0
        assert status["levels"] == []

    def test_status_after_init(self, arithmetic_grid: GridStrategy) -> None:
        arithmetic_grid.generate_initial_orders(current_price=150.0)
        status = arithmetic_grid.get_status()

        assert status["is_initialized"] is True
        assert status["symbol"] == "BTC/USDT"
        assert status["grid_type"] == "arithmetic"
        assert status["grid_count"] == 10
        assert len(status["levels"]) == 11

    def test_status_after_cycle(self, arithmetic_grid: GridStrategy) -> None:
        arithmetic_grid.generate_initial_orders(current_price=150.0)
        arithmetic_grid.on_order_filled(level_index=4, side="buy")
        arithmetic_grid.on_order_filled(level_index=5, side="sell")

        status = arithmetic_grid.get_status()
        assert status["completed_cycles"] == 1
        assert status["total_profit"] > 0
        assert status["profit_per_cycle"] > 0


# ---------------------------------------------------------------------------
# StrategyType.GRID integration
# ---------------------------------------------------------------------------


class TestStrategyTypeGrid:
    """Test GRID enum integration with StrategyManager."""

    def test_grid_enum_exists(self) -> None:
        from keryxflow.agent.strategy import StrategyType

        assert StrategyType.GRID.value == "grid"

    def test_grid_default_strategy_registered(self) -> None:
        from keryxflow.agent.strategy import StrategyManager

        manager = StrategyManager()
        grid = manager.get_strategy("grid_default")

        assert grid is not None
        assert grid.name == "Grid Trading Bot"
        assert grid.parameters["grid_count"] == 10
        assert grid.parameters["grid_type"] == "arithmetic"

    @pytest.mark.asyncio
    async def test_grid_selected_for_ranging_market(self) -> None:
        from keryxflow.agent.strategy import MarketRegime, StrategyManager

        manager = StrategyManager()
        selection = await manager.select_strategy(
            symbol="BTC/USDT",
            prices=[100] * 50,
            force_regime=MarketRegime.RANGING,
        )

        # Grid should be the top or among the top strategies for ranging
        assert selection.detected_regime == MarketRegime.RANGING
        # The grid_default has 0.95 suitability for RANGING, highest among defaults
        assert selection.strategy.id == "grid_default"
