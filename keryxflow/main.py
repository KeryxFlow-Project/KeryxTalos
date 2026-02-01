"""KeryxFlow main entrypoint."""

import asyncio
import signal
from pathlib import Path

from keryxflow import __version__
from keryxflow.config import get_settings
from keryxflow.core.database import get_or_create_user_profile, get_session, init_db
from keryxflow.core.events import EventType, get_event_bus, system_event
from keryxflow.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


class KeryxFlow:
    """Main application class."""

    def __init__(self):
        """Initialize the application."""
        self.settings = get_settings()
        self.event_bus = get_event_bus()
        self._running = False
        self._shutdown_event = asyncio.Event()

    async def startup(self) -> None:
        """Initialize all components."""
        logger.info("starting_keryxflow", version=__version__)

        # Initialize database
        await init_db()
        logger.info("database_initialized")

        # Get or create user profile
        async for session in get_session():
            profile = await get_or_create_user_profile(session)
            logger.info(
                "user_profile_loaded",
                experience=profile.experience_level.value,
                risk_profile=profile.risk_profile.value,
            )

        # Start event bus
        await self.event_bus.start()

        # Publish system started event
        await self.event_bus.publish(
            system_event(EventType.SYSTEM_STARTED, f"KeryxFlow {__version__} started")
        )

        self._running = True
        logger.info("keryxflow_started", mode=self.settings.system.mode)

    async def shutdown(self) -> None:
        """Gracefully shutdown all components."""
        if not self._running:
            return

        logger.info("shutting_down")
        self._running = False

        # Publish system stopped event
        await self.event_bus.publish_sync(
            system_event(EventType.SYSTEM_STOPPED, "KeryxFlow shutting down")
        )

        # Stop event bus
        await self.event_bus.stop()

        logger.info("keryxflow_stopped")

    async def run(self) -> None:
        """Run the main application loop."""
        try:
            await self.startup()

            # Print startup message
            print(f"\n{'='*60}")
            print(f"  KeryxFlow v{__version__}")
            print(f"  Mode: {self.settings.system.mode.upper()}")
            print(f"  Symbols: {', '.join(self.settings.system.symbols)}")
            print(f"{'='*60}")
            print("\n  Stack sats. ₿\n")
            print("  Press Ctrl+C to exit.\n")

            # Wait for shutdown signal
            await self._shutdown_event.wait()

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
        print("\n\nGoodbye! Stack sats. ₿\n")


if __name__ == "__main__":
    run()
