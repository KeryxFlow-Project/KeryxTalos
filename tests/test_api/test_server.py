"""Tests for the FastAPI monitoring endpoints."""

import os

import httpx
import pytest

from keryxflow.api.server import create_app


@pytest.fixture
def app():
    """Create a fresh FastAPI app for each test."""
    return create_app()


@pytest.fixture
def client(app):
    """Create an httpx async client for the app."""
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def _set_api_token():
    """Set a bearer token for auth tests, cleaning up after."""
    import keryxflow.config as config_module

    os.environ["KERYXFLOW_API_TOKEN"] = "secret123"
    config_module._settings = None
    yield
    os.environ.pop("KERYXFLOW_API_TOKEN", None)
    config_module._settings = None


# ── Auth tests ───────────────────────────────────────────────────────────────


async def test_auth_skipped_when_token_empty(client):
    """Auth is skipped when no token is configured."""
    resp = await client.get("/api/status")
    assert resp.status_code == 200


@pytest.mark.usefixtures("_set_api_token")
async def test_auth_rejects_missing_header(client):
    """Requests without Authorization header are rejected when token is set."""
    resp = await client.get("/api/status")
    assert resp.status_code == 401


@pytest.mark.usefixtures("_set_api_token")
async def test_auth_rejects_invalid_token(client):
    """Requests with wrong token are rejected."""
    resp = await client.get("/api/status", headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401


@pytest.mark.usefixtures("_set_api_token")
async def test_auth_accepts_valid_token(client):
    """Requests with correct token succeed."""
    resp = await client.get("/api/status", headers={"Authorization": "Bearer secret123"})
    assert resp.status_code == 200


# ── Endpoint tests ───────────────────────────────────────────────────────────


async def test_status_returns_dict(client):
    """GET /api/status returns a dict with risk and session keys."""
    resp = await client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "risk" in data
    assert "session" in data


async def test_positions_returns_list(client):
    """GET /api/positions returns a list."""
    resp = await client.get("/api/positions")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_trades_returns_list(client):
    """GET /api/trades returns a list."""
    resp = await client.get("/api/trades")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_balance_returns_dict(client):
    """GET /api/balance returns a dict with total/free/used."""
    resp = await client.get("/api/balance")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "free" in data
    assert "used" in data


async def test_trades_with_data(client, init_db):
    """GET /api/trades returns trade data when trades exist."""
    from keryxflow.core.repository import get_trade_repository

    repo = get_trade_repository()
    await repo.create_trade(
        symbol="ETH/USDT",
        side="sell",
        quantity=1.5,
        entry_price=3200.0,
        is_paper=True,
    )

    resp = await client.get("/api/trades")
    assert resp.status_code == 200
    trades = resp.json()
    assert len(trades) >= 1
    # Find the trade we just created (most recent)
    trade = trades[0]
    assert trade["symbol"] == "ETH/USDT"
    assert trade["side"] == "sell"
    assert trade["quantity"] == 1.5
    assert trade["entry_price"] == 3200.0
    assert trade["is_paper"] is True
    assert trade["status"] == "open"
