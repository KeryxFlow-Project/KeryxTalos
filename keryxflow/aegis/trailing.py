"""Trailing stop manager for dynamic stop-loss tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from keryxflow.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TrailingStopState:
    """State for a single trailing stop being tracked."""

    symbol: str
    side: Literal["buy", "sell"]
    entry_price: float
    trail_pct: float
    activation_pct: float
    peak_price: float = field(init=False)
    current_stop: float | None = field(init=False, default=None)
    activated: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        """Initialize peak price from entry."""
        if self.side == "buy":
            self.peak_price = self.entry_price
        else:
            # For short positions, track trough (lowest price)
            self.peak_price = self.entry_price


class TrailingStopManager:
    """Manages trailing stops for open positions.

    For long positions: trails below the peak high.
    For short positions: trails above the trough low.

    Activation threshold gates when trailing begins — only after
    the position has moved a minimum percentage in profit.
    """

    def __init__(self) -> None:
        """Initialize the trailing stop manager."""
        self._states: dict[str, TrailingStopState] = {}

    def start_tracking(
        self,
        symbol: str,
        side: Literal["buy", "sell"],
        entry_price: float,
        trail_pct: float = 0.02,
        activation_pct: float = 0.01,
    ) -> None:
        """Start tracking a trailing stop for a symbol.

        Args:
            symbol: Trading pair symbol
            side: Position side ("buy" for long, "sell" for short)
            entry_price: Position entry price
            trail_pct: Trailing distance as fraction (0.02 = 2%)
            activation_pct: Minimum profit before trailing activates (0.01 = 1%)
        """
        self._states[symbol] = TrailingStopState(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            trail_pct=trail_pct,
            activation_pct=activation_pct,
        )
        logger.info(
            "trailing_stop_tracking_started",
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            trail_pct=trail_pct,
            activation_pct=activation_pct,
        )

    def stop_tracking(self, symbol: str) -> None:
        """Stop tracking a trailing stop for a symbol."""
        if symbol in self._states:
            del self._states[symbol]
            logger.info("trailing_stop_tracking_stopped", symbol=symbol)

    def stop_tracking_all(self) -> None:
        """Stop tracking all trailing stops."""
        self._states.clear()
        logger.info("trailing_stop_tracking_all_stopped")

    def update_price(self, symbol: str, price: float) -> None:
        """Update price and recompute trailing stop level.

        Args:
            symbol: Trading pair symbol
            price: Current market price
        """
        state = self._states.get(symbol)
        if state is None:
            return

        if state.side == "buy":
            # Long position: check if activation threshold reached
            profit_pct = (price - state.entry_price) / state.entry_price
            if not state.activated and profit_pct >= state.activation_pct:
                state.activated = True
                logger.info(
                    "trailing_stop_activated",
                    symbol=symbol,
                    price=price,
                    profit_pct=profit_pct,
                )

            if state.activated:
                # Update peak (highest price seen)
                if price > state.peak_price:
                    state.peak_price = price
                # Compute stop level: trail below peak
                state.current_stop = state.peak_price * (1 - state.trail_pct)
        else:
            # Short position: check if activation threshold reached
            profit_pct = (state.entry_price - price) / state.entry_price
            if not state.activated and profit_pct >= state.activation_pct:
                state.activated = True
                logger.info(
                    "trailing_stop_activated",
                    symbol=symbol,
                    price=price,
                    profit_pct=profit_pct,
                )

            if state.activated:
                # Update trough (lowest price seen)
                if price < state.peak_price:
                    state.peak_price = price
                # Compute stop level: trail above trough
                state.current_stop = state.peak_price * (1 + state.trail_pct)

    def should_trigger_stop(self, symbol: str, price: float) -> bool:
        """Check if the trailing stop should trigger for a symbol.

        Args:
            symbol: Trading pair symbol
            price: Current market price

        Returns:
            True if the stop should trigger
        """
        state = self._states.get(symbol)
        if state is None or not state.activated or state.current_stop is None:
            return False

        if state.side == "buy":
            # Long: trigger if price falls to or below stop
            return price <= state.current_stop
        else:
            # Short: trigger if price rises to or above stop
            return price >= state.current_stop

    def get_stop_price(self, symbol: str) -> float | None:
        """Get the current trailing stop price for a symbol.

        Returns:
            The stop price, or None if not tracking or not activated
        """
        state = self._states.get(symbol)
        if state is None:
            return None
        return state.current_stop

    def is_tracking(self, symbol: str) -> bool:
        """Check if a symbol is being tracked."""
        return symbol in self._states

    def get_all_states(self) -> dict[str, TrailingStopState]:
        """Get all trailing stop states."""
        return dict(self._states)


# Global singleton
_trailing_stop_manager: TrailingStopManager | None = None


def get_trailing_stop_manager() -> TrailingStopManager:
    """Get the global trailing stop manager instance."""
    global _trailing_stop_manager
    if _trailing_stop_manager is None:
        _trailing_stop_manager = TrailingStopManager()
    return _trailing_stop_manager
