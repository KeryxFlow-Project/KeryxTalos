"""FastAPI REST server for monitoring KeryxFlow."""

import asyncio
from typing import Any

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from keryxflow.config import get_settings
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
        from keryxflow.agent.session import get_trading_session

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


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(title="KeryxFlow API", version="0.13.0")
    app.include_router(router)
    return app


async def start_api_server() -> asyncio.Task[None]:
    """Start the API server as a background asyncio task.

    Returns:
        The asyncio task running the server.
    """
    settings = get_settings()
    config = uvicorn.Config(
        app=create_app(),
        host="0.0.0.0",
        port=settings.api.port,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    logger.info("api_server_started", port=settings.api.port)
    return task
