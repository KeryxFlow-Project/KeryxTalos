"""Tests for NotificationManager."""

import pytest

from keryxflow.notifications.base import (
    BaseNotifier,
    NotificationLevel,
    NotificationMessage,
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
