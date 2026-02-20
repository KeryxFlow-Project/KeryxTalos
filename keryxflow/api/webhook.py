"""FastAPI router for webhook signal ingestion."""

from __future__ import annotations

import hmac
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Header, HTTPException

from keryxflow.api.models import WebhookSignalRequest, WebhookSignalResponse
from keryxflow.config import get_settings
from keryxflow.core.events import Event, EventType, get_event_bus
from keryxflow.core.logging import get_logger
from keryxflow.oracle.signals import (
    SignalSource,
    SignalType,
    TradingSignal,
)
from keryxflow.oracle.technical import SignalStrength

if TYPE_CHECKING:
    from keryxflow.core.engine import TradingEngine

logger = get_logger(__name__)

router = APIRouter()

# Module-level engine reference, set by WebhookServer
_engine: TradingEngine | None = None


def set_engine(engine: TradingEngine | None) -> None:
    """Set the engine reference for webhook signal routing."""
    global _engine
    _engine = engine


def _verify_secret(secret_header: str | None) -> None:
    """Verify the webhook secret token. Raises HTTPException on failure."""
    settings = get_settings()
    configured_secret = settings.webhook.secret_token.get_secret_value()

    if not configured_secret:
        return

    if not secret_header:
        raise HTTPException(status_code=401, detail="Missing X-Webhook-Secret header")

    if not hmac.compare_digest(secret_header, configured_secret):
        raise HTTPException(status_code=401, detail="Invalid webhook secret")


def _map_to_trading_signal(req: WebhookSignalRequest) -> TradingSignal:
    """Convert a webhook request to a TradingSignal."""
    action_map: dict[str, SignalType] = {
        "buy": SignalType.LONG,
        "sell": SignalType.SHORT,
        "close": SignalType.CLOSE_LONG,
    }
    signal_type = action_map[req.action]

    return TradingSignal(
        symbol=req.symbol,
        signal_type=signal_type,
        strength=SignalStrength.STRONG,
        confidence=req.confidence,
        source=SignalSource.WEBHOOK,
        timestamp=datetime.now(UTC),
        entry_price=req.price,
        stop_loss=req.stop_loss,
        take_profit=req.take_profit,
        simple_reason=req.message or f"Webhook {req.action} signal",
        technical_reason=f"Webhook signal: {req.action} {req.symbol} @ {req.price}"
        + (f" | strategy: {req.strategy}" if req.strategy else ""),
    )


@router.post("/webhook/signal", response_model=WebhookSignalResponse)
async def receive_webhook_signal(
    payload: WebhookSignalRequest,
    x_webhook_secret: str | None = Header(default=None),
) -> WebhookSignalResponse:
    """Receive a trading signal via webhook (e.g., from TradingView)."""
    _verify_secret(x_webhook_secret)

    signal_id = str(uuid.uuid4())
    settings = get_settings()
    event_bus = get_event_bus()

    signal = _map_to_trading_signal(payload)

    # Publish observability event
    await event_bus.publish(
        Event(
            type=EventType.WEBHOOK_SIGNAL_RECEIVED,
            data={
                "signal_id": signal_id,
                "symbol": payload.symbol,
                "action": payload.action,
                "price": payload.price,
                "source": "webhook",
            },
        )
    )

    logger.info(
        "webhook_signal_received",
        signal_id=signal_id,
        symbol=payload.symbol,
        action=payload.action,
        price=payload.price,
    )

    if not settings.webhook.auto_execute:
        # Publish signal event for logging/display only
        await event_bus.publish(Event(type=EventType.SIGNAL_GENERATED, data=signal.to_dict()))
        return WebhookSignalResponse(
            status="accepted",
            signal_id=signal_id,
            message=f"Signal recorded for {payload.symbol} ({payload.action})",
        )

    # Auto-execute: validate and route through engine
    if _engine is None:
        return WebhookSignalResponse(
            status="error",
            signal_id=signal_id,
            message="Trading engine not available",
        )

    # Entry signals (buy/sell) require stop_loss for position sizing
    if payload.action in ("buy", "sell") and payload.stop_loss is None:
        raise HTTPException(
            status_code=422,
            detail="stop_loss is required for entry signals when auto_execute is enabled",
        )

    try:
        result = await _engine.process_webhook_signal(signal)
    except Exception as e:
        logger.error("webhook_signal_processing_failed", signal_id=signal_id, error=str(e))
        return WebhookSignalResponse(
            status="error",
            signal_id=signal_id,
            message=f"Signal processing failed: {e}",
        )

    return WebhookSignalResponse(
        status=result.get("status", "executed"),
        signal_id=signal_id,
        message=result.get("message", "Signal processed"),
        details=result.get("details"),
    )
