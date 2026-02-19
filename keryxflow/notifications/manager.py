"""Notification manager - coordinates multiple notification providers."""

from typing import TYPE_CHECKING

from keryxflow.core.events import Event, EventBus, EventType
from keryxflow.core.logging import get_logger
from keryxflow.notifications.base import (
    BaseNotifier,
    NotificationLevel,
    NotificationMessage,
    NotificationType,
)

if TYPE_CHECKING:
    from keryxflow.notifications.discord import DiscordNotifier
    from keryxflow.notifications.telegram import TelegramNotifier

logger = get_logger(__name__)


class NotificationManager:
    """Manages multiple notification providers and event subscriptions.

    Subscribes to trading events and dispatches notifications
    to all configured providers.
    """

    def __init__(
        self,
        event_bus: EventBus | None = None,
        telegram: "TelegramNotifier | None" = None,
        discord: "DiscordNotifier | None" = None,
    ):
        """Initialize notification manager.

        Args:
            event_bus: Event bus for subscribing to events
            telegram: Telegram notifier instance
            discord: Discord notifier instance
        """
        self._event_bus = event_bus
        self._notifiers: list[BaseNotifier] = []

        if telegram and telegram.enabled:
            self._notifiers.append(telegram)
        if discord and discord.enabled:
            self._notifiers.append(discord)

        self._subscribed = False

    @property
    def notifiers(self) -> list[BaseNotifier]:
        """Get list of active notifiers."""
        return [n for n in self._notifiers if n.enabled]

    def add_notifier(self, notifier: BaseNotifier) -> None:
        """Add a notification provider.

        Args:
            notifier: Notifier to add
        """
        self._notifiers.append(notifier)

    async def notify(self, message: NotificationMessage) -> dict[str, bool]:
        """Send notification to all providers.

        Args:
            message: Notification message to send

        Returns:
            Dict mapping notifier name to success status
        """
        results = {}

        for notifier in self.notifiers:
            try:
                success = await notifier.send(message)
                results[notifier.get_name()] = success
            except Exception as e:
                logger.error(
                    "notification_failed",
                    notifier=notifier.get_name(),
                    error=str(e),
                )
                results[notifier.get_name()] = False

        return results

    async def notify_order_filled(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        pnl: float | None = None,
    ) -> None:
        """Send order filled notification.

        Args:
            symbol: Trading symbol
            side: Order side (buy/sell)
            quantity: Order quantity
            price: Fill price
            pnl: Realized PnL (for closing orders)
        """
        emoji = "🟢" if side == "buy" else "🔴"
        title = f"{emoji} Order Filled: {side.upper()} {symbol}"

        body = (
            f"Executed {side.upper()} order for {quantity} {symbol.split('/')[0]} @ ${price:,.2f}"
        )

        metadata = {
            "Symbol": symbol,
            "Side": side.upper(),
            "Quantity": f"{quantity:.8f}",
            "Price": f"${price:,.2f}",
        }

        if pnl is not None:
            pnl_emoji = "📈" if pnl >= 0 else "📉"
            metadata["PnL"] = f"{pnl_emoji} ${pnl:,.2f}"
            body += f"\nRealized PnL: ${pnl:,.2f}"

        message = NotificationMessage(
            title=title,
            body=body,
            level=NotificationLevel.SUCCESS,
            notification_type=NotificationType.ORDER_FILLED,
            metadata=metadata,
        )

        await self.notify(message)

    async def notify_circuit_breaker(self, reason: str, cooldown_minutes: int) -> None:
        """Send circuit breaker triggered notification.

        Args:
            reason: Reason for triggering
            cooldown_minutes: Cooldown period in minutes
        """
        message = NotificationMessage(
            title="🚨 Circuit Breaker Triggered",
            body=f"Trading has been automatically paused.\n\nReason: {reason}",
            level=NotificationLevel.CRITICAL,
            notification_type=NotificationType.CIRCUIT_BREAKER,
            metadata={
                "Reason": reason,
                "Cooldown": f"{cooldown_minutes} minutes",
                "Action": "Trading paused",
            },
        )

        await self.notify(message)

    async def notify_daily_summary(
        self,
        total_trades: int,
        winning_trades: int,
        total_pnl: float,
        win_rate: float,
    ) -> None:
        """Send daily trading summary.

        Args:
            total_trades: Total trades today
            winning_trades: Number of winning trades
            total_pnl: Total PnL for the day
            win_rate: Win rate percentage
        """
        pnl_emoji = "📈" if total_pnl >= 0 else "📉"
        title = f"📊 Daily Summary {pnl_emoji}"

        body = (
            f"Today's trading results:\n\n"
            f"• Total Trades: {total_trades}\n"
            f"• Winning Trades: {winning_trades}\n"
            f"• Win Rate: {win_rate:.1f}%\n"
            f"• Total PnL: ${total_pnl:,.2f}"
        )

        level = NotificationLevel.SUCCESS if total_pnl >= 0 else NotificationLevel.WARNING

        message = NotificationMessage(
            title=title,
            body=body,
            level=level,
            notification_type=NotificationType.DAILY_SUMMARY,
            metadata={
                "Trades": str(total_trades),
                "Win Rate": f"{win_rate:.1f}%",
                "PnL": f"${total_pnl:,.2f}",
            },
        )

        await self.notify(message)

    async def notify_system_start(self, mode: str, symbols: list[str]) -> None:
        """Send system start notification.

        Args:
            mode: Trading mode (paper/live)
            symbols: List of trading symbols
        """
        mode_emoji = "🧪" if mode == "paper" else "💰"

        message = NotificationMessage(
            title=f"{mode_emoji} KeryxFlow Started",
            body=f"Trading engine started in {mode.upper()} mode.",
            level=NotificationLevel.INFO,
            notification_type=NotificationType.SYSTEM_START,
            metadata={
                "Mode": mode.upper(),
                "Symbols": ", ".join(symbols),
            },
        )

        await self.notify(message)

    async def notify_system_error(self, error: str, component: str) -> None:
        """Send system error notification.

        Args:
            error: Error message
            component: Component that errored
        """
        message = NotificationMessage(
            title="❌ System Error",
            body=f"An error occurred in {component}:\n\n{error}",
            level=NotificationLevel.ERROR,
            notification_type=NotificationType.SYSTEM_ERROR,
            metadata={
                "Component": component,
            },
        )

        await self.notify(message)

    def subscribe_to_events(self) -> None:
        """Subscribe to relevant trading events."""
        if not self._event_bus or self._subscribed:
            return

        self._event_bus.subscribe(EventType.ORDER_FILLED, self._handle_order_filled)
        self._event_bus.subscribe(EventType.CIRCUIT_BREAKER_TRIGGERED, self._handle_circuit_breaker)
        self._event_bus.subscribe(EventType.PANIC_TRIGGERED, self._handle_panic)
        self._event_bus.subscribe(EventType.POSITION_OPENED, self._handle_position_opened)
        self._event_bus.subscribe(EventType.POSITION_CLOSED, self._handle_position_closed)

        self._subscribed = True
        logger.info("notification_manager_subscribed")

    async def _handle_order_filled(self, event: Event) -> None:
        """Handle order filled event."""
        data = event.data or {}
        await self.notify_order_filled(
            symbol=data.get("symbol", "UNKNOWN"),
            side=data.get("side", "buy"),
            quantity=data.get("quantity", 0.0),
            price=data.get("price", 0.0),
            pnl=data.get("pnl"),
        )

    async def _handle_circuit_breaker(self, event: Event) -> None:
        """Handle circuit breaker triggered event."""
        data = event.data or {}
        await self.notify_circuit_breaker(
            reason=data.get("reason", "Unknown"),
            cooldown_minutes=data.get("cooldown_minutes", 30),
        )

    async def _handle_panic(self, _event: Event) -> None:
        """Handle panic triggered event."""
        await self.notify(
            NotificationMessage(
                title="🆘 PANIC MODE ACTIVATED",
                body="Emergency shutdown triggered. All positions closed.",
                level=NotificationLevel.CRITICAL,
                notification_type=NotificationType.CIRCUIT_BREAKER,
            )
        )

    async def _handle_position_opened(self, event: Event) -> None:
        """Handle position opened event."""
        data = event.data or {}
        await self.notify_position_opened(
            symbol=data.get("symbol", "UNKNOWN"),
            side=data.get("side", "long"),
            quantity=data.get("quantity", 0.0),
            entry_price=data.get("entry_price", 0.0),
        )

    async def _handle_position_closed(self, event: Event) -> None:
        """Handle position closed event."""
        data = event.data or {}
        await self.notify_position_closed(
            symbol=data.get("symbol", "UNKNOWN"),
            side=data.get("side", "long"),
            quantity=data.get("quantity", 0.0),
            entry_price=data.get("entry_price", 0.0),
            exit_price=data.get("exit_price", 0.0),
            pnl=data.get("pnl", 0.0),
            pnl_pct=data.get("pnl_pct", 0.0),
        )

    async def test_all(self) -> dict[str, bool]:
        """Test all notification providers.

        Returns:
            Dict mapping notifier name to connection status
        """
        results = {}

        for notifier in self._notifiers:
            try:
                success = await notifier.test_connection()
                results[notifier.get_name()] = success
            except Exception as e:
                logger.error(
                    "notification_test_failed",
                    notifier=notifier.get_name(),
                    error=str(e),
                )
                results[notifier.get_name()] = False

        return results

    async def notify_position_opened(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
    ) -> None:
        """Send position opened notification.

        Args:
            symbol: Trading symbol
            side: Position side (long/short)
            quantity: Position quantity
            entry_price: Entry price
        """
        emoji = "🟢" if side == "long" else "🔴"
        title = f"{emoji} Position Opened: {side.upper()} {symbol}"

        body = f"Opened {side.upper()} position for {quantity} {symbol.split('/')[0]} @ ${entry_price:,.2f}"

        message = NotificationMessage(
            title=title,
            body=body,
            level=NotificationLevel.SUCCESS,
            notification_type=NotificationType.POSITION_OPENED,
            metadata={
                "Symbol": symbol,
                "Side": side.upper(),
                "Quantity": f"{quantity:.8f}",
                "Entry Price": f"${entry_price:,.2f}",
            },
        )

        await self.notify(message)

    async def notify_position_closed(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        exit_price: float,
        pnl: float,
        pnl_pct: float,
    ) -> None:
        """Send position closed notification.

        Args:
            symbol: Trading symbol
            side: Position side (long/short)
            quantity: Position quantity
            entry_price: Entry price
            exit_price: Exit price
            pnl: Realized PnL
            pnl_pct: PnL percentage
        """
        pnl_emoji = "📈" if pnl >= 0 else "📉"
        result = "WIN" if pnl >= 0 else "LOSS"
        title = f"{pnl_emoji} Position Closed: {result} {symbol}"

        body = (
            f"Closed {side.upper()} position for {quantity} {symbol.split('/')[0]}\n"
            f"Entry: ${entry_price:,.2f} → Exit: ${exit_price:,.2f}\n"
            f"PnL: ${pnl:,.2f} ({pnl_pct:+.2f}%)"
        )

        level = NotificationLevel.SUCCESS if pnl >= 0 else NotificationLevel.WARNING

        message = NotificationMessage(
            title=title,
            body=body,
            level=level,
            notification_type=NotificationType.POSITION_CLOSED,
            metadata={
                "Symbol": symbol,
                "Side": side.upper(),
                "Entry": f"${entry_price:,.2f}",
                "Exit": f"${exit_price:,.2f}",
                "PnL": f"${pnl:,.2f} ({pnl_pct:+.2f}%)",
            },
        )

        await self.notify(message)

    async def close(self) -> None:
        """Close all notifiers."""
        for notifier in self._notifiers:
            if hasattr(notifier, "close"):
                await notifier.close()


_notification_manager: NotificationManager | None = None


def get_notification_manager() -> NotificationManager:
    """Get the global NotificationManager singleton.

    Creates and configures the manager from settings on first call.

    Returns:
        The shared NotificationManager instance
    """
    global _notification_manager
    if _notification_manager is None:
        from keryxflow.config import get_settings
        from keryxflow.core.events import get_event_bus
        from keryxflow.notifications.discord import DiscordNotifier
        from keryxflow.notifications.telegram import TelegramNotifier

        settings = get_settings().notifications
        telegram = TelegramNotifier(
            bot_token=settings.telegram_token,
            chat_id=settings.telegram_chat_id,
            enabled=settings.telegram_enabled,
        )
        discord = DiscordNotifier(
            webhook_url=settings.discord_webhook,
            enabled=settings.discord_enabled,
        )
        _notification_manager = NotificationManager(
            event_bus=get_event_bus(),
            telegram=telegram,
            discord=discord,
        )
    return _notification_manager
