"""Discord notification provider via webhooks."""

import httpx

from keryxflow.core.logging import get_logger
from keryxflow.notifications.base import (
    BaseNotifier,
    NotificationLevel,
    NotificationMessage,
)

logger = get_logger(__name__)


class DiscordNotifier(BaseNotifier):
    """Send notifications via Discord webhook.

    Create a webhook in Discord: Server Settings > Integrations > Webhooks
    """

    def __init__(
        self,
        webhook_url: str,
        username: str = "KeryxFlow",
        enabled: bool = True,
    ):
        """Initialize Discord notifier.

        Args:
            webhook_url: Discord webhook URL
            username: Bot username to display
            enabled: Whether notifications are enabled
        """
        super().__init__(enabled=enabled)
        self._webhook_url = webhook_url
        self._username = username
        self._client = httpx.AsyncClient(timeout=10.0)

    def _get_embed_color(self, level: NotificationLevel) -> int:
        """Get Discord embed color for notification level.

        Args:
            level: Notification level

        Returns:
            Color as integer (Discord format)
        """
        colors = {
            NotificationLevel.INFO: 0x3498DB,  # Blue
            NotificationLevel.SUCCESS: 0x2ECC71,  # Green
            NotificationLevel.WARNING: 0xF39C12,  # Orange
            NotificationLevel.ERROR: 0xE74C3C,  # Red
            NotificationLevel.CRITICAL: 0x9B59B6,  # Purple
        }
        return colors.get(level, 0x95A5A6)  # Grey default

    async def send(self, message: NotificationMessage) -> bool:
        """Send a notification via Discord webhook.

        Args:
            message: The notification to send

        Returns:
            True if sent successfully, False otherwise
        """
        if not self._enabled:
            return False

        if not self._webhook_url:
            logger.warning("discord_not_configured")
            return False

        # Build Discord embed
        embed = {
            "title": message.title,
            "description": message.body,
            "color": self._get_embed_color(message.level),
            "timestamp": message.timestamp.isoformat(),
            "footer": {"text": "KeryxFlow Trading Engine"},
        }

        # Add metadata as fields
        if message.metadata:
            embed["fields"] = [
                {"name": k, "value": str(v), "inline": True} for k, v in message.metadata.items()
            ]

        payload = {
            "username": self._username,
            "embeds": [embed],
        }

        try:
            response = await self._client.post(self._webhook_url, json=payload)

            # Discord returns 204 No Content on success
            if response.status_code == 204:
                logger.debug("discord_sent", title=message.title)
                return True

            logger.warning(
                "discord_api_error",
                status=response.status_code,
                body=response.text[:200],
            )
            return False

        except httpx.TimeoutException:
            logger.error("discord_timeout")
            return False
        except httpx.HTTPStatusError as e:
            logger.error("discord_http_error", status=e.response.status_code)
            return False
        except Exception as e:
            logger.error("discord_error", error=str(e))
            return False

    async def test_connection(self) -> bool:
        """Test connection to Discord webhook.

        Note: Discord doesn't have a test endpoint for webhooks,
        so we just verify the URL format.

        Returns:
            True if webhook URL is valid format
        """
        if not self._webhook_url:
            return False

        # Basic URL format check
        if not self._webhook_url.startswith("https://discord.com/api/webhooks/"):
            logger.warning("discord_invalid_webhook_url")
            return False

        logger.info("discord_configured")
        return True

    def get_name(self) -> str:
        """Get notifier name."""
        return "Discord"

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()
