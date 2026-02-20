"""Tests for webhook signal ingestion endpoint."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from keryxflow.api.models import WebhookSignalRequest
from keryxflow.api.server import create_app
from keryxflow.api.webhook import _map_to_trading_signal, set_engine
from keryxflow.config import get_settings
from keryxflow.oracle.signals import SignalSource, SignalType
from keryxflow.oracle.technical import SignalStrength


@pytest.fixture
def app():
    """Create a fresh FastAPI app for testing."""
    return create_app()


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def valid_payload():
    """Valid TradingView-style webhook payload."""
    return {
        "symbol": "BTC/USDT",
        "action": "buy",
        "price": 67000.0,
        "stop_loss": 65000.0,
        "take_profit": 71000.0,
        "confidence": 0.85,
        "strategy": "RSI_Oversold",
        "message": "BTC oversold on 4H",
    }


@pytest.fixture
def mock_engine():
    """Create a mock TradingEngine."""
    engine = AsyncMock()
    engine._running = True
    engine._paused = False
    engine.process_webhook_signal = AsyncMock(
        return_value={
            "status": "executed",
            "message": "Signal processed for BTC/USDT",
        }
    )
    return engine


# --- Health Check ---


def test_health_check(client):
    """GET /api/health returns 200."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# --- Request Validation ---


def test_valid_payload_accepted(client, valid_payload):
    """Valid payload returns 200 with 'accepted' status."""
    response = client.post("/api/webhook/signal", json=valid_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"
    assert data["signal_id"]
    assert "BTC/USDT" in data["message"]


def test_missing_symbol_rejected(client, valid_payload):
    """Missing symbol returns 422."""
    del valid_payload["symbol"]
    response = client.post("/api/webhook/signal", json=valid_payload)
    assert response.status_code == 422


def test_missing_action_rejected(client, valid_payload):
    """Missing action returns 422."""
    del valid_payload["action"]
    response = client.post("/api/webhook/signal", json=valid_payload)
    assert response.status_code == 422


def test_missing_price_rejected(client, valid_payload):
    """Missing price returns 422."""
    del valid_payload["price"]
    response = client.post("/api/webhook/signal", json=valid_payload)
    assert response.status_code == 422


def test_invalid_symbol_format_rejected(client, valid_payload):
    """Invalid symbol format returns 422."""
    valid_payload["symbol"] = "BTCUSDT"
    response = client.post("/api/webhook/signal", json=valid_payload)
    assert response.status_code == 422


def test_invalid_symbol_lowercase_rejected(client, valid_payload):
    """Lowercase symbol returns 422."""
    valid_payload["symbol"] = "btc/usdt"
    response = client.post("/api/webhook/signal", json=valid_payload)
    assert response.status_code == 422


def test_invalid_action_rejected(client, valid_payload):
    """Invalid action returns 422."""
    valid_payload["action"] = "hold"
    response = client.post("/api/webhook/signal", json=valid_payload)
    assert response.status_code == 422


def test_price_zero_rejected(client, valid_payload):
    """Price = 0 returns 422."""
    valid_payload["price"] = 0
    response = client.post("/api/webhook/signal", json=valid_payload)
    assert response.status_code == 422


def test_negative_price_rejected(client, valid_payload):
    """Negative price returns 422."""
    valid_payload["price"] = -100.0
    response = client.post("/api/webhook/signal", json=valid_payload)
    assert response.status_code == 422


def test_confidence_out_of_range_rejected(client, valid_payload):
    """Confidence > 1.0 returns 422."""
    valid_payload["confidence"] = 1.5
    response = client.post("/api/webhook/signal", json=valid_payload)
    assert response.status_code == 422


def test_optional_fields_default(client):
    """Minimal payload with only required fields works."""
    payload = {
        "symbol": "ETH/USDT",
        "action": "sell",
        "price": 3500.0,
    }
    response = client.post("/api/webhook/signal", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


def test_close_action_accepted(client):
    """Close action is accepted."""
    payload = {
        "symbol": "BTC/USDT",
        "action": "close",
        "price": 67000.0,
    }
    response = client.post("/api/webhook/signal", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


# --- Authentication ---


def test_auth_required_when_secret_configured(client, valid_payload):
    """Request without secret header is rejected when secret is configured."""
    settings = get_settings()
    with patch.object(
        settings.webhook.secret_token,
        "get_secret_value",
        return_value="my-secret-token",
    ):
        response = client.post("/api/webhook/signal", json=valid_payload)
    assert response.status_code == 401
    assert "Missing" in response.json()["detail"]


def test_wrong_secret_rejected(client, valid_payload):
    """Wrong secret header is rejected."""
    settings = get_settings()
    with patch.object(
        settings.webhook.secret_token,
        "get_secret_value",
        return_value="correct-secret",
    ):
        response = client.post(
            "/api/webhook/signal",
            json=valid_payload,
            headers={"X-Webhook-Secret": "wrong-secret"},
        )
    assert response.status_code == 401
    assert "Invalid" in response.json()["detail"]


def test_correct_secret_accepted(client, valid_payload):
    """Correct secret header is accepted."""
    settings = get_settings()
    with patch.object(
        settings.webhook.secret_token,
        "get_secret_value",
        return_value="my-secret",
    ):
        response = client.post(
            "/api/webhook/signal",
            json=valid_payload,
            headers={"X-Webhook-Secret": "my-secret"},
        )
    assert response.status_code == 200


def test_no_auth_when_secret_empty(client, valid_payload):
    """No auth required when secret is empty string."""
    # Default secret is empty, so this should work without header
    response = client.post("/api/webhook/signal", json=valid_payload)
    assert response.status_code == 200


# --- Signal Mapping ---


def test_buy_maps_to_long():
    """buy action maps to SignalType.LONG."""
    req = WebhookSignalRequest(symbol="BTC/USDT", action="buy", price=67000.0, stop_loss=65000.0)
    signal = _map_to_trading_signal(req)
    assert signal.signal_type == SignalType.LONG
    assert signal.source == SignalSource.WEBHOOK
    assert signal.strength == SignalStrength.STRONG
    assert signal.confidence == 0.75  # default
    assert signal.entry_price == 67000.0
    assert signal.stop_loss == 65000.0
    assert signal.symbol == "BTC/USDT"


def test_sell_maps_to_short():
    """sell action maps to SignalType.SHORT."""
    req = WebhookSignalRequest(symbol="ETH/USDT", action="sell", price=3500.0, confidence=0.9)
    signal = _map_to_trading_signal(req)
    assert signal.signal_type == SignalType.SHORT
    assert signal.confidence == 0.9


def test_close_maps_to_close_long():
    """close action maps to SignalType.CLOSE_LONG."""
    req = WebhookSignalRequest(symbol="BTC/USDT", action="close", price=67000.0)
    signal = _map_to_trading_signal(req)
    assert signal.signal_type == SignalType.CLOSE_LONG


def test_signal_fields_mapped_correctly():
    """All fields are mapped correctly from request to TradingSignal."""
    req = WebhookSignalRequest(
        symbol="SOL/USDT",
        action="buy",
        price=150.0,
        stop_loss=140.0,
        take_profit=170.0,
        confidence=0.88,
        strategy="Breakout",
        message="SOL breaking resistance",
    )
    signal = _map_to_trading_signal(req)
    assert signal.symbol == "SOL/USDT"
    assert signal.entry_price == 150.0
    assert signal.stop_loss == 140.0
    assert signal.take_profit == 170.0
    assert signal.confidence == 0.88
    assert signal.source == SignalSource.WEBHOOK
    assert "SOL breaking resistance" in signal.simple_reason
    assert "Breakout" in signal.technical_reason


# --- Auto-Execute Flow ---


def test_auto_execute_routes_through_engine(client, valid_payload, mock_engine):
    """When auto_execute=True, signal routes through engine."""
    settings = get_settings()
    set_engine(mock_engine)
    try:
        with patch.object(settings.webhook, "auto_execute", True):
            response = client.post("/api/webhook/signal", json=valid_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "executed"
        mock_engine.process_webhook_signal.assert_called_once()
    finally:
        set_engine(None)


def test_auto_execute_missing_stop_loss_rejected(client, mock_engine):
    """Entry signal without stop_loss returns 422 when auto_execute=True."""
    payload = {
        "symbol": "BTC/USDT",
        "action": "buy",
        "price": 67000.0,
    }
    settings = get_settings()
    set_engine(mock_engine)
    try:
        with patch.object(settings.webhook, "auto_execute", True):
            response = client.post("/api/webhook/signal", json=payload)
        assert response.status_code == 422
        assert "stop_loss" in response.json()["detail"]
    finally:
        set_engine(None)


def test_auto_execute_close_without_stop_loss_ok(client, mock_engine):
    """Close signal without stop_loss is OK when auto_execute=True."""
    payload = {
        "symbol": "BTC/USDT",
        "action": "close",
        "price": 67000.0,
    }
    settings = get_settings()
    set_engine(mock_engine)
    try:
        with patch.object(settings.webhook, "auto_execute", True):
            response = client.post("/api/webhook/signal", json=payload)
        assert response.status_code == 200
    finally:
        set_engine(None)


def test_auto_execute_no_engine_returns_error(client, valid_payload):
    """When auto_execute=True but no engine, returns error."""
    settings = get_settings()
    set_engine(None)
    with patch.object(settings.webhook, "auto_execute", True):
        response = client.post("/api/webhook/signal", json=valid_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert "not available" in data["message"]


def test_auto_execute_engine_rejection(client, valid_payload):
    """When engine rejects signal, returns rejection status."""
    engine = AsyncMock()
    engine.process_webhook_signal = AsyncMock(
        return_value={
            "status": "rejected",
            "message": "Position size too large",
            "details": {"reason": "MAX_POSITION_SIZE_PCT exceeded"},
        }
    )
    settings = get_settings()
    set_engine(engine)
    try:
        with patch.object(settings.webhook, "auto_execute", True):
            response = client.post("/api/webhook/signal", json=valid_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected"
    finally:
        set_engine(None)


# --- Non-Execute Flow ---


def test_non_execute_publishes_event_only(client, valid_payload):
    """When auto_execute=False, signal is accepted but no order created."""
    response = client.post("/api/webhook/signal", json=valid_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"
    assert "recorded" in data["message"].lower() or "BTC/USDT" in data["message"]
