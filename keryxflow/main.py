"""KeryxFlow main entrypoint."""

import asyncio
import logging
import sys
import warnings
from pathlib import Path

# Suppress aiohttp/ccxt unclosed session warnings
# These occur because we use multiple asyncio.run() calls with Textual TUI
# The resources are still cleaned up by garbage collection
warnings.filterwarnings("ignore", message="Unclosed client session")
warnings.filterwarnings("ignore", message="Unclosed connector")
warnings.filterwarnings("ignore", message="binance requires")
logging.getLogger("ccxt.base.exchange").setLevel(logging.CRITICAL)
logging.getLogger("aiohttp.client").setLevel(logging.CRITICAL)


class _StderrFilter:
    """Filter to suppress ccxt/aiohttp cleanup messages on stderr."""

    def __init__(self, stream):
        self._stream = stream
        self._suppress_patterns = [
            "binance requires to release",
            "Unclosed client session",
            "Unclosed connector",
            "client_session:",
            "connections:",
            "connector:",
        ]

    def write(self, text):
        if not any(p in text for p in self._suppress_patterns):
            self._stream.write(text)

    def flush(self):
        self._stream.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


# Apply stderr filter immediately to suppress cleanup messages
sys.stderr = _StderrFilter(sys.__stderr__)

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


async def initialize() -> tuple[ExchangeClient, PaperTradingEngine]:
    """Initialize all components before starting TUI."""
    settings = get_settings()
    event_bus = get_event_bus()

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

    return client, paper


async def shutdown(client: ExchangeClient) -> None:
    """Gracefully shutdown all components."""
    event_bus = get_event_bus()

    logger.info("shutting_down")

    # Disconnect from exchange
    if client:
        await client.disconnect()

    # Stop event bus
    await event_bus.stop()

    logger.info("keryxflow_stopped")


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

    # Initialize components
    client, paper = asyncio.run(initialize())

    # Create and start trading engine (before TUI, where asyncio works correctly)
    print("\n  [5/5] Starting trading engine...")
    event_bus = get_event_bus()
    trading_engine = TradingEngine(
        exchange_client=client,
        paper_engine=paper,
        event_bus=event_bus,
    )
    try:
        asyncio.run(trading_engine.start())
        print("        ✓ Trading engine started")
    except Exception as e:
        print(f"        ✗ Trading engine failed: {e}")
        # Continue without engine - TUI can still work
        logger.error("trading_engine_start_failed", error=str(e))

    try:
        # Run the TUI
        app = KeryxFlowApp(
            event_bus=event_bus,
            exchange_client=client,
            paper_engine=paper,
            trading_engine=trading_engine,
        )
        app.run()
    finally:
        # Cleanup
        asyncio.run(trading_engine.stop())
        asyncio.run(shutdown(client))
        print("\n  Stack sats. ₿\n")


if __name__ == "__main__":
    run()
