"""Tests for Discord notifier."""

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
        notifier = DiscordNotifier(
            webhook_url="https://discord.com/api/webhooks/123/abc"
        )

        result = await notifier.test_connection()

        assert result is True
        await notifier.close()
