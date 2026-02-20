"""FastAPI REST server with auth, monitoring endpoints, and WebSocket event streaming."""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from keryxflow.agent.session import get_trading_session
from keryxflow.config import get_settings
from keryxflow.core.events import Event, EventType, get_event_bus
from keryxflow.core.logging import get_logger

logger = get_logger(__name__)

security = HTTPBearer(auto_error=False)


async def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> None:
    """Verify bearer token against configured API token.

    If no token is configured (empty string), authentication is skipped.
    """
    settings = get_settings()
    token = settings.api.token

    if not token:
        return

    if credentials is None or credentials.credentials != token:
        raise HTTPException(status_code=401, detail="Invalid or missing token")


router = APIRouter(prefix="/api", dependencies=[Depends(verify_token)])


@router.get("/status")
async def get_status() -> dict[str, Any]:
    """Get engine and risk manager status."""
    result: dict[str, Any] = {}

    try:
        from keryxflow.aegis.risk import get_risk_manager

        risk = get_risk_manager()
        result["risk"] = risk.get_status()
    except Exception:
        result["risk"] = None

    try:
        session = get_trading_session()
        result["session"] = session.get_status()
    except Exception:
        result["session"] = None

    return result


@router.get("/positions")
async def get_positions() -> list[dict[str, Any]]:
    """Get open positions with unrealized PnL."""
    try:
        from keryxflow.exchange.paper import get_paper_engine

        engine = get_paper_engine()
        positions = await engine.get_positions()
        return [
            {
                "id": p.id,
                "symbol": p.symbol,
                "side": p.side.value,
                "quantity": p.quantity,
                "entry_price": p.entry_price,
                "current_price": p.current_price,
                "unrealized_pnl": p.unrealized_pnl,
                "unrealized_pnl_percentage": p.unrealized_pnl_percentage,
                "stop_loss": p.stop_loss,
                "take_profit": p.take_profit,
                "opened_at": p.opened_at.isoformat() if p.opened_at else None,
            }
            for p in positions
        ]
    except Exception:
        return []


@router.get("/trades")
async def get_trades() -> list[dict[str, Any]]:
    """Get the 50 most recent trades."""
    try:
        from keryxflow.core.repository import get_trade_repository

        repo = get_trade_repository()
        trades = await repo.get_recent_trades(limit=50)
        return [
            {
                "id": t.id,
                "symbol": t.symbol,
                "side": t.side.value,
                "quantity": t.quantity,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "stop_loss": t.stop_loss,
                "take_profit": t.take_profit,
                "pnl": t.pnl,
                "pnl_percentage": t.pnl_percentage,
                "status": t.status.value,
                "is_paper": t.is_paper,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "closed_at": t.closed_at.isoformat() if t.closed_at else None,
            }
            for t in trades
        ]
    except Exception:
        return []


@router.get("/balance")
async def get_balance() -> dict[str, Any]:
    """Get portfolio balance."""
    try:
        from keryxflow.exchange.paper import get_paper_engine

        engine = get_paper_engine()
        return await engine.get_balance()
    except Exception:
        return {"total": {}, "free": {}, "used": {}}


# Module-level state for pause tracking and server lifecycle
_paused = False
_server: uvicorn.Server | None = None
_server_task: asyncio.Task | None = None


def _event_to_dict(event: Event) -> dict[str, Any]:
    """Convert an Event to a JSON-serializable dictionary."""
    return {
        "type": event.type.value,
        "timestamp": event.timestamp.isoformat(),
        "data": event.data,
    }


async def _on_paused(_event: Event) -> None:
    global _paused
    _paused = True


async def _on_resumed(_event: Event) -> None:
    global _paused
    _paused = False


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Lifespan handler: subscribe/unsubscribe pause sync events."""
    event_bus = get_event_bus()
    event_bus.subscribe(EventType.SYSTEM_PAUSED, _on_paused)
    event_bus.subscribe(EventType.SYSTEM_RESUMED, _on_resumed)
    event_bus.subscribe(EventType.PANIC_TRIGGERED, _on_paused)
    yield
    event_bus.unsubscribe(EventType.SYSTEM_PAUSED, _on_paused)
    event_bus.unsubscribe(EventType.SYSTEM_RESUMED, _on_resumed)
    event_bus.unsubscribe(EventType.PANIC_TRIGGERED, _on_paused)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="KeryxFlow API",
        version="0.13.0",
        lifespan=_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include the authenticated router with GET endpoints
    app.include_router(router)

    @app.post("/api/panic")
    async def panic() -> dict[str, str]:
        """Trigger emergency stop -- closes all positions and pauses trading."""
        global _paused
        event_bus = get_event_bus()
        await event_bus.publish(
            Event(
                type=EventType.PANIC_TRIGGERED,
                data={"source": "api", "timestamp": datetime.now(UTC).isoformat()},
            )
        )
        _paused = True
        return {"status": "panic_triggered"}

    @app.post("/api/pause")
    async def pause_toggle() -> dict[str, str]:
        """Toggle pause/resume for trading."""
        global _paused
        event_bus = get_event_bus()

        if _paused:
            await event_bus.publish(
                Event(
                    type=EventType.SYSTEM_RESUMED,
                    data={"source": "api"},
                )
            )
            _paused = False
            return {"status": "resumed"}
        else:
            await event_bus.publish(
                Event(
                    type=EventType.SYSTEM_PAUSED,
                    data={"source": "api"},
                )
            )
            _paused = True
            return {"status": "paused"}

    @app.get("/api/agent/status")
    async def agent_status() -> dict[str, Any]:
        """Return the cognitive agent session state and stats."""
        session = get_trading_session()
        return session.get_status()

    @app.websocket("/ws/events")
    async def websocket_events(websocket: WebSocket) -> None:
        """Stream all EventBus events to connected WebSocket clients as JSON."""
        await websocket.accept()
        event_bus = get_event_bus()
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=256)

        async def _enqueue(event: Event) -> None:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest, then enqueue
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
                with contextlib.suppress(asyncio.QueueFull):
                    queue.put_nowait(event)

        # Subscribe to all event types
        for event_type in EventType:
            event_bus.subscribe(event_type, _enqueue)

        try:
            while True:
                event = await queue.get()
                await websocket.send_json(_event_to_dict(event))
        except WebSocketDisconnect:
            pass
        except Exception:
            logger.warning("websocket_error", exc_info=True)
        finally:
            for event_type in EventType:
                event_bus.unsubscribe(event_type, _enqueue)

    return app


async def start_api_server(
    host: str = "0.0.0.0",
    port: int = 8080,
) -> tuple[uvicorn.Server, asyncio.Task]:
    """Start the FastAPI server as a background asyncio task.

    Returns:
        Tuple of (server, task) for lifecycle management.
    """
    global _server, _server_task

    app = create_app()
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)

    task = asyncio.create_task(server.serve())

    _server = server
    _server_task = task

    logger.info("api_server_started", host=host, port=port)
    return server, task


async def stop_api_server() -> None:
    """Stop the running API server gracefully."""
    global _server, _server_task

    if _server is not None:
        _server.should_exit = True

    if _server_task is not None:
        try:
            await asyncio.wait_for(_server_task, timeout=5.0)
        except TimeoutError:
            _server_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await _server_task

    _server = None
    _server_task = None
    logger.info("api_server_stopped")
