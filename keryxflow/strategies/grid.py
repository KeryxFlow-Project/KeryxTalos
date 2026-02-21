from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class GridType(str, Enum):
    """Grid spacing type."""

    ARITHMETIC = "arithmetic"
    GEOMETRIC = "geometric"


@dataclass
class GridOrder:
    """A single grid order."""

    price: float
    quantity: float
    side: str  # "buy" or "sell"
    level_index: int


class GridStrategy:
    """Grid bot trading strategy with arithmetic or geometric level spacing."""

    def __init__(
        self,
        symbol: str,
        lower_price: float,
        upper_price: float,
        grid_count: int,
        total_investment: float,
        grid_type: str | GridType = GridType.ARITHMETIC,
        auto_stop_on_breakout: bool = True,
    ) -> None:
        if upper_price <= lower_price:
            raise ValueError(
                f"upper_price must be greater than lower_price "
                f"(got upper={upper_price}, lower={lower_price})"
            )
        if grid_count < 1:
            raise ValueError(f"grid_count must be at least 1 (got {grid_count})")
        if total_investment <= 0:
            raise ValueError(f"total_investment must be positive (got {total_investment})")

        if isinstance(grid_type, str):
            grid_type = GridType(grid_type)

        self.symbol = symbol
        self.lower_price = lower_price
        self.upper_price = upper_price
        self.grid_count = grid_count
        self.total_investment = total_investment
        self.grid_type = grid_type
        self.auto_stop_on_breakout = auto_stop_on_breakout

        self.is_stopped = False
        self.total_profit = 0.0
        self.completed_cycles = 0
        self.levels: list[float] = []
        self._initialized = False
        self._pending_buys: dict[int, float] = {}  # level_index -> quantity
        self._capital_per_cell = total_investment / grid_count

    def calculate_grid_levels(self) -> list[float]:
        """Generate grid price levels including lower and upper bounds.

        Returns grid_count + 1 levels (fence-post).
        """
        if self.grid_type == GridType.ARITHMETIC:
            step = (self.upper_price - self.lower_price) / self.grid_count
            return [self.lower_price + i * step for i in range(self.grid_count + 1)]

        # geometric
        ratio = (self.upper_price / self.lower_price) ** (1 / self.grid_count)
        return [self.lower_price * (ratio**i) for i in range(self.grid_count + 1)]

    def generate_initial_orders(self, current_price: float) -> list[GridOrder]:
        """Generate initial grid orders around the current price.

        Buy orders are placed below current_price, sell orders above.
        No order is placed at the exact current_price level.
        """
        if self.is_stopped:
            return []

        self.levels = self.calculate_grid_levels()
        self._initialized = True

        orders: list[GridOrder] = []
        for i, level in enumerate(self.levels):
            if level < current_price:
                quantity = round(self._capital_per_cell / level, 8)
                orders.append(GridOrder(price=level, quantity=quantity, side="buy", level_index=i))
            elif level > current_price:
                quantity = round(self._capital_per_cell / current_price, 8)
                orders.append(GridOrder(price=level, quantity=quantity, side="sell", level_index=i))
            # skip level == current_price

        return orders

    def on_order_filled(self, level_index: int, side: str) -> GridOrder | None:
        """Handle an order fill and return the counter-order, if any.

        A buy fill at level *i* creates a sell at level *i+1*.
        A sell fill at level *j* creates a buy at level *j-1*.
        Profit is recorded when a sell completes a buy-sell cycle.
        """
        if self.is_stopped or not self._initialized:
            return None
        if level_index < 0 or level_index >= len(self.levels):
            return None

        if side == "buy":
            quantity = round(self._capital_per_cell / self.levels[level_index], 8)
            self._pending_buys[level_index] = quantity

            sell_index = level_index + 1
            if sell_index >= len(self.levels):
                return None

            return GridOrder(
                price=self.levels[sell_index],
                quantity=quantity,
                side="sell",
                level_index=sell_index,
            )

        if side == "sell":
            buy_index = level_index - 1

            # Complete cycle if there was a pending buy one level below
            if buy_index >= 0 and buy_index in self._pending_buys:
                buy_qty = self._pending_buys.pop(buy_index)
                profit = (self.levels[level_index] - self.levels[buy_index]) * buy_qty
                self.total_profit += profit
                self.completed_cycles += 1

            if buy_index < 0:
                return None

            buy_quantity = round(self._capital_per_cell / self.levels[buy_index], 8)
            return GridOrder(
                price=self.levels[buy_index],
                quantity=buy_quantity,
                side="buy",
                level_index=buy_index,
            )

        return None

    def check_price_in_range(self, price: float) -> bool:
        """Check if price is within grid bounds. Auto-stops if out of range."""
        in_range = self.lower_price <= price <= self.upper_price
        if not in_range and self.auto_stop_on_breakout:
            self.is_stopped = True
        return in_range

    def get_profit_per_cycle(self) -> float:
        """Average profit per completed cycle."""
        if self.completed_cycles == 0:
            return 0.0
        return self.total_profit / self.completed_cycles

    def get_status(self) -> dict[str, Any]:
        """Return a status dictionary with grid info and profit."""
        return {
            "symbol": self.symbol,
            "grid_type": self.grid_type.value,
            "grid_count": self.grid_count,
            "lower_price": self.lower_price,
            "upper_price": self.upper_price,
            "total_investment": self.total_investment,
            "is_initialized": self._initialized,
            "is_stopped": self.is_stopped,
            "levels": list(self.levels),
            "total_profit": self.total_profit,
            "completed_cycles": self.completed_cycles,
            "profit_per_cycle": self.get_profit_per_cycle(),
        }
