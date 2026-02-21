"""Tests for the API server endpoints and WebSocket."""

import asyncio
import os

import pytest
from httpx import ASGITransport, AsyncClient

from keryxflow.api.server import create_app
from keryxflow.core.events import Event, EventType, get_event_bus

# Reusable transport + client helper
_BASE_URL = "http://test"


@pytest.fixture
def app():
    """Create a fresh FastAPI app for each test."""
    import keryxflow.api.server as server_module

    server_module._paused = False
    return create_app()


@pytest.fixture
async def client(app):
    """Async HTTP client wired to the ASGI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=_BASE_URL) as c:
        yield c


@pytest.fixture
def _set_api_token():
    """Set a bearer token for auth tests, cleaning up after."""
    import keryxflow.config as config_module

    os.environ["KERYXFLOW_API_TOKEN"] = "secret123"
    config_module._settings = None
    yield
    os.environ.pop("KERYXFLOW_API_TOKEN", None)
    config_module._settings = None


# -- Auth tests ---------------------------------------------------------------


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


# -- GET endpoint tests -------------------------------------------------------


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


async def test_trades_with_data(client, init_db):  # noqa: ARG001
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


# -- POST / WebSocket endpoint tests ------------------------------------------


async def test_panic_endpoint_publishes_event(client):
    """POST /api/panic should publish PANIC_TRIGGERED and return status."""
    event_bus = get_event_bus()
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    event_bus.subscribe(EventType.PANIC_TRIGGERED, handler)

    resp = await client.post("/api/panic")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "panic_triggered"

    # Event should be queued; dispatch it via publish_sync for determinism
    # The event was published to the queue, so let's drain it
    await _drain_event_bus(event_bus)

    assert len(received) == 1
    assert received[0].type == EventType.PANIC_TRIGGERED
    assert received[0].data["source"] == "api"


async def test_pause_toggle_pauses_then_resumes(client):
    """POST /api/pause should toggle between paused and resumed."""
    event_bus = get_event_bus()
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    event_bus.subscribe(EventType.SYSTEM_PAUSED, handler)
    event_bus.subscribe(EventType.SYSTEM_RESUMED, handler)

    # First call: should pause
    resp1 = await client.post("/api/pause")
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "paused"
    await _drain_event_bus(event_bus)

    # Second call: should resume
    resp2 = await client.post("/api/pause")
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "resumed"
    await _drain_event_bus(event_bus)

    paused_events = [e for e in received if e.type == EventType.SYSTEM_PAUSED]
    resumed_events = [e for e in received if e.type == EventType.SYSTEM_RESUMED]
    assert len(paused_events) >= 1
    assert len(resumed_events) >= 1


async def test_agent_status_endpoint(client):
    """GET /api/agent/status should return session status dict."""
    resp = await client.get("/api/agent/status")
    assert resp.status_code == 200
    body = resp.json()
    assert "session_id" in body
    assert "state" in body
    assert "stats" in body


async def test_websocket_receives_events(app):
    """WebSocket /ws/events should stream published events as JSON."""
    from starlette.testclient import TestClient

    event_bus = get_event_bus()
    await event_bus.start()

    test_client = TestClient(app)

    with test_client.websocket_connect("/ws/events") as ws:
        # Publish an event
        await event_bus.publish_sync(
            Event(
                type=EventType.PRICE_UPDATE,
                data={"symbol": "BTC/USDT", "price": 50000.0},
            )
        )
        # Give a small window for the event to propagate
        await asyncio.sleep(0.1)

        # Also publish via publish_sync to ensure handler fires
        await event_bus.publish_sync(
            Event(
                type=EventType.SIGNAL_GENERATED,
                data={"symbol": "ETH/USDT", "direction": "long"},
            )
        )

        # Read messages -- we should get at least 1
        msg = ws.receive_json(mode="text")
        assert "type" in msg
        assert "timestamp" in msg
        assert "data" in msg

    await event_bus.stop()


async def test_panic_sets_paused_flag(app):
    """After panic, the pause toggle should show resumed on next call."""
    import keryxflow.api.server as server_module

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=_BASE_URL) as client:
        # Panic sets _paused = True
        await client.post("/api/panic")
        assert server_module._paused is True

        # Next pause toggle should resume
        resp = await client.post("/api/pause")
        assert resp.json()["status"] == "resumed"
        assert server_module._paused is False


async def _drain_event_bus(event_bus) -> None:
    """Process all queued events in the event bus."""
    while not event_bus._queue.empty():
        try:
            event = event_bus._queue.get_nowait()
            await event_bus._dispatch(event)
            event_bus._queue.task_done()
        except asyncio.QueueEmpty:
            break
