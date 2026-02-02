"""Main TUI application using Textual."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header

from keryxflow import __version__
from keryxflow.config import get_settings
from keryxflow.core.events import EventBus, get_event_bus
from keryxflow.core.logging import get_logger
from keryxflow.hermes.widgets.aegis import AegisWidget
from keryxflow.hermes.widgets.chart import ChartWidget
from keryxflow.hermes.widgets.help import HelpModal
from keryxflow.hermes.widgets.logs import LogsWidget
from keryxflow.hermes.widgets.oracle import OracleWidget
from keryxflow.hermes.widgets.positions import PositionsWidget
from keryxflow.hermes.widgets.stats import StatsWidget

logger = get_logger(__name__)


class KeryxFlowApp(App):
    """KeryxFlow Terminal User Interface."""

    TITLE = f"KeryxFlow v{__version__}"
    SUB_TITLE = "Your keys, your trades, your code."
    CSS_PATH = "theme.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("p", "panic", "Panic", priority=True),
        Binding("space", "toggle_pause", "Pause/Resume"),
        Binding("question_mark", "show_help", "Help"),
        Binding("l", "toggle_logs", "Toggle Logs"),
        Binding("s", "cycle_symbol", "Next Symbol"),
    ]

    def __init__(self, event_bus: EventBus | None = None) -> None:
        """Initialize the app."""
        super().__init__()
        self.settings = get_settings()
        self.event_bus = event_bus or get_event_bus()
        self._paused = False
        self._current_symbol_index = 0
        self._symbols = self.settings.system.symbols

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header(show_clock=True)

        with Container(id="main-container"):
            with Horizontal(id="top-row"):
                with Vertical(id="left-column"):
                    yield ChartWidget(id="chart")
                    yield OracleWidget(id="oracle")

                with Vertical(id="right-column"):
                    yield PositionsWidget(id="positions")
                    yield AegisWidget(id="aegis")
                    yield StatsWidget(id="stats")

            yield LogsWidget(id="logs")

        yield Footer()

    async def on_mount(self) -> None:
        """Called when the app is mounted."""
        logger.info("tui_started", version=__version__)

        # Subscribe to events
        await self.event_bus.subscribe("price.update", self._on_price_update)
        await self.event_bus.subscribe("oracle.signal_generated", self._on_signal)
        await self.event_bus.subscribe("aegis.circuit_tripped", self._on_circuit_trip)
        await self.event_bus.subscribe("trade.executed", self._on_trade)

        # Initial data load
        await self._refresh_all()

    async def _refresh_all(self) -> None:
        """Refresh all widgets with current data."""
        chart = self.query_one("#chart", ChartWidget)
        chart.symbol = self.current_symbol
        await chart.refresh_data()

        positions = self.query_one("#positions", PositionsWidget)
        await positions.refresh_data()

        aegis = self.query_one("#aegis", AegisWidget)
        await aegis.refresh_data()

        stats = self.query_one("#stats", StatsWidget)
        await stats.refresh_data()

    @property
    def current_symbol(self) -> str:
        """Get the currently selected symbol."""
        return self._symbols[self._current_symbol_index]

    async def _on_price_update(self, data: dict) -> None:
        """Handle price update events."""
        if self._paused:
            return

        chart = self.query_one("#chart", ChartWidget)
        if data.get("symbol") == self.current_symbol:
            chart.update_price(data.get("price", 0.0))

        positions = self.query_one("#positions", PositionsWidget)
        await positions.update_prices(data)

    async def _on_signal(self, data: dict) -> None:
        """Handle signal generated events."""
        if self._paused:
            return

        oracle = self.query_one("#oracle", OracleWidget)
        oracle.update_signal(data)

        logs = self.query_one("#logs", LogsWidget)
        logs.add_entry(f"Signal: {data.get('signal_type', 'unknown')} @ {data.get('symbol', '')}")

    async def _on_circuit_trip(self, data: dict) -> None:
        """Handle circuit breaker trip events."""
        aegis = self.query_one("#aegis", AegisWidget)
        aegis.set_tripped(data.get("reason", "Unknown"))

        logs = self.query_one("#logs", LogsWidget)
        logs.add_entry(f"CIRCUIT BREAKER: {data.get('reason', 'Trading paused')}", level="warning")

        self.notify("Circuit Breaker Tripped!", severity="warning", timeout=10)

    async def _on_trade(self, data: dict) -> None:
        """Handle trade executed events."""
        logs = self.query_one("#logs", LogsWidget)
        side = data.get("side", "").upper()
        symbol = data.get("symbol", "")
        quantity = data.get("quantity", 0)
        price = data.get("price", 0)
        logs.add_entry(f"{side} {quantity} {symbol} @ ${price:,.2f}")

        # Refresh positions and stats
        positions = self.query_one("#positions", PositionsWidget)
        await positions.refresh_data()

        stats = self.query_one("#stats", StatsWidget)
        await stats.refresh_data()

    def action_quit(self) -> None:
        """Quit the application."""
        logger.info("tui_quit_requested")
        self.exit()

    async def action_panic(self) -> None:
        """Panic button - close all positions."""
        logs = self.query_one("#logs", LogsWidget)
        logs.add_entry("PANIC MODE ACTIVATED - Closing all positions!", level="error")

        await self.event_bus.publish("panic.requested", {})

        self.notify("Panic Mode - Closing all positions!", severity="error", timeout=5)

    def action_toggle_pause(self) -> None:
        """Toggle pause/resume trading."""
        self._paused = not self._paused

        logs = self.query_one("#logs", LogsWidget)
        if self._paused:
            logs.add_entry("Trading PAUSED", level="warning")
            self.notify("Trading Paused", severity="warning")
        else:
            logs.add_entry("Trading RESUMED", level="info")
            self.notify("Trading Resumed", severity="information")

    def action_show_help(self) -> None:
        """Show help modal."""
        self.push_screen(HelpModal())

    def action_toggle_logs(self) -> None:
        """Toggle logs panel visibility."""
        logs = self.query_one("#logs", LogsWidget)
        logs.toggle_class("hidden")

    async def action_cycle_symbol(self) -> None:
        """Cycle through available symbols."""
        self._current_symbol_index = (self._current_symbol_index + 1) % len(self._symbols)

        chart = self.query_one("#chart", ChartWidget)
        chart.symbol = self.current_symbol
        await chart.refresh_data()

        logs = self.query_one("#logs", LogsWidget)
        logs.add_entry(f"Switched to {self.current_symbol}")

        self.notify(f"Symbol: {self.current_symbol}")


def run_app() -> None:
    """Run the KeryxFlow TUI application."""
    app = KeryxFlowApp()
    app.run()


if __name__ == "__main__":
    run_app()
