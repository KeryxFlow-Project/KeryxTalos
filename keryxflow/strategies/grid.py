from __future__ import annotations


class GridStrategy:
    """Grid bot trading strategy with arithmetic or geometric level spacing."""

    def __init__(
        self,
        lower_price: float,
        upper_price: float,
        grid_count: int,
        total_investment: float,
        grid_type: str = "arithmetic",
    ) -> None:
        if lower_price >= upper_price:
            raise ValueError(
                f"lower_price ({lower_price}) must be less than upper_price ({upper_price})"
            )
        if grid_count < 2:
            raise ValueError(f"grid_count ({grid_count}) must be at least 2")
        if grid_type not in ("arithmetic", "geometric"):
            raise ValueError(f"grid_type must be 'arithmetic' or 'geometric', got '{grid_type}'")

        self.lower_price = lower_price
        self.upper_price = upper_price
        self.grid_count = grid_count
        self.total_investment = total_investment
        self.grid_type = grid_type

    def generate_levels(self) -> list[float]:
        """Generate grid price levels including lower and upper bounds.

        Returns grid_count + 1 levels.
        """
        if self.grid_type == "arithmetic":
            step = (self.upper_price - self.lower_price) / self.grid_count
            return [self.lower_price + i * step for i in range(self.grid_count + 1)]

        # geometric
        ratio = (self.upper_price / self.lower_price) ** (1 / self.grid_count)
        return [self.lower_price * (ratio**i) for i in range(self.grid_count + 1)]

    def get_buy_levels(self, current_price: float) -> list[float]:
        """Return grid levels strictly below current_price."""
        return [level for level in self.generate_levels() if level < current_price]

    def get_sell_levels(self, current_price: float) -> list[float]:
        """Return grid levels strictly above current_price."""
        return [level for level in self.generate_levels() if level > current_price]

    @property
    def order_size(self) -> float:
        """Investment allocated per grid level."""
        return self.total_investment / self.grid_count

    def price_in_range(self, price: float) -> bool:
        """Check if price is within the grid range (inclusive)."""
        return self.lower_price <= price <= self.upper_price

    @property
    def profit_per_grid(self) -> float:
        """Estimated profit from one buy-sell cycle at adjacent grid levels.

        For arithmetic grids: order_size * (step / lower_price)
        For geometric grids: order_size * (ratio - 1)
        """
        if self.grid_type == "arithmetic":
            step = (self.upper_price - self.lower_price) / self.grid_count
            return self.order_size * (step / self.lower_price)

        ratio = (self.upper_price / self.lower_price) ** (1 / self.grid_count)
        return self.order_size * (ratio - 1)
