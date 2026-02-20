"""DCA (Dollar Cost Averaging) bot strategy implementation."""

from dataclasses import dataclass


@dataclass
class DCAStrategy:
    """DCA bot strategy with safety orders, martingale sizing, and take profit.

    Calculates safety order trigger prices, order sizes, average entry,
    take profit targets, and required capital for a DCA trading bot.
    """

    base_order_size: float = 100.0
    safety_order_size: float = 50.0
    safety_order_count: int = 5
    deviation_pct: float = 0.01
    step_multiplier: float = 1.0
    size_multiplier: float = 1.0
    take_profit_pct: float = 0.01

    def safety_order_prices(self, base_price: float) -> list[float]:
        """Calculate trigger prices for each safety order.

        With step_multiplier=1.0, prices decrease by a fixed deviation_pct.
        With step_multiplier>1.0, each gap widens: gap_n = deviation_pct * step_multiplier^(n-1).
        """
        prices: list[float] = []
        cumulative_deviation = 0.0
        for i in range(self.safety_order_count):
            gap = self.deviation_pct * (self.step_multiplier**i)
            cumulative_deviation += gap
            prices.append(base_price * (1 - cumulative_deviation))
        return prices

    def safety_order_sizes(self) -> list[float]:
        """Calculate the size of each safety order with martingale scaling."""
        sizes: list[float] = []
        for i in range(self.safety_order_count):
            sizes.append(self.safety_order_size * (self.size_multiplier**i))
        return sizes

    def average_entry(self, fills: list[tuple[float, float]]) -> float:
        """Calculate weighted average entry price from fills.

        Args:
            fills: List of (price, quantity) tuples.
        """
        total_cost = sum(price * qty for price, qty in fills)
        total_qty = sum(qty for _, qty in fills)
        return total_cost / total_qty

    def take_profit_price(self, avg_entry: float) -> float:
        """Calculate take profit price from average entry."""
        return avg_entry * (1 + self.take_profit_pct)

    def should_place_safety_order(
        self,
        current_price: float,
        base_price: float,
        safety_orders_filled: int,
    ) -> bool:
        """Check whether the next safety order should be placed.

        Returns False if all safety orders have been filled.
        Returns True if current price is at or below the next safety order trigger.
        """
        if safety_orders_filled >= self.safety_order_count:
            return False
        trigger_prices = self.safety_order_prices(base_price)
        return current_price <= trigger_prices[safety_orders_filled]

    def required_capital(self) -> float:
        """Calculate total capital needed (base order + all safety orders)."""
        return self.base_order_size + sum(self.safety_order_sizes())
