"""Web dashboard router for KeryxFlow."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from keryxflow.aegis.risk import get_risk_manager
from keryxflow.agent.session import get_trading_session
from keryxflow.core.repository import get_trade_repository
from keryxflow.exchange.paper import get_paper_engine

router = APIRouter()

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


async def _get_balance() -> dict[str, Any]:
    try:
        engine = get_paper_engine()
        balance = await engine.get_balance()
        total = balance.get("total", {})
        return {"total": total.get("USDT", 0.0), "free": balance.get("free", {}).get("USDT", 0.0)}
    except Exception:
        return {"total": 0.0, "free": 0.0}


async def _get_positions() -> list[dict[str, Any]]:
    try:
        engine = get_paper_engine()
        positions = await engine.get_positions()
        return [
            {
                "symbol": p.symbol,
                "side": p.side,
                "quantity": p.quantity,
                "entry_price": p.entry_price,
                "current_price": p.current_price,
                "unrealized_pnl": p.unrealized_pnl,
                "unrealized_pnl_pct": p.unrealized_pnl_percentage,
            }
            for p in positions
        ]
    except Exception:
        return []


async def _get_recent_trades() -> list[dict[str, Any]]:
    try:
        repo = get_trade_repository()
        today_start = datetime.now(tz=UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        trades = await repo.get_trades_by_date(start_date=today_start)
        return [
            {
                "symbol": t.symbol,
                "side": t.side,
                "quantity": t.quantity,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "pnl": t.pnl,
                "pnl_pct": t.pnl_percentage,
                "status": t.status,
            }
            for t in trades
        ]
    except Exception:
        return []


def _get_risk_status() -> dict[str, Any]:
    try:
        rm = get_risk_manager()
        return rm.get_status()
    except Exception:
        return {
            "profile": "N/A",
            "balance": 0.0,
            "daily_pnl": 0.0,
            "daily_drawdown": 0.0,
            "circuit_breaker_active": False,
            "total_exposure_pct": 0.0,
        }


def _get_session_status() -> dict[str, Any]:
    try:
        session = get_trading_session()
        return session.get_status()
    except Exception:
        return {
            "state": "idle",
            "stats": {
                "cycles_completed": 0,
                "trades_executed": 0,
                "trades_won": 0,
                "total_pnl": 0.0,
                "win_rate": 0.0,
            },
        }


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Render the main dashboard page."""
    balance, positions, recent_trades = await asyncio.gather(
        _get_balance(), _get_positions(), _get_recent_trades()
    )
    risk_status = _get_risk_status()
    session_status = _get_session_status()

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "balance": balance,
            "positions": positions,
            "recent_trades": recent_trades,
            "risk": risk_status,
            "session": session_status,
        },
    )
