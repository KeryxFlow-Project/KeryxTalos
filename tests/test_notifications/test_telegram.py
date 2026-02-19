"""Tests for Telegram notifier."""

from unittest.mock import AsyncMock, patch

import httpx
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


class TestTelegramNotifierSendHttp:
    """Tests for TelegramNotifier send with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_send_success(self):
        """Test successful send returns True."""
        notifier = TelegramNotifier(bot_token="test_token", chat_id="123456")

        mock_response = httpx.Response(
            200,
            json={"ok": True, "result": {"message_id": 42}},
            request=httpx.Request("POST", "https://api.telegram.org/bottest_token/sendMessage"),
        )

        with patch.object(
            notifier._client, "post", new_callable=AsyncMock, return_value=mock_response
        ):
            msg = NotificationMessage(title="Test", body="test body")
            result = await notifier.send(msg)

        assert result is True
        await notifier.close()

    @pytest.mark.asyncio
    async def test_send_api_error(self):
        """Test that Telegram API error returns False."""
        notifier = TelegramNotifier(bot_token="test_token", chat_id="123456")

        mock_response = httpx.Response(
            200,
            json={"ok": False, "description": "Bad Request"},
            request=httpx.Request("POST", "https://api.telegram.org/bottest_token/sendMessage"),
        )

        with patch.object(
            notifier._client, "post", new_callable=AsyncMock, return_value=mock_response
        ):
            msg = NotificationMessage(title="Test", body="test body")
            result = await notifier.send(msg)

        assert result is False
        await notifier.close()

    @pytest.mark.asyncio
    async def test_send_timeout(self):
        """Test that timeout returns False."""
        notifier = TelegramNotifier(bot_token="test_token", chat_id="123456")

        with patch.object(
            notifier._client,
            "post",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timeout"),
        ):
            msg = NotificationMessage(title="Test", body="test body")
            result = await notifier.send(msg)

        assert result is False
        await notifier.close()

    @pytest.mark.asyncio
    async def test_send_http_error(self):
        """Test that HTTP 500 raises and returns False."""
        notifier = TelegramNotifier(bot_token="test_token", chat_id="123456")

        mock_response = httpx.Response(
            500,
            request=httpx.Request("POST", "https://api.telegram.org/bottest_token/sendMessage"),
        )

        with patch.object(
            notifier._client,
            "post",
            new_callable=AsyncMock,
            side_effect=httpx.HTTPStatusError(
                "error", request=mock_response.request, response=mock_response
            ),
        ):
            msg = NotificationMessage(title="Test", body="test body")
            result = await notifier.send(msg)

        assert result is False
        await notifier.close()


class TestTelegramNotifierTestConnectionHttp:
    """Tests for TelegramNotifier test_connection with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_connection_success(self):
        """Test successful connection test."""
        notifier = TelegramNotifier(bot_token="test_token", chat_id="123456")

        mock_response = httpx.Response(
            200,
            json={"ok": True, "result": {"username": "test_bot"}},
            request=httpx.Request("GET", "https://api.telegram.org/bottest_token/getMe"),
        )

        with patch.object(
            notifier._client, "get", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await notifier.test_connection()

        assert result is True
        await notifier.close()

    @pytest.mark.asyncio
    async def test_connection_failure(self):
        """Test failed connection test."""
        notifier = TelegramNotifier(bot_token="test_token", chat_id="123456")

        with patch.object(
            notifier._client,
            "get",
            new_callable=AsyncMock,
            side_effect=Exception("Connection refused"),
        ):
            result = await notifier.test_connection()

        assert result is False
        await notifier.close()
