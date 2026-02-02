"""Tests for Telegram notifier."""

import pytest

from keryxflow.notifications.base import NotificationMessage
from keryxflow.notifications.telegram import TelegramNotifier


class TestTelegramNotifierInit:
    """Tests for TelegramNotifier initialization."""

    def test_init_default(self):
        """Test default initialization."""
        notifier = TelegramNotifier(
            bot_token="test_token",
            chat_id="123456",
        )

        assert notifier.enabled is True
        assert notifier._bot_token == "test_token"
        assert notifier._chat_id == "123456"

    def test_init_disabled(self):
        """Test disabled initialization."""
        notifier = TelegramNotifier(
            bot_token="test_token",
            chat_id="123456",
            enabled=False,
        )

        assert notifier.enabled is False

    def test_get_name(self):
        """Test get_name returns Telegram."""
        notifier = TelegramNotifier("token", "chat")
        assert notifier.get_name() == "Telegram"


class TestTelegramNotifierSend:
    """Tests for TelegramNotifier send method."""

    @pytest.mark.asyncio
    async def test_send_disabled_returns_false(self):
        """Test that disabled notifier returns False."""
        notifier = TelegramNotifier(
            bot_token="token",
            chat_id="chat",
            enabled=False,
        )

        msg = NotificationMessage(title="Test", body="test")
        result = await notifier.send(msg)

        assert result is False
        await notifier.close()

    @pytest.mark.asyncio
    async def test_send_no_token_returns_false(self):
        """Test that missing token returns False."""
        notifier = TelegramNotifier(
            bot_token="",
            chat_id="chat",
        )

        msg = NotificationMessage(title="Test", body="test")
        result = await notifier.send(msg)

        assert result is False
        await notifier.close()

    @pytest.mark.asyncio
    async def test_send_no_chat_id_returns_false(self):
        """Test that missing chat_id returns False."""
        notifier = TelegramNotifier(
            bot_token="token",
            chat_id="",
        )

        msg = NotificationMessage(title="Test", body="test")
        result = await notifier.send(msg)

        assert result is False
        await notifier.close()


class TestTelegramNotifierTestConnection:
    """Tests for TelegramNotifier test_connection method."""

    @pytest.mark.asyncio
    async def test_no_token_returns_false(self):
        """Test that missing token returns False."""
        notifier = TelegramNotifier(bot_token="", chat_id="chat")

        result = await notifier.test_connection()

        assert result is False
        await notifier.close()
