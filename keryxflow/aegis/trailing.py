"""Trailing stop manager for dynamic stop-loss tracking."""

from __future__ import annotations

from keryxflow.config import get_settings


class TrailingStopManager:
    """
    Tracks highest price per symbol and computes trailing stop levels.

    The trailing stop moves up with price but never moves down,
    providing a dynamic exit level that locks in profits.
    """

    def __init__(
        self,
        trailing_pct: float | None = None,
        breakeven_pct: float | None = None,
    ) -> None:
        settings = get_settings().risk
        self.trailing_pct: float = (
            trailing_pct if trailing_pct is not None else settings.trailing_stop_pct
        )
        self.breakeven_pct: float = (
            breakeven_pct if breakeven_pct is not None else settings.breakeven_trigger_pct
        )
        self._highest_prices: dict[str, float] = {}

    def update_price(self, symbol: str, price: float) -> None:
        """Track highest price for a symbol."""
        if symbol not in self._highest_prices or price > self._highest_prices[symbol]:
            self._highest_prices[symbol] = price

    def get_stop_level(self, symbol: str) -> float | None:
        """Return trailing stop level, or None if symbol is not tracked."""
        highest = self._highest_prices.get(symbol)
        if highest is None:
            return None
        return highest * (1 - self.trailing_pct / 100)

    def should_trigger_stop(self, symbol: str, current_price: float) -> bool:
        """Return True if current price is at or below the trailing stop level."""
        stop_level = self.get_stop_level(symbol)
        if stop_level is None:
            return False
        return current_price <= stop_level

    def reset(self, symbol: str) -> None:
        """Clear tracking for a symbol."""
        self._highest_prices.pop(symbol, None)


# Global instance
_trailing_stop_manager: TrailingStopManager | None = None


def get_trailing_stop_manager(
    trailing_pct: float | None = None,
    breakeven_pct: float | None = None,
) -> TrailingStopManager:
    """Get the global trailing stop manager instance."""
    global _trailing_stop_manager
    if _trailing_stop_manager is None:
        _trailing_stop_manager = TrailingStopManager(
            trailing_pct=trailing_pct,
            breakeven_pct=breakeven_pct,
        )
    return _trailing_stop_manager
