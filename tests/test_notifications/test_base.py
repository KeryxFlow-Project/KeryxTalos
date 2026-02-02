"""Tests for notification base classes."""

from datetime import UTC, datetime

from keryxflow.notifications.base import (
    NotificationLevel,
    NotificationMessage,
    NotificationType,
)


class TestNotificationLevel:
    """Tests for NotificationLevel enum."""

    def test_values(self):
        """Test enum values."""
        assert NotificationLevel.INFO.value == "info"
        assert NotificationLevel.SUCCESS.value == "success"
        assert NotificationLevel.WARNING.value == "warning"
        assert NotificationLevel.ERROR.value == "error"
        assert NotificationLevel.CRITICAL.value == "critical"


class TestNotificationType:
    """Tests for NotificationType enum."""

    def test_values(self):
        """Test enum values."""
        assert NotificationType.ORDER_FILLED.value == "order_filled"
        assert NotificationType.CIRCUIT_BREAKER.value == "circuit_breaker"
        assert NotificationType.DAILY_SUMMARY.value == "daily_summary"


class TestNotificationMessage:
    """Tests for NotificationMessage dataclass."""

    def test_create_basic(self):
        """Test creating basic message."""
        msg = NotificationMessage(
            title="Test Title",
            body="Test body content",
        )

        assert msg.title == "Test Title"
        assert msg.body == "Test body content"
        assert msg.level == NotificationLevel.INFO
        assert msg.notification_type is None

    def test_create_with_all_fields(self):
        """Test creating message with all fields."""
        msg = NotificationMessage(
            title="Order Filled",
            body="BTC order filled",
            level=NotificationLevel.SUCCESS,
            notification_type=NotificationType.ORDER_FILLED,
            metadata={"symbol": "BTC/USDT", "price": 50000},
        )

        assert msg.level == NotificationLevel.SUCCESS
        assert msg.notification_type == NotificationType.ORDER_FILLED
        assert msg.metadata["symbol"] == "BTC/USDT"

    def test_timestamp_auto_set(self):
        """Test timestamp is automatically set."""
        before = datetime.now(UTC)
        msg = NotificationMessage(title="Test", body="test")
        after = datetime.now(UTC)

        assert before <= msg.timestamp <= after

    def test_to_markdown(self):
        """Test markdown formatting."""
        msg = NotificationMessage(
            title="Alert",
            body="Something happened",
            level=NotificationLevel.WARNING,
            metadata={"key": "value"},
        )

        md = msg.to_markdown()

        assert "⚠️" in md  # warning emoji
        assert "**Alert**" in md
        assert "Something happened" in md
        assert "key" in md
        assert "`value`" in md

    def test_to_markdown_all_levels(self):
        """Test markdown emojis for all levels."""
        levels_emojis = {
            NotificationLevel.INFO: "ℹ️",
            NotificationLevel.SUCCESS: "✅",
            NotificationLevel.WARNING: "⚠️",
            NotificationLevel.ERROR: "❌",
            NotificationLevel.CRITICAL: "🚨",
        }

        for level, emoji in levels_emojis.items():
            msg = NotificationMessage(title="Test", body="test", level=level)
            assert emoji in msg.to_markdown()

    def test_to_plain_text(self):
        """Test plain text formatting."""
        msg = NotificationMessage(
            title="Alert",
            body="Something happened",
            level=NotificationLevel.ERROR,
            metadata={"key": "value"},
        )

        text = msg.to_plain_text()

        assert "[ERROR]" in text
        assert "Alert" in text
        assert "Something happened" in text
        assert "key: value" in text
