"""Telegram notification provider."""

import httpx

from keryxflow.core.logging import get_logger
from keryxflow.notifications.base import BaseNotifier, NotificationMessage

logger = get_logger(__name__)


class TelegramNotifier(BaseNotifier):
    """Send notifications via Telegram Bot API.

    Requires a Telegram bot token and chat ID.
    Create a bot via @BotFather and get your chat ID via @userinfobot.
    """

    API_BASE = "https://api.telegram.org"

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        enabled: bool = True,
    ):
        """Initialize Telegram notifier.

        Args:
            bot_token: Telegram bot token from @BotFather
            chat_id: Target chat ID for messages
            enabled: Whether notifications are enabled
        """
        super().__init__(enabled=enabled)
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._client = httpx.AsyncClient(timeout=10.0)

    async def send(self, message: NotificationMessage) -> bool:
        """Send a notification via Telegram.

        Args:
            message: The notification to send

        Returns:
            True if sent successfully, False otherwise
        """
        if not self._enabled:
            return False

        if not self._bot_token or not self._chat_id:
            logger.warning("telegram_not_configured")
            return False

        url = f"{self.API_BASE}/bot{self._bot_token}/sendMessage"

        payload = {
            "chat_id": self._chat_id,
            "text": message.to_markdown(),
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }

        try:
            response = await self._client.post(url, json=payload)
            response.raise_for_status()

            result = response.json()
            if result.get("ok"):
                logger.debug(
                    "telegram_sent",
                    message_id=result.get("result", {}).get("message_id"),
                )
                return True

            logger.warning(
                "telegram_api_error",
                description=result.get("description"),
            )
            return False

        except httpx.TimeoutException:
            logger.error("telegram_timeout")
            return False
        except httpx.HTTPStatusError as e:
            logger.error("telegram_http_error", status=e.response.status_code)
            return False
        except Exception as e:
            logger.error("telegram_error", error=str(e))
            return False

    async def test_connection(self) -> bool:
        """Test connection to Telegram API.

        Returns:
            True if bot token is valid, False otherwise
        """
        if not self._bot_token:
            return False

        url = f"{self.API_BASE}/bot{self._bot_token}/getMe"

        try:
            response = await self._client.get(url)
            response.raise_for_status()

            result = response.json()
            if result.get("ok"):
                bot_name = result.get("result", {}).get("username", "unknown")
                logger.info("telegram_connected", bot=bot_name)
                return True

            return False

        except Exception as e:
            logger.error("telegram_test_failed", error=str(e))
            return False

    def get_name(self) -> str:
        """Get notifier name."""
        return "Telegram"

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()
