"""KeryxFlow main entrypoint."""

import asyncio
from pathlib import Path

from keryxflow import __version__
from keryxflow.config import get_settings
from keryxflow.core.database import get_or_create_user_profile, get_session, init_db
from keryxflow.core.engine import TradingEngine
from keryxflow.core.events import get_event_bus
from keryxflow.core.logging import get_logger, setup_logging
from keryxflow.exchange.client import ExchangeClient
from keryxflow.exchange.paper import PaperTradingEngine
from keryxflow.hermes.app import KeryxFlowApp

logger = get_logger(__name__)


BANNER = """
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   ██╗  ██╗███████╗██████╗ ██╗   ██╗██╗  ██╗                   ║
║   ██║ ██╔╝██╔════╝██╔══██╗╚██╗ ██╔╝╚██╗██╔╝                   ║
║   █████╔╝ █████╗  ██████╔╝ ╚████╔╝  ╚███╔╝                    ║
║   ██╔═██╗ ██╔══╝  ██╔══██╗  ╚██╔╝   ██╔██╗                    ║
║   ██║  ██╗███████╗██║  ██║   ██║   ██╔╝ ██╗                   ║
║   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝  FLOW             ║
║                                                               ║
║   Your keys, your trades, your code.                          ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
"""


async def main() -> None:
    """Main async function - runs everything in a single event loop."""
    settings = get_settings()
    event_bus = get_event_bus()
    client: ExchangeClient | None = None
    trading_engine: TradingEngine | None = None

    try:
        # === INITIALIZATION ===
        print(BANNER)
        print(f"  Version: {__version__}")
        print(f"  Mode: {settings.system.mode.upper()} TRADING")
        print(f"  Symbols: {', '.join(settings.system.symbols)}")
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
        paper = PaperTradingEngine(
            initial_balance=10000.0,
            slippage_pct=0.001,
        )
        await paper.initialize()
        balance = await paper.get_balance()
        usdt = balance["total"].get("USDT", 0)
        print(f"        ✓ Balance: ${usdt:,.2f} USDT")

        # Connect to exchange
        print("\n  [4/4] Connecting to Binance...")
        sandbox = settings.system.mode == "paper"
        client = ExchangeClient(sandbox=sandbox)
        connected = await client.connect()

        if not connected:
            print("        ✗ Connection failed!")
            raise RuntimeError("Failed to connect to exchange")

        print("        ✓ Connected!")

        # Start event bus
        await event_bus.start()
        logger.info("keryxflow_initialized", mode=settings.system.mode)

        print()
        print("─" * 65)
        print("\n  Starting TUI...")
        print()

        # === START TRADING ENGINE ===
        print("\n  [5/5] Starting trading engine...")
        trading_engine = TradingEngine(
            exchange_client=client,
            paper_engine=paper,
            event_bus=event_bus,
        )
        try:
            await trading_engine.start()
            print("        ✓ Trading engine started")
        except Exception as e:
            print(f"        ✗ Trading engine failed: {e}")
            logger.error("trading_engine_start_failed", error=str(e))

        # === RUN TUI ===
        app = KeryxFlowApp(
            event_bus=event_bus,
            exchange_client=client,
            paper_engine=paper,
            trading_engine=trading_engine,
        )
        await app.run_async()

    finally:
        # === CLEANUP (same event loop!) ===
        if trading_engine:
            await trading_engine.stop()

        logger.info("shutting_down")

        if client:
            await client.disconnect()

        await event_bus.stop()
        logger.info("keryxflow_stopped")

        print("\n  Stack sats. ₿\n")


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

    # Run everything in a single event loop
    asyncio.run(main())


if __name__ == "__main__":
    run()
