"""DCA (Dollar Cost Averaging) bot strategy."""

from dataclasses import dataclass


@dataclass
class DCAStrategy:
    """DCA bot strategy with safety orders and Martingale scaling.

    Implements the math/logic layer for a DCA trading bot. Safety orders are
    placed at increasing price deviations below the entry price, with optional
    Martingale size scaling and step multipliers for deviation spacing.
    """

    base_order_size: float
    """USDT amount for the initial buy."""

    safety_order_size: float
    """USDT amount for each safety order (before multiplier scaling)."""

    safety_order_count: int = 5
    """Maximum number of safety orders."""

    price_deviation_pct: float = 1.5
    """Percentage drop from entry to trigger the first safety order."""

    take_profit_pct: float = 1.5
    """Percentage above average entry price to take profit."""

    size_multiplier: float = 1.5
    """Martingale multiplier applied to each successive safety order size."""

    step_multiplier: float = 1.0
    """Multiplier for deviation spacing between successive safety orders."""

    def calculate_safety_order_prices(self, entry_price: float) -> list[tuple[float, float]]:
        """Calculate trigger prices and sizes for all safety orders.

        Each safety order's deviation from entry compounds as:
            deviation_i = price_deviation_pct * step_multiplier^(i-1)
            cumulative_deviation = sum of all deviations up to order i
            trigger_price = entry_price * (1 - cumulative_deviation / 100)

        Each safety order's size scales as:
            size_i = safety_order_size * size_multiplier^(i-1)

        Args:
            entry_price: The initial entry price.

        Returns:
            List of (trigger_price, size_in_usdt) tuples for each safety order.
        """
        orders: list[tuple[float, float]] = []
        cumulative_deviation = 0.0

        for i in range(self.safety_order_count):
            deviation = self.price_deviation_pct * (self.step_multiplier**i)
            cumulative_deviation += deviation
            trigger_price = entry_price * (1 - cumulative_deviation / 100)
            size = self.safety_order_size * (self.size_multiplier**i)
            orders.append((trigger_price, size))

        return orders

    def calculate_average_entry(self, fills: list[tuple[float, float]]) -> float:
        """Calculate the weighted average entry price from fills.

        Args:
            fills: List of (price, quantity) tuples.

        Returns:
            Weighted average price. Returns 0.0 if total quantity is zero.
        """
        total_cost = sum(price * qty for price, qty in fills)
        total_qty = sum(qty for _, qty in fills)
        if total_qty == 0:
            return 0.0
        return total_cost / total_qty

    def calculate_take_profit_price(self, avg_entry: float) -> float:
        """Calculate the take-profit price from average entry.

        Args:
            avg_entry: The weighted average entry price.

        Returns:
            Target price for taking profit.
        """
        return avg_entry * (1 + self.take_profit_pct / 100)

    def should_place_safety_order(
        self,
        current_price: float,
        entry_price: float,
        safety_orders_filled: int,
    ) -> bool:
        """Check whether the next safety order should be triggered.

        Args:
            current_price: The current market price.
            entry_price: The initial entry price.
            safety_orders_filled: Number of safety orders already filled.

        Returns:
            True if current_price has dropped to or below the next safety
            order's trigger price and there are remaining safety orders.
        """
        if safety_orders_filled >= self.safety_order_count:
            return False

        orders = self.calculate_safety_order_prices(entry_price)
        trigger_price = orders[safety_orders_filled][0]
        return current_price <= trigger_price

    def get_required_capital(self) -> float:
        """Calculate total capital needed for base order plus all safety orders.

        Returns:
            Total USDT required assuming all safety orders fill.
        """
        total = self.base_order_size
        for i in range(self.safety_order_count):
            total += self.safety_order_size * (self.size_multiplier**i)
        return total
