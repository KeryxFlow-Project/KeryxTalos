"""Grid trading strategy - pure math/logic for grid bot parameters."""

from dataclasses import dataclass
from typing import Literal


@dataclass
class GridStrategy:
    """Grid trading strategy configuration and calculations.

    A grid bot places buy and sell orders at predefined price levels
    within a range, profiting from price oscillations.
    """

    upper_price: float
    lower_price: float
    grid_count: int = 10
    total_investment: float = 0.0
    grid_type: Literal["arithmetic", "geometric"] = "arithmetic"

    def __post_init__(self) -> None:
        if self.upper_price <= self.lower_price:
            raise ValueError("upper_price must be greater than lower_price")
        if self.grid_count < 2:
            raise ValueError("grid_count must be at least 2")
        if self.total_investment < 0:
            raise ValueError("total_investment must be non-negative")
        if self.lower_price <= 0:
            raise ValueError("lower_price must be positive")

    def calculate_grid_levels(self) -> list[float]:
        """Return sorted list of price levels for the grid.

        Arithmetic: equal absolute spacing between levels.
        Geometric: equal percentage spacing between levels.
        """
        n = self.grid_count
        if self.grid_type == "arithmetic":
            step = (self.upper_price - self.lower_price) / (n - 1)
            return [self.lower_price + i * step for i in range(n)]
        else:
            ratio = (self.upper_price / self.lower_price) ** (1 / (n - 1))
            return [self.lower_price * (ratio**i) for i in range(n)]

    def calculate_order_size(self) -> float:
        """Return the USDT amount allocated per grid level."""
        return self.total_investment / self.grid_count

    def get_buy_levels(self, current_price: float) -> list[float]:
        """Return grid levels below the current price (buy zones)."""
        return [lvl for lvl in self.calculate_grid_levels() if lvl < current_price]

    def get_sell_levels(self, current_price: float) -> list[float]:
        """Return grid levels above the current price (sell zones)."""
        return [lvl for lvl in self.calculate_grid_levels() if lvl > current_price]

    def is_price_in_range(self, price: float) -> bool:
        """Return True if price is within the grid range (inclusive)."""
        return self.lower_price <= price <= self.upper_price

    def calculate_profit_per_grid(self) -> float:
        """Return estimated profit from one buy-sell grid cycle.

        For arithmetic grids: spacing * order_size / average_level_price.
        For geometric grids: percentage_step * order_size.
        """
        order_size = self.calculate_order_size()
        if self.grid_type == "arithmetic":
            spacing = self.get_grid_spacing()
            avg_price = (self.upper_price + self.lower_price) / 2
            return spacing * order_size / avg_price
        else:
            ratio = self.get_grid_spacing()
            return ratio * order_size

    def get_grid_spacing(self) -> float:
        """Return the distance between adjacent grid levels.

        Arithmetic: absolute price difference.
        Geometric: percentage ratio between adjacent levels (e.g. 0.02 = 2%).
        """
        if self.grid_type == "arithmetic":
            return (self.upper_price - self.lower_price) / (self.grid_count - 1)
        else:
            ratio = (self.upper_price / self.lower_price) ** (1 / (self.grid_count - 1))
            return ratio - 1
