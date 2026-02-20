"""Tests for NotificationManager."""

import pytest

from keryxflow.core.events import Event, EventBus, EventType
from keryxflow.notifications.base import (
    BaseNotifier,
    NotificationLevel,
    NotificationMessage,
    NotificationType,
)
from keryxflow.notifications.manager import NotificationManager


class MockNotifier(BaseNotifier):
    """Mock notifier for testing."""

    def __init__(self, name: str = "Mock", enabled: bool = True, should_fail: bool = False):
        super().__init__(enabled=enabled)
        self._name = name
        self._should_fail = should_fail
        self.sent_messages: list[NotificationMessage] = []

    async def send(self, message: NotificationMessage) -> bool:
        if not self._enabled:
            return False
        if self._should_fail:
            return False
        self.sent_messages.append(message)
        return True

    async def test_connection(self) -> bool:
        return not self._should_fail

    def get_name(self) -> str:
        return self._name


class TestNotificationManagerInit:
    """Tests for NotificationManager initialization."""

    def test_init_empty(self):
        """Test initialization with no notifiers."""
        manager = NotificationManager()

        assert len(manager.notifiers) == 0

    def test_init_with_notifiers(self):
        """Test initialization with notifiers."""
        mock1 = MockNotifier("Mock1")
        mock2 = MockNotifier("Mock2")

        manager = NotificationManager()
        manager.add_notifier(mock1)
        manager.add_notifier(mock2)

        assert len(manager.notifiers) == 2


class TestNotificationManagerNotifiers:
    """Tests for notifiers property."""

    def test_notifiers_only_enabled(self):
        """Test that only enabled notifiers are returned."""
        mock1 = MockNotifier("Mock1", enabled=True)
        mock2 = MockNotifier("Mock2", enabled=False)

        manager = NotificationManager()
        manager.add_notifier(mock1)
        manager.add_notifier(mock2)

        assert len(manager.notifiers) == 1
        assert manager.notifiers[0].get_name() == "Mock1"


class TestNotificationManagerNotify:
    """Tests for notify method."""

    @pytest.mark.asyncio
    async def test_notify_sends_to_all(self):
        """Test that notify sends to all notifiers."""
        mock1 = MockNotifier("Mock1")
        mock2 = MockNotifier("Mock2")

        manager = NotificationManager()
        manager.add_notifier(mock1)
        manager.add_notifier(mock2)

        msg = NotificationMessage(title="Test", body="test body")
        results = await manager.notify(msg)

        assert results["Mock1"] is True
        assert results["Mock2"] is True
        assert len(mock1.sent_messages) == 1
        assert len(mock2.sent_messages) == 1

    @pytest.mark.asyncio
    async def test_notify_handles_failure(self):
        """Test that notify handles failures gracefully."""
        mock1 = MockNotifier("Mock1")
        mock2 = MockNotifier("Mock2", should_fail=True)

        manager = NotificationManager()
        manager.add_notifier(mock1)
        manager.add_notifier(mock2)

        msg = NotificationMessage(title="Test", body="test body")
        results = await manager.notify(msg)

        assert results["Mock1"] is True
        assert results["Mock2"] is False


class TestNotificationManagerOrderFilled:
    """Tests for notify_order_filled method."""

    @pytest.mark.asyncio
    async def test_notify_order_filled(self):
        """Test order filled notification."""
        mock = MockNotifier("Mock")
        manager = NotificationManager()
        manager.add_notifier(mock)

        await manager.notify_order_filled(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.1,
            price=50000.0,
        )

        assert len(mock.sent_messages) == 1
        msg = mock.sent_messages[0]
        assert "BTC/USDT" in msg.title
        assert "BUY" in msg.title
        assert msg.level == NotificationLevel.SUCCESS

    @pytest.mark.asyncio
    async def test_notify_order_filled_with_pnl(self):
        """Test order filled with PnL."""
        mock = MockNotifier("Mock")
        manager = NotificationManager()
        manager.add_notifier(mock)

        await manager.notify_order_filled(
            symbol="BTC/USDT",
            side="sell",
            quantity=0.1,
            price=51000.0,
            pnl=100.0,
        )

        msg = mock.sent_messages[0]
        assert "100" in msg.body
        assert "PnL" in str(msg.metadata)


class TestNotificationManagerCircuitBreaker:
    """Tests for notify_circuit_breaker method."""

    @pytest.mark.asyncio
    async def test_notify_circuit_breaker(self):
        """Test circuit breaker notification."""
        mock = MockNotifier("Mock")
        manager = NotificationManager()
        manager.add_notifier(mock)

        await manager.notify_circuit_breaker(
            reason="Daily loss limit",
            cooldown_minutes=30,
        )

        assert len(mock.sent_messages) == 1
        msg = mock.sent_messages[0]
        assert "Circuit Breaker" in msg.title
        assert msg.level == NotificationLevel.CRITICAL
        assert "Daily loss limit" in msg.body


class TestNotificationManagerDailySummary:
    """Tests for notify_daily_summary method."""

    @pytest.mark.asyncio
    async def test_notify_daily_summary_profit(self):
        """Test daily summary with profit."""
        mock = MockNotifier("Mock")
        manager = NotificationManager()
        manager.add_notifier(mock)

        await manager.notify_daily_summary(
            total_trades=10,
            winning_trades=7,
            total_pnl=500.0,
            win_rate=70.0,
        )

        msg = mock.sent_messages[0]
        assert "Daily Summary" in msg.title
        assert msg.level == NotificationLevel.SUCCESS

    @pytest.mark.asyncio
    async def test_notify_daily_summary_loss(self):
        """Test daily summary with loss."""
        mock = MockNotifier("Mock")
        manager = NotificationManager()
        manager.add_notifier(mock)

        await manager.notify_daily_summary(
            total_trades=10,
            winning_trades=3,
            total_pnl=-200.0,
            win_rate=30.0,
        )

        msg = mock.sent_messages[0]
        assert msg.level == NotificationLevel.WARNING


class TestNotificationManagerSystemStart:
    """Tests for notify_system_start method."""

    @pytest.mark.asyncio
    async def test_notify_system_start_paper(self):
        """Test system start in paper mode."""
        mock = MockNotifier("Mock")
        manager = NotificationManager()
        manager.add_notifier(mock)

        await manager.notify_system_start(
            mode="paper",
            symbols=["BTC/USDT", "ETH/USDT"],
        )

        msg = mock.sent_messages[0]
        assert "Started" in msg.title
        assert "PAPER" in msg.body

    @pytest.mark.asyncio
    async def test_notify_system_start_live(self):
        """Test system start in live mode."""
        mock = MockNotifier("Mock")
        manager = NotificationManager()
        manager.add_notifier(mock)

        await manager.notify_system_start(
            mode="live",
            symbols=["BTC/USDT"],
        )

        msg = mock.sent_messages[0]
        assert "LIVE" in msg.body


class TestNotificationManagerTestAll:
    """Tests for test_all method."""

    @pytest.mark.asyncio
    async def test_test_all(self):
        """Test all notifiers."""
        mock1 = MockNotifier("Mock1")
        mock2 = MockNotifier("Mock2", should_fail=True)

        manager = NotificationManager()
        manager.add_notifier(mock1)
        manager.add_notifier(mock2)

        results = await manager.test_all()

        assert results["Mock1"] is True
        assert results["Mock2"] is False


class TestNotificationManagerPositionOpened:
    """Tests for notify_position_opened method."""

    @pytest.mark.asyncio
    async def test_notify_position_opened_long(self):
        """Test position opened notification for long."""
        mock = MockNotifier("Mock")
        manager = NotificationManager()
        manager.add_notifier(mock)

        await manager.notify_position_opened(
            symbol="BTC/USDT",
            side="long",
            quantity=0.1,
            entry_price=50000.0,
        )

        assert len(mock.sent_messages) == 1
        msg = mock.sent_messages[0]
        assert "BTC/USDT" in msg.title
        assert "LONG" in msg.title
        assert msg.notification_type == NotificationType.POSITION_OPENED
        assert msg.level == NotificationLevel.SUCCESS

    @pytest.mark.asyncio
    async def test_notify_position_opened_short(self):
        """Test position opened notification for short."""
        mock = MockNotifier("Mock")
        manager = NotificationManager()
        manager.add_notifier(mock)

        await manager.notify_position_opened(
            symbol="ETH/USDT",
            side="short",
            quantity=1.0,
            entry_price=3000.0,
        )

        msg = mock.sent_messages[0]
        assert "SHORT" in msg.title


class TestNotificationManagerPositionClosed:
    """Tests for notify_position_closed method."""

    @pytest.mark.asyncio
    async def test_notify_position_closed_win(self):
        """Test position closed notification with profit."""
        mock = MockNotifier("Mock")
        manager = NotificationManager()
        manager.add_notifier(mock)

        await manager.notify_position_closed(
            symbol="BTC/USDT",
            side="long",
            quantity=0.1,
            entry_price=50000.0,
            exit_price=52000.0,
            pnl=200.0,
            pnl_pct=4.0,
        )

        assert len(mock.sent_messages) == 1
        msg = mock.sent_messages[0]
        assert "WIN" in msg.title
        assert msg.notification_type == NotificationType.POSITION_CLOSED
        assert msg.level == NotificationLevel.SUCCESS
        assert "200" in msg.body
        assert "+4.00%" in msg.body

    @pytest.mark.asyncio
    async def test_notify_position_closed_loss(self):
        """Test position closed notification with loss."""
        mock = MockNotifier("Mock")
        manager = NotificationManager()
        manager.add_notifier(mock)

        await manager.notify_position_closed(
            symbol="BTC/USDT",
            side="long",
            quantity=0.1,
            entry_price=50000.0,
            exit_price=48000.0,
            pnl=-200.0,
            pnl_pct=-4.0,
        )

        msg = mock.sent_messages[0]
        assert "LOSS" in msg.title
        assert msg.level == NotificationLevel.WARNING


class TestNotificationManagerEventBus:
    """Tests for event bus integration."""

    @pytest.mark.asyncio
    async def test_subscribe_to_events(self):
        """Test that subscribe_to_events registers all 5 event types."""
        event_bus = EventBus()
        mock = MockNotifier("Mock")
        manager = NotificationManager(event_bus=event_bus)
        manager.add_notifier(mock)

        manager.subscribe_to_events()

        assert EventType.ORDER_FILLED in event_bus._subscribers
        assert EventType.CIRCUIT_BREAKER_TRIGGERED in event_bus._subscribers
        assert EventType.PANIC_TRIGGERED in event_bus._subscribers
        assert EventType.POSITION_OPENED in event_bus._subscribers
        assert EventType.POSITION_CLOSED in event_bus._subscribers

    @pytest.mark.asyncio
    async def test_subscribe_idempotent(self):
        """Test that calling subscribe_to_events twice doesn't double-subscribe."""
        event_bus = EventBus()
        manager = NotificationManager(event_bus=event_bus)

        manager.subscribe_to_events()
        manager.subscribe_to_events()

        assert len(event_bus._subscribers.get(EventType.ORDER_FILLED, [])) == 1

    @pytest.mark.asyncio
    async def test_subscribe_no_event_bus(self):
        """Test that subscribe_to_events is a no-op without event bus."""
        manager = NotificationManager()
        manager.subscribe_to_events()
        assert not manager._subscribed

    @pytest.mark.asyncio
    async def test_handle_order_filled_via_event(self):
        """Test order filled handler via event bus dispatch."""
        event_bus = EventBus()
        mock = MockNotifier("Mock")
        manager = NotificationManager(event_bus=event_bus)
        manager.add_notifier(mock)
        manager.subscribe_to_events()

        event = Event(
            type=EventType.ORDER_FILLED,
            data={"symbol": "BTC/USDT", "side": "buy", "quantity": 0.1, "price": 50000.0},
        )
        await event_bus.publish_sync(event)

        assert len(mock.sent_messages) == 1
        assert "BTC/USDT" in mock.sent_messages[0].title

    @pytest.mark.asyncio
    async def test_handle_circuit_breaker_via_event(self):
        """Test circuit breaker handler via event bus dispatch."""
        event_bus = EventBus()
        mock = MockNotifier("Mock")
        manager = NotificationManager(event_bus=event_bus)
        manager.add_notifier(mock)
        manager.subscribe_to_events()

        event = Event(
            type=EventType.CIRCUIT_BREAKER_TRIGGERED,
            data={"reason": "Max drawdown", "cooldown_minutes": 60},
        )
        await event_bus.publish_sync(event)

        assert len(mock.sent_messages) == 1
        assert "Circuit Breaker" in mock.sent_messages[0].title

    @pytest.mark.asyncio
    async def test_handle_panic_via_event(self):
        """Test panic handler via event bus dispatch."""
        event_bus = EventBus()
        mock = MockNotifier("Mock")
        manager = NotificationManager(event_bus=event_bus)
        manager.add_notifier(mock)
        manager.subscribe_to_events()

        event = Event(type=EventType.PANIC_TRIGGERED, data={})
        await event_bus.publish_sync(event)

        assert len(mock.sent_messages) == 1
        assert "PANIC" in mock.sent_messages[0].title

    @pytest.mark.asyncio
    async def test_handle_position_opened_via_event(self):
        """Test position opened handler via event bus dispatch."""
        event_bus = EventBus()
        mock = MockNotifier("Mock")
        manager = NotificationManager(event_bus=event_bus)
        manager.add_notifier(mock)
        manager.subscribe_to_events()

        event = Event(
            type=EventType.POSITION_OPENED,
            data={"symbol": "ETH/USDT", "side": "long", "quantity": 1.0, "entry_price": 3000.0},
        )
        await event_bus.publish_sync(event)

        assert len(mock.sent_messages) == 1
        msg = mock.sent_messages[0]
        assert "ETH/USDT" in msg.title
        assert msg.notification_type == NotificationType.POSITION_OPENED

    @pytest.mark.asyncio
    async def test_handle_position_closed_via_event(self):
        """Test position closed handler via event bus dispatch."""
        event_bus = EventBus()
        mock = MockNotifier("Mock")
        manager = NotificationManager(event_bus=event_bus)
        manager.add_notifier(mock)
        manager.subscribe_to_events()

        event = Event(
            type=EventType.POSITION_CLOSED,
            data={
                "symbol": "BTC/USDT",
                "side": "long",
                "quantity": 0.5,
                "entry_price": 40000.0,
                "exit_price": 42000.0,
                "pnl": 1000.0,
                "pnl_pct": 5.0,
            },
        )
        await event_bus.publish_sync(event)

        assert len(mock.sent_messages) == 1
        msg = mock.sent_messages[0]
        assert "BTC/USDT" in msg.title
        assert msg.notification_type == NotificationType.POSITION_CLOSED
        assert "1,000" in msg.body

    @pytest.mark.asyncio
    async def test_handle_position_closed_defaults(self):
        """Test position closed handler with missing data uses defaults."""
        event_bus = EventBus()
        mock = MockNotifier("Mock")
        manager = NotificationManager(event_bus=event_bus)
        manager.add_notifier(mock)
        manager.subscribe_to_events()

        event = Event(type=EventType.POSITION_CLOSED, data={})
        await event_bus.publish_sync(event)

        assert len(mock.sent_messages) == 1
        msg = mock.sent_messages[0]
        assert "UNKNOWN" in msg.title


class TestNotificationManagerClose:
    """Tests for close method."""

    @pytest.mark.asyncio
    async def test_close(self):
        """Test closing manager."""
        mock = MockNotifier("Mock")
        manager = NotificationManager()
        manager.add_notifier(mock)

        # Should not raise
        await manager.close()
