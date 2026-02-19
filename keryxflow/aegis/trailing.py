"""Trailing stop manager for dynamic stop-loss tracking."""

import asyncio
from dataclasses import dataclass, field
from typing import Any

from keryxflow.config import get_settings
from keryxflow.core.events import Event, EventType, get_event_bus
from keryxflow.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TrailingStopState:
    """Per-symbol trailing stop state."""

    entry_price: float
    highest_price: float
    current_stop: float
    breakeven_activated: bool = False


@dataclass
class TrailingStopManager:
    """
    Manages trailing stops for open positions.

    Tracks price movement per symbol and ratchets the stop-loss upward.
    Includes break-even logic: when unrealized profit reaches the
    breakeven trigger threshold, the stop moves to at least entry price.

    Emits events:
    - STOP_LOSS_TRAILED when the stop level moves up
    - STOP_LOSS_BREAKEVEN when the stop moves to entry price
    """

    trailing_stop_pct: float = 2.0
    breakeven_trigger_pct: float = 1.0
    _positions: dict[str, TrailingStopState] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Initialize event bus and load config."""
        self.event_bus = get_event_bus()
        settings = get_settings()
        self.trailing_stop_pct = settings.risk.trailing_stop_pct
        self.breakeven_trigger_pct = settings.risk.breakeven_trigger_pct

    def start_tracking(self, symbol: str, entry_price: float) -> None:
        """
        Begin tracking a trailing stop for a symbol.

        Args:
            symbol: Trading pair symbol
            entry_price: Position entry price
        """
        initial_stop = entry_price * (1 - self.trailing_stop_pct / 100)
        self._positions[symbol] = TrailingStopState(
            entry_price=entry_price,
            highest_price=entry_price,
            current_stop=initial_stop,
        )
        logger.info(
            "trailing_stop_started",
            symbol=symbol,
            entry_price=entry_price,
            initial_stop=initial_stop,
        )

    def update_price(self, symbol: str, price: float) -> None:
        """
        Update the current price and adjust the trailing stop.

        Args:
            symbol: Trading pair symbol
            price: Current market price
        """
        state = self._positions.get(symbol)
        if state is None:
            return

        # Check breakeven trigger
        if not state.breakeven_activated:
            breakeven_price = state.entry_price * (1 + self.breakeven_trigger_pct / 100)
            if price >= breakeven_price:
                state.breakeven_activated = True
                old_stop = state.current_stop
                state.current_stop = max(state.current_stop, state.entry_price)
                if state.current_stop > old_stop:
                    logger.info(
                        "trailing_stop_breakeven",
                        symbol=symbol,
                        new_stop=state.current_stop,
                    )
                    self._emit_event(
                        EventType.STOP_LOSS_BREAKEVEN,
                        symbol=symbol,
                        stop_level=state.current_stop,
                        entry_price=state.entry_price,
                        price=price,
                    )

        # Update highest price
        if price > state.highest_price:
            state.highest_price = price
            new_stop = state.highest_price * (1 - self.trailing_stop_pct / 100)

            if new_stop > state.current_stop:
                old_stop = state.current_stop
                state.current_stop = new_stop
                logger.info(
                    "trailing_stop_moved",
                    symbol=symbol,
                    old_stop=old_stop,
                    new_stop=new_stop,
                )
                self._emit_event(
                    EventType.STOP_LOSS_TRAILED,
                    symbol=symbol,
                    old_stop=old_stop,
                    new_stop=new_stop,
                    highest_price=state.highest_price,
                    price=price,
                )

    def get_stop_level(self, symbol: str) -> float | None:
        """
        Get the current stop level for a symbol.

        Args:
            symbol: Trading pair symbol

        Returns:
            Current stop level or None if not tracking
        """
        state = self._positions.get(symbol)
        return state.current_stop if state else None

    def should_trigger_stop(self, symbol: str, current_price: float) -> bool:
        """
        Check if the stop loss should be triggered.

        Args:
            symbol: Trading pair symbol
            current_price: Current market price

        Returns:
            True if price is at or below the stop level
        """
        state = self._positions.get(symbol)
        if state is None:
            return False
        return current_price <= state.current_stop

    def reset(self, symbol: str) -> None:
        """
        Clear trailing stop state for a symbol.

        Args:
            symbol: Trading pair symbol
        """
        if symbol in self._positions:
            del self._positions[symbol]
            logger.info("trailing_stop_reset", symbol=symbol)

    def _emit_event(self, event_type: EventType, **data: Any) -> None:
        """Emit an event via the event bus (fire-and-forget)."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.event_bus.publish_sync(Event(type=event_type, data=data)))
        except RuntimeError:
            pass  # No event loop running


# Global instance
_trailing_stop_manager: TrailingStopManager | None = None


def get_trailing_stop_manager() -> TrailingStopManager:
    """Get the global trailing stop manager instance."""
    global _trailing_stop_manager
    if _trailing_stop_manager is None:
        _trailing_stop_manager = TrailingStopManager()
    return _trailing_stop_manager
