"""KeryxFlow main entrypoint."""

import asyncio
from pathlib import Path
from typing import Any

from keryxflow import __version__
from keryxflow.config import get_settings
from keryxflow.core.database import get_or_create_user_profile, get_session, init_db
from keryxflow.core.engine import TradingEngine
from keryxflow.core.events import get_event_bus
from keryxflow.core.logging import get_logger, setup_logging
from keryxflow.exchange import get_exchange_adapter
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

# Global state for cleanup
_cleanup_state: dict[str, Any] = {}


def initialize_sync() -> dict[str, Any]:
    """Initialize components synchronously (creates objects but doesn't connect).

    The actual connection happens inside Textual's event loop.
    """
    settings = get_settings()
    event_bus = get_event_bus()

    # === INITIALIZATION ===
    print(BANNER)
    print(f"  Version: {__version__}")
    print(f"  Mode: {settings.system.mode.upper()} TRADING")
    print(f"  Symbols: {', '.join(settings.system.symbols)}")
    print()
    print("─" * 65)

    # Initialize database (sync wrapper)
    print("\n  [1/3] Initializing database...")
    asyncio.run(_init_db_and_profile())
    print("        ✓ Database ready")

    # Initialize paper trading (sync wrapper)
    print("\n  [2/3] Initializing paper trading engine...")
    paper = PaperTradingEngine(
        initial_balance=10000.0,
        slippage_pct=0.001,
    )
    asyncio.run(paper.initialize())
    balance = asyncio.run(paper.get_balance())
    usdt = balance["total"].get("USDT", 0)
    print(f"        ✓ Balance: ${usdt:,.2f} USDT")

    # Create exchange client (but DON'T connect yet - that happens in TUI)
    print("\n  [3/3] Creating exchange client...")
    is_demo = settings.system.mode == "demo"
    sandbox = settings.system.mode == "paper"
    client = get_exchange_adapter(sandbox=sandbox)
    if is_demo:
        print("        ✓ Demo client ready (synthetic data)")
    else:
        print(
            f"        ✓ {settings.system.exchange.capitalize()} client ready (will connect in TUI)"
        )

    # Create trading engine (but DON'T start yet - that happens in TUI)
    trading_engine = TradingEngine(
        exchange_client=client,
        paper_engine=paper,
        event_bus=event_bus,
    )

    print()
    print("─" * 65)
    print("\n  Starting TUI...")
    print()

    return {
        "event_bus": event_bus,
        "client": client,
        "paper": paper,
        "trading_engine": trading_engine,
    }


async def _init_db_and_profile() -> None:
    """Initialize database and load user profile."""
    await init_db()
    logger.info("database_initialized")

    async for session in get_session():
        profile = await get_or_create_user_profile(session)
        logger.info(
            "user_profile_loaded",
            experience=profile.experience_level.value,
            risk_profile=profile.risk_profile.value,
        )
        print(f"        ✓ Experience: {profile.experience_level.value}")
        print(f"        ✓ Risk Profile: {profile.risk_profile.value}")


async def cleanup(state: dict[str, Any]) -> None:
    """Clean up all components asynchronously."""
    trading_engine = state.get("trading_engine")
    client = state.get("client")
    event_bus = state.get("event_bus")

    if trading_engine and trading_engine._running:
        await trading_engine.stop()

    logger.info("shutting_down")

    if client and client.is_connected:
        await client.disconnect()

    if event_bus:
        await event_bus.stop()

    logger.info("keryxflow_stopped")
    print("\n  Stack sats. ₿\n")


def run() -> None:
    """Main entry point."""
    global _cleanup_state

    # Ensure data directories exist
    Path("data/logs").mkdir(parents=True, exist_ok=True)

    # Setup logging
    settings = get_settings()
    setup_logging(
        level=settings.system.log_level,
        log_file=Path("data/logs/keryxflow.log"),
        json_format=settings.env == "production",
    )

    try:
        # Phase 1: Initialize (sync - creates objects but doesn't connect)
        _cleanup_state = initialize_sync()

        # Phase 2: Run TUI (sync - Textual manages its own event loop)
        # Connection/startup happens inside Textual's event loop in on_mount()
        app = KeryxFlowApp(
            event_bus=_cleanup_state["event_bus"],
            exchange_client=_cleanup_state["client"],
            paper_engine=_cleanup_state["paper"],
            trading_engine=_cleanup_state["trading_engine"],
        )
        app.run()

    finally:
        # Phase 3: Cleanup (async)
        if _cleanup_state:
            asyncio.run(cleanup(_cleanup_state))


if __name__ == "__main__":
    run()
