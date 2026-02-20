"""FastAPI application factory and webhook server lifecycle."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import uvicorn
from fastapi import FastAPI

from keryxflow.api.webhook import router as webhook_router
from keryxflow.api.webhook import set_engine
from keryxflow.config import get_settings
from keryxflow.core.logging import get_logger

if TYPE_CHECKING:
    from keryxflow.core.engine import TradingEngine

logger = get_logger(__name__)


def create_app() -> FastAPI:
    """Create the FastAPI application with webhook routes."""
    app = FastAPI(
        title="KeryxFlow Webhook API",
        description="Webhook endpoint for external signal ingestion (e.g., TradingView alerts)",
        version="1.0.0",
    )

    app.include_router(webhook_router, prefix="/api")

    @app.get("/api/health")
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return app


class WebhookServer:
    """Manages the uvicorn server lifecycle for the webhook API."""

    def __init__(self, engine: TradingEngine | None = None) -> None:
        self._engine = engine
        self._server: uvicorn.Server | None = None
        self._task: asyncio.Task[None] | None = None

    def set_engine(self, engine: TradingEngine) -> None:
        """Set the trading engine for signal routing."""
        self._engine = engine
        set_engine(engine)

    async def start(self) -> None:
        """Start the webhook server as a background asyncio task."""
        settings = get_settings()

        set_engine(self._engine)

        app = create_app()
        config = uvicorn.Config(
            app=app,
            host=settings.webhook.host,
            port=settings.webhook.port,
            log_level="warning",
        )
        self._server = uvicorn.Server(config)

        self._task = asyncio.create_task(self._server.serve())

        logger.info(
            "webhook_server_started",
            host=settings.webhook.host,
            port=settings.webhook.port,
        )

    async def stop(self) -> None:
        """Stop the webhook server gracefully."""
        if self._server is not None:
            self._server.should_exit = True

        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except TimeoutError:
                self._task.cancel()
            self._task = None

        set_engine(None)
        logger.info("webhook_server_stopped")


# Global singleton
_server: WebhookServer | None = None


def get_webhook_server() -> WebhookServer:
    """Get the global webhook server instance."""
    global _server
    if _server is None:
        _server = WebhookServer()
    return _server
