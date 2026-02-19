"""Tests for Discord notifier."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from keryxflow.notifications.base import NotificationLevel, NotificationMessage
from keryxflow.notifications.discord import DiscordNotifier


class TestDiscordNotifierInit:
    """Tests for DiscordNotifier initialization."""

    def test_init_default(self):
        """Test default initialization."""
        notifier = DiscordNotifier(
            webhook_url="https://discord.com/api/webhooks/123/abc",
        )

        assert notifier.enabled is True
        assert notifier._username == "KeryxFlow"

    def test_init_custom_username(self):
        """Test custom username."""
        notifier = DiscordNotifier(
            webhook_url="https://discord.com/api/webhooks/123/abc",
            username="CustomBot",
        )

        assert notifier._username == "CustomBot"

    def test_init_disabled(self):
        """Test disabled initialization."""
        notifier = DiscordNotifier(
            webhook_url="https://discord.com/api/webhooks/123/abc",
            enabled=False,
        )

        assert notifier.enabled is False

    def test_get_name(self):
        """Test get_name returns Discord."""
        notifier = DiscordNotifier("https://discord.com/api/webhooks/123/abc")
        assert notifier.get_name() == "Discord"


class TestDiscordNotifierEmbedColor:
    """Tests for Discord embed colors."""

    @pytest.fixture
    def notifier(self):
        """Create Discord notifier."""
        return DiscordNotifier("https://discord.com/api/webhooks/123/abc")

    def test_info_color(self, notifier):
        """Test info level color."""
        color = notifier._get_embed_color(NotificationLevel.INFO)
        assert color == 0x3498DB  # Blue

    def test_success_color(self, notifier):
        """Test success level color."""
        color = notifier._get_embed_color(NotificationLevel.SUCCESS)
        assert color == 0x2ECC71  # Green

    def test_warning_color(self, notifier):
        """Test warning level color."""
        color = notifier._get_embed_color(NotificationLevel.WARNING)
        assert color == 0xF39C12  # Orange

    def test_error_color(self, notifier):
        """Test error level color."""
        color = notifier._get_embed_color(NotificationLevel.ERROR)
        assert color == 0xE74C3C  # Red

    def test_critical_color(self, notifier):
        """Test critical level color."""
        color = notifier._get_embed_color(NotificationLevel.CRITICAL)
        assert color == 0x9B59B6  # Purple


class TestDiscordNotifierSend:
    """Tests for DiscordNotifier send method."""

    @pytest.mark.asyncio
    async def test_send_disabled_returns_false(self):
        """Test that disabled notifier returns False."""
        notifier = DiscordNotifier(
            webhook_url="https://discord.com/api/webhooks/123/abc",
            enabled=False,
        )

        msg = NotificationMessage(title="Test", body="test")
        result = await notifier.send(msg)

        assert result is False
        await notifier.close()

    @pytest.mark.asyncio
    async def test_send_no_webhook_returns_false(self):
        """Test that missing webhook returns False."""
        notifier = DiscordNotifier(webhook_url="")

        msg = NotificationMessage(title="Test", body="test")
        result = await notifier.send(msg)

        assert result is False
        await notifier.close()


class TestDiscordNotifierTestConnection:
    """Tests for DiscordNotifier test_connection method."""

    @pytest.mark.asyncio
    async def test_no_webhook_returns_false(self):
        """Test that missing webhook returns False."""
        notifier = DiscordNotifier(webhook_url="")

        result = await notifier.test_connection()

        assert result is False
        await notifier.close()

    @pytest.mark.asyncio
    async def test_invalid_webhook_returns_false(self):
        """Test that invalid webhook URL returns False."""
        notifier = DiscordNotifier(webhook_url="https://example.com/webhook")

        result = await notifier.test_connection()

        assert result is False
        await notifier.close()

    @pytest.mark.asyncio
    async def test_valid_format_returns_true(self):
        """Test that valid format webhook URL returns True."""
        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/123/abc")

        result = await notifier.test_connection()

        assert result is True
        await notifier.close()


class TestDiscordNotifierSendHttp:
    """Tests for DiscordNotifier send with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_send_success(self):
        """Test successful send returns True on HTTP 204."""
        notifier = DiscordNotifier(
            webhook_url="https://discord.com/api/webhooks/123/abc",
        )

        mock_response = httpx.Response(
            204, request=httpx.Request("POST", "https://discord.com/api/webhooks/123/abc")
        )

        with patch.object(
            notifier._client, "post", new_callable=AsyncMock, return_value=mock_response
        ):
            msg = NotificationMessage(
                title="Test", body="test body", level=NotificationLevel.SUCCESS
            )
            result = await notifier.send(msg)

        assert result is True
        await notifier.close()

    @pytest.mark.asyncio
    async def test_send_server_error(self):
        """Test that HTTP 500 returns False."""
        notifier = DiscordNotifier(
            webhook_url="https://discord.com/api/webhooks/123/abc",
        )

        mock_response = httpx.Response(
            500,
            text="Internal Server Error",
            request=httpx.Request("POST", "https://discord.com/api/webhooks/123/abc"),
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
        notifier = DiscordNotifier(
            webhook_url="https://discord.com/api/webhooks/123/abc",
        )

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
    async def test_send_with_metadata(self):
        """Test that metadata is included as embed fields."""
        notifier = DiscordNotifier(
            webhook_url="https://discord.com/api/webhooks/123/abc",
        )

        mock_response = httpx.Response(
            204, request=httpx.Request("POST", "https://discord.com/api/webhooks/123/abc")
        )
        mock_post = AsyncMock(return_value=mock_response)

        with patch.object(notifier._client, "post", mock_post):
            msg = NotificationMessage(
                title="Order",
                body="filled",
                metadata={"Symbol": "BTC/USDT", "Price": "$50,000"},
            )
            await notifier.send(msg)

        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        fields = payload["embeds"][0]["fields"]
        assert len(fields) == 2
        assert fields[0]["name"] == "Symbol"
        await notifier.close()
