"""Main TUI application using Textual."""

import asyncio

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header

from keryxflow import __version__
from keryxflow.agent.session import TradingSession
from keryxflow.config import get_settings
from keryxflow.core.engine import TradingEngine
from keryxflow.core.events import Event, EventBus, EventType, get_event_bus
from keryxflow.core.logging import get_logger
from keryxflow.exchange.adapter import ExchangeAdapter
from keryxflow.exchange.paper import PaperTradingEngine
from keryxflow.hermes.widgets.aegis import AegisWidget
from keryxflow.hermes.widgets.agent import AgentWidget
from keryxflow.hermes.widgets.balance import BalanceWidget
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
        Binding("a", "toggle_agent", "Toggle Agent"),
        Binding("question_mark", "show_help", "Help"),
        Binding("l", "toggle_logs", "Toggle Logs"),
        Binding("s", "cycle_symbol", "Next Symbol"),
    ]

    def __init__(
        self,
        event_bus: EventBus | None = None,
        exchange_client: ExchangeAdapter | None = None,
        paper_engine: PaperTradingEngine | None = None,
        trading_engine: TradingEngine | None = None,
        trading_session: TradingSession | None = None,
    ) -> None:
        """Initialize the app."""
        super().__init__()
        self.settings = get_settings()
        self.event_bus = event_bus or get_event_bus()
        self.exchange_client = exchange_client
        self.paper_engine = paper_engine
        self.trading_engine = trading_engine
        self.trading_session = trading_session
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
                    yield BalanceWidget(id="balance")
                    yield PositionsWidget(id="positions")
                    yield AegisWidget(id="aegis")
                    yield StatsWidget(id="stats")
                    yield AgentWidget(id="agent")

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
        self.event_bus.subscribe(EventType.SESSION_STATE_CHANGED, self._on_session_state_changed)
        self.event_bus.subscribe(EventType.AGENT_CYCLE_COMPLETED, self._on_agent_cycle)

        # Log startup
        try:
            logs = self.query_one("#logs", LogsWidget)
            logs.add_entry("KeryxFlow starting...", level="info")
        except Exception:
            logger.debug("logs_widget_not_ready_at_mount", exc_info=True)

        # Initialize directly (skip splash for now)
        self.run_worker(self._initialize_after_splash)

    async def _initialize_after_splash(self) -> None:
        """Async initialization after splash screen."""
        try:
            self._log_msg("Starting initialization...")

            # Start event bus if not already running
            # This ensures the task runs in Textual's event loop
            if not self.event_bus.is_running:
                self._log_msg("Starting event bus...")
                await self.event_bus.start()
                self._log_msg("Event bus started!")

            # Connect exchange client if not already connected
            # This ensures the connection happens in Textual's event loop
            if self.exchange_client and not self.exchange_client.is_connected:
                self._log_msg("Connecting to exchange...")
                connected = await self.exchange_client.connect()
                if connected:
                    self._log_msg("Exchange connected!")
                else:
                    self._log_msg("Exchange connection failed!")

            # Start trading engine if not already started
            if self.trading_engine and not self.trading_engine._running:
                self._log_msg("Starting trading engine...")
                try:
                    await self.trading_engine.start()
                    self._log_msg("Trading engine started!")
                except Exception as e:
                    self._log_msg(f"Trading engine error: {e}")

            # Connect widgets
            self._log_msg("Connecting widgets...")
            if self.paper_engine:
                self._connect_widgets()
            else:
                self._log_msg(
                    f"No client/paper: client={self.exchange_client is not None}, "
                    f"paper={self.paper_engine is not None}"
                )

            # Connect balance widget if we have exchange client (even without paper engine)
            if self.exchange_client:
                try:
                    balance_widget = self.query_one("#balance", BalanceWidget)
                    balance_widget.set_exchange_client(self.exchange_client)
                    self._log_msg("Connected BALANCE to exchange client")
                    # Initial balance refresh
                    await balance_widget.refresh_data()
                except Exception as e:
                    self._log_msg(f"Balance widget setup error: {e}")

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
            logger.debug("log_msg_widget_unavailable", exc_info=True)

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

        # Connect balance widget to exchange client
        if self.exchange_client:
            balance_widget = self.query_one("#balance", BalanceWidget)
            balance_widget.set_exchange_client(self.exchange_client)
            self._log_msg("Connected BALANCE to exchange client")

        # Connect agent widget to trading session
        agent_widget = self.query_one("#agent", AgentWidget)
        if self.trading_session:
            agent_widget.set_session(self.trading_session)
            self._log_msg("Connected AGENT to trading session")
        else:
            # Check settings for agent mode
            agent_enabled = getattr(self.settings, "agent", None)
            if agent_enabled and getattr(agent_enabled, "enabled", False):
                agent_widget.set_enabled(True)
                self._log_msg("Agent mode enabled (no session)")
            else:
                agent_widget.set_enabled(False)
                self._log_msg("Agent mode disabled")

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
        balance_counter = 0
        balance_interval = int(self.settings.live.sync_interval / self.settings.hermes.refresh_rate)

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

            # Refresh balance periodically (every sync_interval seconds)
            balance_counter += 1
            if balance_counter >= balance_interval:
                balance_counter = 0
                try:
                    balance_widget = self.query_one("#balance", BalanceWidget)
                    await balance_widget.refresh_data()
                except Exception:
                    logger.debug("balance_refresh_error", exc_info=True)

            await asyncio.sleep(self.settings.hermes.refresh_rate)

    async def _fetch_prices_once(self) -> None:
        """Fetch prices once and update widgets."""
        if not self.exchange_client:
            return

        # Fetch prices in parallel with concurrency limit
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests

        async def fetch_single(symbol: str) -> tuple[str, dict | None]:
            async with semaphore:
                try:
                    ticker = await self.exchange_client.get_ticker(symbol)
                    return (symbol, ticker)
                except Exception as e:
                    logger.warning("price_fetch_error", symbol=symbol, error=str(e))
                    return (symbol, None)

        # Fetch all prices in parallel
        results = await asyncio.gather(*[fetch_single(s) for s in self._symbols])

        # Process results
        for symbol, ticker in results:
            if ticker is None:
                continue

            try:
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
            if self.trading_engine._ohlcv_buffer is not None:
                ohlcv = self.trading_engine._ohlcv_buffer.get_ohlcv(symbol)
            elif self.trading_engine._mtf_buffer is not None:
                ohlcv = self.trading_engine._mtf_buffer.get_primary_ohlcv(symbol)
            else:
                return
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
                self._log_msg(
                    f"Signal: {signal.signal_type.value.upper()} {symbol} ({signal.confidence:.0%})"
                )

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

        balance = self.query_one("#balance", BalanceWidget)
        await balance.refresh_data()

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

    async def _on_session_state_changed(self, event: Event) -> None:
        """Handle session state change events."""
        data = event.data
        new_state = data.get("new_state", "unknown")
        old_state = data.get("old_state", "unknown")

        # Update agent widget
        agent_widget = self.query_one("#agent", AgentWidget)
        if self.trading_session:
            agent_widget.set_status(self.trading_session.get_status())

        # Log the state change
        logs = self.query_one("#logs", LogsWidget)
        if new_state == "running":
            logs.add_entry(f"Agent session STARTED (was {old_state})", level="success")
            self.notify("Agent Running", severity="information")
        elif new_state == "paused":
            logs.add_entry(f"Agent session PAUSED (was {old_state})", level="warning")
            self.notify("Agent Paused", severity="warning")
        elif new_state == "stopped":
            logs.add_entry(f"Agent session STOPPED (was {old_state})", level="info")
            self.notify("Agent Stopped", severity="information")
        elif new_state == "error":
            reason = data.get("reason", "Unknown error")
            logs.add_entry(f"Agent session ERROR: {reason}", level="error")
            self.notify(f"Agent Error: {reason}", severity="error")

    async def _on_agent_cycle(self, _event: Event) -> None:
        """Handle agent cycle completion events."""
        # Update agent widget with latest stats
        agent_widget = self.query_one("#agent", AgentWidget)
        if self.trading_session:
            agent_widget.set_status(self.trading_session.get_status())

        # Refresh other widgets that may have been affected
        positions = self.query_one("#positions", PositionsWidget)
        await positions.refresh_data()

        stats = self.query_one("#stats", StatsWidget)
        await stats.refresh_data()

        aegis = self.query_one("#aegis", AegisWidget)
        await aegis.refresh_data()

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

    async def action_toggle_agent(self) -> None:
        """Toggle agent mode - start/pause the trading session."""
        import traceback

        logs = self.query_one("#logs", LogsWidget)
        agent_widget = self.query_one("#agent", AgentWidget)

        if not self.trading_session:
            # No session - try to create one if we have the necessary components
            if self.trading_engine:
                try:
                    self.trading_session = TradingSession(
                        engine=self.trading_engine,
                    )
                    self.trading_session._event_bus = self.event_bus
                    agent_widget.set_session(self.trading_session)
                    logs.add_entry("Trading session created", level="info")
                except Exception as e:
                    logs.add_entry(f"Failed to create session: {e}", level="error")
                    self.notify("Cannot create trading session", severity="error")
                    return
            else:
                logs.add_entry("No trading engine available for agent mode", level="warning")
                self.notify("Agent mode requires trading engine", severity="warning")
                return

        # Toggle session state
        if agent_widget.is_running:
            # Pause the session
            success = await self.trading_session.pause()
            if success:
                logs.add_entry("Agent session paused", level="warning")
            else:
                logs.add_entry("Failed to pause agent session", level="error")
        elif self.trading_session.state.value == "paused":
            # Resume the session
            success = await self.trading_session.resume()
            if success:
                logs.add_entry("Agent session resumed", level="success")
            else:
                logs.add_entry("Failed to resume agent session", level="error")
        else:
            # Start the session
            try:
                success = await self.trading_session.start()
                if success:
                    logs.add_entry("Agent session started", level="success")
                else:
                    # Show more details about the failure
                    errors = self.trading_session.stats.errors
                    if errors:
                        logs.add_entry(f"Start failed: {errors[-1][:50]}", level="error")
                    else:
                        logs.add_entry("Failed to start agent session", level="error")
            except Exception as e:
                logs.add_entry(f"Agent error: {str(e)[:50]}", level="error")
                logger.error("agent_start_error", error=str(e), tb=traceback.format_exc())

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
