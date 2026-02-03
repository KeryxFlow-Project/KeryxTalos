"""Main TUI application using Textual."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header

from keryxflow import __version__
from keryxflow.config import get_settings
from keryxflow.core.engine import TradingEngine
from keryxflow.core.events import Event, EventBus, EventType, get_event_bus
from keryxflow.core.logging import get_logger
from keryxflow.exchange.client import ExchangeClient
from keryxflow.exchange.paper import PaperTradingEngine
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

    def __init__(
        self,
        event_bus: EventBus | None = None,
        exchange_client: ExchangeClient | None = None,
        paper_engine: PaperTradingEngine | None = None,
        trading_engine: TradingEngine | None = None,
    ) -> None:
        """Initialize the app."""
        super().__init__()
        self.settings = get_settings()
        self.event_bus = event_bus or get_event_bus()
        self.exchange_client = exchange_client
        self.paper_engine = paper_engine
        self.trading_engine = trading_engine
        self._paused = False
        self._current_symbol_index = 0
        self._symbols = self.settings.system.symbols
        self._price_timer = None

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

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        logger.info("tui_started", version=__version__)

        # Subscribe to events
        self.event_bus.subscribe(EventType.PRICE_UPDATE, self._on_price_update)
        self.event_bus.subscribe(EventType.SIGNAL_GENERATED, self._on_signal)
        self.event_bus.subscribe(EventType.CIRCUIT_BREAKER_TRIGGERED, self._on_circuit_trip)
        self.event_bus.subscribe(EventType.ORDER_FILLED, self._on_trade)
        self.event_bus.subscribe(EventType.ORDER_APPROVED, self._on_order_approved)
        self.event_bus.subscribe(EventType.ORDER_REJECTED, self._on_order_rejected)

        # Log startup
        try:
            logs = self.query_one("#logs", LogsWidget)
            logs.add_entry("KeryxFlow starting...", level="info")
        except Exception:
            pass

        # Initialize directly (skip splash for now)
        self.run_worker(self._initialize_after_splash)

    async def _initialize_after_splash(self) -> None:
        """Async initialization after splash screen."""
        try:
            self._log_msg("Starting initialization...")

            # Connect widgets
            self._log_msg("Connecting widgets...")
            if self.paper_engine:
                self._connect_widgets()
            else:
                self._log_msg(
                    f"No client/paper: client={self.exchange_client is not None}, "
                    f"paper={self.paper_engine is not None}"
                )

            # Start price feed timer
            self._start_price_feed()

        except Exception as e:
            import traceback
            self._log_msg(f"ERROR: {e}")
            self._log_msg(traceback.format_exc()[:200])

    def _log_msg(self, msg: str) -> None:
        """Log a message to the activity widget."""
        try:
            logs = self.query_one("#logs", LogsWidget)
            logs.add_entry(msg, level="info")
        except Exception:
            pass

    def _connect_widgets(self) -> None:
        """Connect widgets to engines."""
        if self.trading_engine:
            # Connect aegis widget to risk manager
            aegis = self.query_one("#aegis", AegisWidget)
            aegis.set_risk_manager(self.trading_engine.risk)
            self._log_msg("Connected AEGIS to risk manager")

        if self.paper_engine:
            # Connect positions widget to paper engine
            positions = self.query_one("#positions", PositionsWidget)
            positions.set_paper_engine(self.paper_engine)

        self._log_msg("Widgets connected")

    def _start_price_feed(self) -> None:
        """Start the price feed timer (called from main thread)."""
        self._log_msg("Starting price feed...")
        if self.exchange_client:
            # Start the price loop as a worker
            self._log_msg("Starting price loop worker...")
            self.run_worker(self._price_loop, exclusive=True)
        else:
            self._log_msg("No exchange client for price feed!")

    async def _price_loop(self) -> None:
        """Background worker for fetching prices."""
        import asyncio

        self._log_msg("Price loop started!")
        analysis_counter = 0

        while True:
            if self._paused:
                await asyncio.sleep(1)
                continue

            await self._fetch_prices_once()

            # Run analysis every 3 iterations (~12 seconds)
            analysis_counter += 1
            if analysis_counter >= 3 and self.trading_engine:
                analysis_counter = 0
                await self._update_oracle()

            await asyncio.sleep(self.settings.hermes.refresh_rate)

    async def _fetch_prices_once(self) -> None:
        """Fetch prices once and update widgets."""
        import asyncio

        import ccxt

        for symbol in self._symbols:
            try:
                # Use sync ccxt in thread to avoid event loop conflicts
                def fetch_sync():
                    client = ccxt.binance({"enableRateLimit": True})
                    return client.fetch_ticker(symbol)

                ticker = await asyncio.to_thread(fetch_sync)
                price = ticker["last"]
                self._log_msg(f"{symbol}: ${price:,.2f}")

                # Update paper engine
                if self.paper_engine:
                    self.paper_engine.update_price(symbol, price)

                # Update chart directly if it's the current symbol
                if symbol == self.current_symbol:
                    try:
                        chart = self.query_one("#chart", ChartWidget)
                        chart.update_price(price)
                    except Exception as chart_err:
                        logger.warning("chart_update_error", error=str(chart_err))

                # Publish to event bus for trading engine
                await self.event_bus.publish(
                    Event(
                        type=EventType.PRICE_UPDATE,
                        data={
                            "symbol": symbol,
                            "price": price,
                            "bid": ticker.get("bid"),
                            "ask": ticker.get("ask"),
                            "volume": ticker.get("baseVolume", 0),
                        },
                    )
                )

            except Exception as e:
                logger.warning("price_fetch_error", symbol=symbol, error=str(e))
                self._log_msg(f"Error {symbol}: {e}")

    async def _update_oracle(self) -> None:
        """Update Oracle widget with latest signal from trading engine."""
        import asyncio

        if not self.trading_engine:
            return

        try:
            symbol = self.current_symbol

            # Get OHLCV data from engine buffer
            ohlcv = self.trading_engine._ohlcv_buffer.get_ohlcv(symbol)
            if ohlcv is None or len(ohlcv) < 50:
                return

            current_price = ohlcv["close"].iloc[-1]

            # Generate signal using engine's signal generator (in thread to avoid blocking)
            def generate_signal_sync():
                import asyncio
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(
                        self.trading_engine.signals.generate_signal(
                            symbol=symbol,
                            ohlcv=ohlcv,
                            current_price=current_price,
                            include_news=False,
                            include_llm=False,
                        )
                    )
                finally:
                    loop.close()

            signal = await asyncio.to_thread(generate_signal_sync)

            # Update Oracle widget
            oracle = self.query_one("#oracle", OracleWidget)
            oracle.update_signal(signal.to_dict())

            # Log actionable signals
            if signal.signal_type.value in ("long", "short"):
                self._log_msg(f"Signal: {signal.signal_type.value.upper()} {symbol} ({signal.confidence:.0%})")

        except Exception as e:
            logger.warning("oracle_update_error", error=str(e))

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

    async def _on_price_update(self, _event: Event) -> None:
        """Handle price update events from trading engine."""
        # Note: Most widget updates are now done directly in _fetch_prices
        # This handler is mainly for trading engine events
        if self._paused:
            return

        # Update aegis periodically
        if self.paper_engine:
            aegis = self.query_one("#aegis", AegisWidget)
            await aegis.refresh_data()

    async def _on_signal(self, event: Event) -> None:
        """Handle signal generated events."""
        data = event.data
        signal_type = data.get("signal_type", "unknown").upper()
        symbol = data.get("symbol", "")
        confidence = data.get("confidence", 0)

        # Always log signal received
        self._log_msg(f"Signal received: {signal_type} {symbol} ({confidence:.0%})")

        if self._paused:
            return

        # Update oracle widget
        try:
            oracle = self.query_one("#oracle", OracleWidget)
            oracle.update_signal(data)
        except Exception as e:
            self._log_msg(f"Oracle update error: {e}")

        # Log to activity
        if signal_type in ("LONG", "SHORT"):
            logs = self.query_one("#logs", LogsWidget)
            logs.add_entry(
                f"Signal: {signal_type} {symbol} (conf: {confidence:.0%})", level="signal"
            )

    async def _on_circuit_trip(self, event: Event) -> None:
        """Handle circuit breaker trip events."""
        data = event.data
        aegis = self.query_one("#aegis", AegisWidget)
        aegis.set_tripped(data.get("reason", "Unknown"))

        logs = self.query_one("#logs", LogsWidget)
        logs.add_entry(f"CIRCUIT BREAKER: {data.get('reason', 'Trading paused')}", level="warning")

        self.notify("Circuit Breaker Tripped!", severity="warning", timeout=10)

    async def _on_trade(self, event: Event) -> None:
        """Handle trade executed events."""
        data = event.data
        logs = self.query_one("#logs", LogsWidget)
        side = data.get("side", "").upper()
        symbol = data.get("symbol", "")
        quantity = data.get("quantity", 0)
        price = data.get("price", 0)
        logs.add_entry(f"FILLED: {side} {quantity:.6f} {symbol} @ ${price:,.2f}", level="trade")

        # Refresh positions and stats
        positions = self.query_one("#positions", PositionsWidget)
        await positions.refresh_data()

        stats = self.query_one("#stats", StatsWidget)
        await stats.refresh_data()

        aegis = self.query_one("#aegis", AegisWidget)
        await aegis.refresh_data()

        self.notify(f"Order Filled: {side} {symbol}", severity="information")

    async def _on_order_approved(self, event: Event) -> None:
        """Handle order approved events."""
        data = event.data
        logs = self.query_one("#logs", LogsWidget)
        side = data.get("side", "").upper()
        symbol = data.get("symbol", "")
        logs.add_entry(f"APPROVED: {side} {symbol}", level="success")

    async def _on_order_rejected(self, event: Event) -> None:
        """Handle order rejected events."""
        data = event.data
        logs = self.query_one("#logs", LogsWidget)
        symbol = data.get("symbol", "")
        reason = data.get("message", data.get("reason", "Unknown"))
        logs.add_entry(f"REJECTED: {symbol} - {reason}", level="warning")

    def action_quit(self) -> None:
        """Quit the application."""
        logger.info("tui_quit_requested")
        self.exit()

    async def action_panic(self) -> None:
        """Panic button - close all positions."""
        logs = self.query_one("#logs", LogsWidget)
        logs.add_entry("PANIC MODE ACTIVATED - Closing all positions!", level="error")

        await self.event_bus.publish(Event(type=EventType.PANIC_TRIGGERED, data={}))

        self.notify("Panic Mode - Closing all positions!", severity="error", timeout=5)

    async def action_toggle_pause(self) -> None:
        """Toggle pause/resume trading."""
        self._paused = not self._paused

        logs = self.query_one("#logs", LogsWidget)
        if self._paused:
            await self.event_bus.publish(Event(type=EventType.SYSTEM_PAUSED, data={}))
            logs.add_entry("Trading PAUSED", level="warning")
            self.notify("Trading Paused", severity="warning")
        else:
            await self.event_bus.publish(Event(type=EventType.SYSTEM_RESUMED, data={}))
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
