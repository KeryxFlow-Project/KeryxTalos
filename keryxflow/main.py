"""KeryxFlow main entrypoint."""

import asyncio
import signal
from datetime import datetime
from pathlib import Path

from keryxflow import __version__
from keryxflow.config import get_settings
from keryxflow.core.database import get_or_create_user_profile, get_session, init_db
from keryxflow.core.events import EventType, get_event_bus, system_event
from keryxflow.core.logging import get_logger, setup_logging
from keryxflow.exchange.client import ExchangeClient
from keryxflow.exchange.paper import PaperTradingEngine

logger = get_logger(__name__)


BANNER = """
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   ██╗  ██╗███████╗██████╗ ██╗   ██╗██╗  ██╗                   ║
║   ██║ ██╔╝██╔════╝██╔══██╗╚██╗ ██╔╝╚██╗██╔╝                   ║
║   █████╔╝ █████╗  ██████╔╝ ╚████╔╝  ╚███╔╝                    ║
║   ██╔═██╗ ██╔══╝  ██╔══██╗  ╚██╔╝   ██╔██╗                    ║
║   ██║  ██╗███████╗██║  ██║   ██║   ██╔╝ ██╗                   ║
║   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝  FLOW            ║
║                                                               ║
║   Your keys, your trades, your code.                         ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
"""


class KeryxFlow:
    """Main application class."""

    def __init__(self):
        """Initialize the application."""
        self.settings = get_settings()
        self.event_bus = get_event_bus()
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._client: ExchangeClient | None = None
        self._paper: PaperTradingEngine | None = None

    async def startup(self) -> None:
        """Initialize all components."""
        print(BANNER)
        print(f"  Version: {__version__}")
        print(f"  Mode: {self.settings.system.mode.upper()} TRADING")
        print(f"  Symbols: {', '.join(self.settings.system.symbols)}")
        print()
        print("─" * 65)

        # Initialize database
        print("\n  [1/4] Initializing database...")
        await init_db()
        logger.info("database_initialized")
        print("        ✓ Database ready")

        # Get or create user profile
        print("\n  [2/4] Loading user profile...")
        async for session in get_session():
            profile = await get_or_create_user_profile(session)
            logger.info(
                "user_profile_loaded",
                experience=profile.experience_level.value,
                risk_profile=profile.risk_profile.value,
            )
            print(f"        ✓ Experience: {profile.experience_level.value}")
            print(f"        ✓ Risk Profile: {profile.risk_profile.value}")

        # Initialize paper trading
        print("\n  [3/4] Initializing paper trading engine...")
        self._paper = PaperTradingEngine(
            initial_balance=10000.0,  # Default paper trading balance
            slippage_pct=0.001,
        )
        await self._paper.initialize()
        balance = await self._paper.get_balance()
        usdt = balance["total"].get("USDT", 0)
        print(f"        ✓ Balance: ${usdt:,.2f} USDT")

        # Connect to exchange
        print("\n  [4/4] Connecting to Binance...")
        sandbox = self.settings.system.mode == "paper"
        self._client = ExchangeClient(sandbox=sandbox)
        connected = await self._client.connect()

        if not connected:
            print("        ✗ Connection failed!")
            raise RuntimeError("Failed to connect to exchange")

        print("        ✓ Connected!")

        # Start event bus
        await self.event_bus.start()

        # Publish system started event
        await self.event_bus.publish(
            system_event(EventType.SYSTEM_STARTED, f"KeryxFlow {__version__} started")
        )

        self._running = True
        logger.info("keryxflow_started", mode=self.settings.system.mode)

        print()
        print("─" * 65)
        print()
        print("  Press Ctrl+C to stop")
        print()
        print("─" * 65)

    async def shutdown(self) -> None:
        """Gracefully shutdown all components."""
        if not self._running:
            return

        print("\n\n  Shutting down...")
        logger.info("shutting_down")
        self._running = False

        # Disconnect from exchange
        if self._client:
            await self._client.disconnect()
            print("  ✓ Disconnected from Binance")

        # Publish system stopped event
        await self.event_bus.publish_sync(
            system_event(EventType.SYSTEM_STOPPED, "KeryxFlow shutting down")
        )

        # Stop event bus
        await self.event_bus.stop()

        logger.info("keryxflow_stopped")
        print()
        print("  Stack sats. ₿")
        print()

    async def price_loop(self) -> None:
        """Main price monitoring loop."""
        symbols = self.settings.system.symbols
        iteration = 0

        print("\n  LIVE PRICE FEED")
        print("  " + "─" * 50)
        print()

        while self._running and not self._shutdown_event.is_set():
            iteration += 1
            now = datetime.now().strftime("%H:%M:%S")

            for symbol in symbols:
                try:
                    ticker = await self._client.get_ticker(symbol)
                    price = ticker["last"]
                    bid = ticker["bid"]
                    ask = ticker["ask"]
                    volume = ticker["volume"]

                    # Update paper engine
                    self._paper.update_price(symbol, price)

                    # Format symbol for display
                    base = symbol.split("/")[0]

                    # Calculate spread
                    spread = ((ask - bid) / bid) * 100 if bid else 0

                    # Display
                    print(
                        f"  [{now}] {base:>4}: ${price:>12,.2f}  "
                        f"│  Spread: {spread:.3f}%  "
                        f"│  Vol: {volume:>10,.2f}"
                    )

                except Exception as e:
                    logger.warning("price_fetch_error", symbol=symbol, error=str(e))

            # Show portfolio every 12 iterations (1 minute at 5s interval)
            if iteration % 12 == 0:
                await self._show_portfolio()

            # Wait before next update (5 seconds)
            try:
                await asyncio.wait_for(
                    asyncio.shield(self._shutdown_event.wait()),
                    timeout=5.0,
                )
                break
            except asyncio.TimeoutError:
                continue

    async def _show_portfolio(self) -> None:
        """Display current portfolio."""
        balance = await self._paper.get_balance()
        positions = await self._paper.get_positions()

        print()
        print("  " + "─" * 50)
        print("  PORTFOLIO")

        total_value = 0.0

        for curr, amt in balance["total"].items():
            if amt > 0:
                if curr == "USDT":
                    print(f"    {curr}: ${amt:,.2f}")
                    total_value += amt
                else:
                    price = self._paper.get_price(f"{curr}/USDT") or 0
                    value = amt * price
                    total_value += value
                    print(f"    {curr}: {amt:.8f} (≈${value:,.2f})")

        print(f"    ────────────────────────")
        print(f"    Total: ${total_value:,.2f}")

        if positions:
            print()
            print("  OPEN POSITIONS")
            for pos in positions:
                pnl_color = "+" if pos.unrealized_pnl >= 0 else ""
                print(
                    f"    {pos.symbol}: {pos.quantity} @ ${pos.entry_price:,.2f} "
                    f"│ PnL: {pnl_color}${pos.unrealized_pnl:,.2f} "
                    f"({pnl_color}{pos.unrealized_pnl_percentage:.2f}%)"
                )

        print("  " + "─" * 50)
        print()

    async def run(self) -> None:
        """Run the main application loop."""
        try:
            await self.startup()
            await self.price_loop()

        except asyncio.CancelledError:
            logger.info("received_cancel")
        except Exception as e:
            logger.error("runtime_error", error=str(e))
            raise
        finally:
            await self.shutdown()

    def handle_signal(self, sig: signal.Signals) -> None:
        """Handle OS signals."""
        logger.info("received_signal", signal=sig.name)
        self._shutdown_event.set()


async def async_main() -> None:
    """Async main function."""
    app = KeryxFlow()

    # Setup signal handlers
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: app.handle_signal(s))

    await app.run()


def run() -> None:
    """Main entry point."""
    # Ensure data directories exist
    Path("data/logs").mkdir(parents=True, exist_ok=True)

    # Setup logging
    settings = get_settings()
    setup_logging(
        level=settings.system.log_level,
        log_file=Path("data/logs/keryxflow.log"),
        json_format=settings.env == "production",
    )

    # Run the async main
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
