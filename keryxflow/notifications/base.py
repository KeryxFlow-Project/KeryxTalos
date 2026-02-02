"""Base notifier interface and common types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class NotificationLevel(str, Enum):
    """Notification urgency level."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class NotificationType(str, Enum):
    """Type of notification."""

    ORDER_FILLED = "order_filled"
    ORDER_REJECTED = "order_rejected"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    CIRCUIT_BREAKER = "circuit_breaker"
    DAILY_SUMMARY = "daily_summary"
    SYSTEM_ERROR = "system_error"
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"


@dataclass
class NotificationMessage:
    """Structured notification message."""

    title: str
    body: str
    level: NotificationLevel = NotificationLevel.INFO
    notification_type: NotificationType | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict = field(default_factory=dict)

    def to_markdown(self) -> str:
        """Format message as markdown."""
        emoji = {
            NotificationLevel.INFO: "ℹ️",
            NotificationLevel.SUCCESS: "✅",
            NotificationLevel.WARNING: "⚠️",
            NotificationLevel.ERROR: "❌",
            NotificationLevel.CRITICAL: "🚨",
        }.get(self.level, "📢")

        lines = [
            f"{emoji} **{self.title}**",
            "",
            self.body,
        ]

        if self.metadata:
            lines.append("")
            for key, value in self.metadata.items():
                lines.append(f"• {key}: `{value}`")

        lines.append("")
        lines.append(f"_🕐 {self.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}_")

        return "\n".join(lines)

    def to_plain_text(self) -> str:
        """Format message as plain text."""
        lines = [
            f"[{self.level.value.upper()}] {self.title}",
            self.body,
        ]

        if self.metadata:
            for key, value in self.metadata.items():
                lines.append(f"  {key}: {value}")

        lines.append(f"  Time: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")

        return "\n".join(lines)


class BaseNotifier(ABC):
    """Abstract base class for notification providers."""

    def __init__(self, enabled: bool = True):
        """Initialize notifier.

        Args:
            enabled: Whether this notifier is enabled
        """
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        """Check if notifier is enabled."""
        return self._enabled

    @abstractmethod
    async def send(self, message: NotificationMessage) -> bool:
        """Send a notification message.

        Args:
            message: The notification to send

        Returns:
            True if sent successfully, False otherwise
        """
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test if the notification service is reachable.

        Returns:
            True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Get the name of this notifier."""
        pass
