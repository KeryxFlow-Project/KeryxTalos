"""Tests for the webhook signal ingestion endpoint."""

import asyncio
import os

import pytest
from httpx import ASGITransport, AsyncClient

from keryxflow.api.server import create_app
from keryxflow.core.events import Event, EventType, get_event_bus

_BASE_URL = "http://test"


@pytest.fixture
def app():
    """Create a fresh FastAPI app for each test."""
    return create_app()


@pytest.fixture
async def client(app):
    """Async HTTP client wired to the ASGI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=_BASE_URL) as c:
        yield c


@pytest.fixture
def _set_webhook_secret():
    """Set a webhook secret for auth tests, cleaning up after."""
    import keryxflow.config as config_module

    os.environ["KERYXFLOW_API_WEBHOOK_SECRET"] = "webhook-secret-123"
    config_module._settings = None
    yield
    os.environ.pop("KERYXFLOW_API_WEBHOOK_SECRET", None)
    config_module._settings = None


async def _drain_event_bus(event_bus) -> None:
    """Process all queued events in the event bus."""
    while not event_bus._queue.empty():
        try:
            event = event_bus._queue.get_nowait()
            await event_bus._dispatch(event)
            event_bus._queue.task_done()
        except asyncio.QueueEmpty:
            break


# -- Successful signal submission ----------------------------------------------


async def test_webhook_signal_valid_payload(client):
    """POST /api/webhook/signal with valid payload returns 200."""
    resp = await client.post(
        "/api/webhook/signal",
        json={"symbol": "BTC/USDT", "side": "buy"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "received"
    assert body["symbol"] == "BTC/USDT"
    assert body["side"] == "buy"


async def test_webhook_signal_publishes_event(client):
    """POST /api/webhook/signal publishes a SIGNAL_GENERATED event."""
    event_bus = get_event_bus()
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    event_bus.subscribe(EventType.SIGNAL_GENERATED, handler)

    await client.post(
        "/api/webhook/signal",
        json={"symbol": "ETH/USDT", "side": "sell", "source": "tradingview"},
    )

    await _drain_event_bus(event_bus)

    assert len(received) == 1
    assert received[0].type == EventType.SIGNAL_GENERATED
    assert received[0].data["symbol"] == "ETH/USDT"
    assert received[0].data["direction"] == "short"
    assert received[0].data["source"] == "webhook:tradingview"


async def test_webhook_signal_buy_maps_to_long(client):
    """Side 'buy' maps to direction 'long' in the event."""
    event_bus = get_event_bus()
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    event_bus.subscribe(EventType.SIGNAL_GENERATED, handler)

    await client.post(
        "/api/webhook/signal",
        json={"symbol": "BTC/USDT", "side": "buy"},
    )
    await _drain_event_bus(event_bus)

    assert received[0].data["direction"] == "long"


# -- Optional fields -----------------------------------------------------------


async def test_webhook_signal_optional_fields(client):
    """Optional fields (price, quantity, source, strategy) are passed through."""
    event_bus = get_event_bus()
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    event_bus.subscribe(EventType.SIGNAL_GENERATED, handler)

    await client.post(
        "/api/webhook/signal",
        json={
            "symbol": "BTC/USDT",
            "side": "buy",
            "price": 45000.0,
            "quantity": 0.1,
            "source": "custom_bot",
            "strategy": "My Strategy",
        },
    )
    await _drain_event_bus(event_bus)

    assert len(received) == 1
    assert received[0].data["source"] == "webhook:custom_bot"
    assert "price=45000.0" in received[0].data["context"]
    assert "quantity=0.1" in received[0].data["context"]
    assert "strategy=My Strategy" in received[0].data["context"]


# -- Validation errors ---------------------------------------------------------


async def test_webhook_signal_missing_symbol(client):
    """Missing 'symbol' returns 422."""
    resp = await client.post(
        "/api/webhook/signal",
        json={"side": "buy"},
    )
    assert resp.status_code == 422


async def test_webhook_signal_missing_side(client):
    """Missing 'side' returns 422."""
    resp = await client.post(
        "/api/webhook/signal",
        json={"symbol": "BTC/USDT"},
    )
    assert resp.status_code == 422


async def test_webhook_signal_invalid_side(client):
    """Invalid 'side' value returns 422."""
    resp = await client.post(
        "/api/webhook/signal",
        json={"symbol": "BTC/USDT", "side": "hold"},
    )
    assert resp.status_code == 422


# -- Webhook secret auth -------------------------------------------------------


@pytest.mark.usefixtures("_set_webhook_secret")
async def test_webhook_rejects_missing_secret(client):
    """Requests without X-Webhook-Secret header are rejected when secret is set."""
    resp = await client.post(
        "/api/webhook/signal",
        json={"symbol": "BTC/USDT", "side": "buy"},
    )
    assert resp.status_code == 401


@pytest.mark.usefixtures("_set_webhook_secret")
async def test_webhook_rejects_wrong_secret(client):
    """Requests with wrong secret are rejected."""
    resp = await client.post(
        "/api/webhook/signal",
        json={"symbol": "BTC/USDT", "side": "buy"},
        headers={"X-Webhook-Secret": "wrong-secret"},
    )
    assert resp.status_code == 401


@pytest.mark.usefixtures("_set_webhook_secret")
async def test_webhook_accepts_correct_secret(client):
    """Requests with correct secret succeed."""
    resp = await client.post(
        "/api/webhook/signal",
        json={"symbol": "BTC/USDT", "side": "buy"},
        headers={"X-Webhook-Secret": "webhook-secret-123"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "received"


async def test_webhook_auth_skipped_when_no_secret(client):
    """Auth is skipped when no webhook secret is configured."""
    resp = await client.post(
        "/api/webhook/signal",
        json={"symbol": "BTC/USDT", "side": "buy"},
    )
    assert resp.status_code == 200
