"""Event bus for async pub/sub communication between modules."""

import asyncio
import contextlib
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from keryxflow.core.logging import get_logger

logger = get_logger(__name__)


class EventType(str, Enum):
    """Types of events in the system."""

    # Price events
    PRICE_UPDATE = "price_update"
    OHLCV_UPDATE = "ohlcv_update"

    # Signal events
    SIGNAL_GENERATED = "signal_generated"
    SIGNAL_VALIDATED = "signal_validated"
    SIGNAL_REJECTED = "signal_rejected"

    # Order events
    ORDER_REQUESTED = "order_requested"
    ORDER_APPROVED = "order_approved"
    ORDER_REJECTED = "order_rejected"
    ORDER_SUBMITTED = "order_submitted"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"

    # Position events
    POSITION_OPENED = "position_opened"
    POSITION_UPDATED = "position_updated"
    POSITION_CLOSED = "position_closed"

    # Risk events
    RISK_ALERT = "risk_alert"
    CIRCUIT_BREAKER_TRIGGERED = "circuit_breaker_triggered"
    DRAWDOWN_WARNING = "drawdown_warning"

    # System events
    SYSTEM_STARTED = "system_started"
    SYSTEM_STOPPED = "system_stopped"
    SYSTEM_PAUSED = "system_paused"
    SYSTEM_RESUMED = "system_resumed"
    PANIC_TRIGGERED = "panic_triggered"

    # LLM events
    LLM_ANALYSIS_STARTED = "llm_analysis_started"
    LLM_ANALYSIS_COMPLETED = "llm_analysis_completed"
    LLM_ANALYSIS_FAILED = "llm_analysis_failed"

    # News events
    NEWS_FETCHED = "news_fetched"

    # Agent events
    AGENT_CYCLE_STARTED = "agent_cycle_started"
    AGENT_CYCLE_COMPLETED = "agent_cycle_completed"
    AGENT_CYCLE_FAILED = "agent_cycle_failed"
    SESSION_STATE_CHANGED = "session_state_changed"


@dataclass
class Event:
    """Base event class."""

    type: EventType
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Ensure type is EventType."""
        if isinstance(self.type, str):
            self.type = EventType(self.type)


# Type alias for event handlers
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """
    Async event bus for publish/subscribe pattern.

    Usage:
        bus = EventBus()

        # Subscribe to events
        async def on_price_update(event: Event):
            print(f"Price updated: {event.data}")

        bus.subscribe(EventType.PRICE_UPDATE, on_price_update)

        # Publish events
        await bus.publish(Event(
            type=EventType.PRICE_UPDATE,
            data={"symbol": "BTC/USDT", "price": 67000.0}
        ))
    """

    def __init__(self, max_queue_size: int = 1000):
        """
        Initialize the event bus.

        Args:
            max_queue_size: Maximum number of events in the queue
        """
        self._subscribers: dict[EventType, list[EventHandler]] = {}
        self._queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=max_queue_size)
        self._running = False
        self._processor_task: asyncio.Task | None = None

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """
        Subscribe to an event type.

        Args:
            event_type: The type of event to subscribe to
            handler: Async function to handle the event
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []

        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)
            logger.debug("handler_subscribed", event_type=event_type.value)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """
        Unsubscribe from an event type.

        Args:
            event_type: The type of event to unsubscribe from
            handler: The handler to remove
        """
        if event_type in self._subscribers and handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)
            logger.debug("handler_unsubscribed", event_type=event_type.value)

    async def publish(self, event: Event) -> None:
        """
        Publish an event to all subscribers.

        Args:
            event: The event to publish
        """
        try:
            await self._queue.put(event)
            logger.debug(
                "event_published",
                event_type=event.type.value,
                queue_size=self._queue.qsize(),
            )
        except asyncio.QueueFull:
            logger.warning("event_queue_full", event_type=event.type.value)

    async def publish_sync(self, event: Event) -> None:
        """
        Publish an event and wait for all handlers to complete.

        Args:
            event: The event to publish
        """
        await self._dispatch(event)

    async def _dispatch(self, event: Event) -> None:
        """
        Dispatch an event to all subscribers.

        Args:
            event: The event to dispatch
        """
        handlers = self._subscribers.get(event.type, [])

        if not handlers:
            logger.debug("no_handlers", event_type=event.type.value)
            return

        # Run all handlers concurrently
        tasks = [self._safe_call(handler, event) for handler in handlers]
        await asyncio.gather(*tasks)

    async def _safe_call(self, handler: EventHandler, event: Event) -> None:
        """
        Safely call a handler, catching exceptions.

        Args:
            handler: The handler to call
            event: The event to pass to the handler
        """
        try:
            await handler(event)
        except Exception as e:
            logger.error(
                "handler_error",
                event_type=event.type.value,
                handler=handler.__name__,
                error=str(e),
            )

    async def _process_events(self) -> None:
        """Process events from the queue."""
        while self._running:
            try:
                # Wait for event with timeout to allow checking _running flag
                event = await asyncio.wait_for(self._queue.get(), timeout=0.1)
                await self._dispatch(event)
                self._queue.task_done()
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("event_processor_error", error=str(e))

    async def start(self) -> None:
        """Start the event processor."""
        if self._running:
            return

        self._running = True
        self._processor_task = asyncio.create_task(self._process_events())
        logger.info("event_bus_started")

    async def stop(self) -> None:
        """Stop the event processor."""
        if not self._running:
            return

        self._running = False

        if self._processor_task:
            self._processor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._processor_task

        logger.info("event_bus_stopped")

    @property
    def is_running(self) -> bool:
        """Check if the event bus is running."""
        return self._running

    @property
    def queue_size(self) -> int:
        """Get the current queue size."""
        return self._queue.qsize()


# Global event bus instance
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


# Convenience functions for creating common events
def price_update_event(symbol: str, price: float, volume: float | None = None) -> Event:
    """Create a price update event."""
    return Event(
        type=EventType.PRICE_UPDATE,
        data={"symbol": symbol, "price": price, "volume": volume},
    )


def signal_event(
    symbol: str,
    direction: str,
    strength: float,
    source: str,
    context: str | None = None,
) -> Event:
    """Create a signal generated event."""
    return Event(
        type=EventType.SIGNAL_GENERATED,
        data={
            "symbol": symbol,
            "direction": direction,
            "strength": strength,
            "source": source,
            "context": context,
        },
    )


def order_event(
    event_type: EventType,
    symbol: str,
    side: str,
    quantity: float,
    price: float,
    order_id: str | None = None,
    reason: str | None = None,
) -> Event:
    """Create an order-related event."""
    return Event(
        type=event_type,
        data={
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "order_id": order_id,
            "reason": reason,
        },
    )


def risk_alert_event(
    alert_type: str,
    message: str,
    current_value: float,
    threshold: float,
) -> Event:
    """Create a risk alert event."""
    return Event(
        type=EventType.RISK_ALERT,
        data={
            "alert_type": alert_type,
            "message": message,
            "current_value": current_value,
            "threshold": threshold,
        },
    )


def system_event(event_type: EventType, message: str | None = None) -> Event:
    """Create a system event."""
    return Event(
        type=event_type,
        data={"message": message} if message else {},
    )
