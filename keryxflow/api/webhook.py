"""Webhook endpoint for receiving trading signals from TradingView and other sources."""

from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from keryxflow.config import get_settings
from keryxflow.core.events import get_event_bus, signal_event
from keryxflow.core.logging import get_logger

logger = get_logger(__name__)


class WebhookSignalPayload(BaseModel):
    """Payload for incoming webhook trading signals."""

    symbol: str = Field(..., min_length=1, description="Trading pair, e.g. BTC/USDT")
    side: Literal["buy", "sell"] = Field(..., description="Trade side: buy or sell")
    price: float | None = Field(default=None, gt=0, description="Signal price")
    quantity: float | None = Field(default=None, gt=0, description="Trade quantity")
    source: str = Field(default="tradingview", description="Signal source identifier")
    strategy: str | None = Field(default=None, description="Strategy name")


async def verify_webhook_secret(
    x_webhook_secret: str | None = Header(default=None),
) -> None:
    """Verify the webhook secret header against the configured secret.

    If no secret is configured (empty string), authentication is skipped.
    """
    settings = get_settings()
    secret = settings.api.webhook_secret

    if not secret:
        return

    if x_webhook_secret is None or x_webhook_secret != secret:
        raise HTTPException(status_code=401, detail="Invalid or missing webhook secret")


webhook_router = APIRouter(
    prefix="/api/webhook",
    dependencies=[Depends(verify_webhook_secret)],
)


@webhook_router.post("/signal")
async def receive_signal(payload: WebhookSignalPayload) -> dict[str, Any]:
    """Receive a trading signal from an external source and publish it to the event bus."""
    direction = "long" if payload.side == "buy" else "short"

    context_parts = []
    if payload.price is not None:
        context_parts.append(f"price={payload.price}")
    if payload.quantity is not None:
        context_parts.append(f"quantity={payload.quantity}")
    if payload.strategy:
        context_parts.append(f"strategy={payload.strategy}")
    context = ", ".join(context_parts) if context_parts else None

    event = signal_event(
        symbol=payload.symbol,
        direction=direction,
        strength=1.0,
        source=f"webhook:{payload.source}",
        context=context,
    )

    event_bus = get_event_bus()
    await event_bus.publish(event)

    logger.info(
        "webhook_signal_received",
        symbol=payload.symbol,
        side=payload.side,
        source=payload.source,
    )

    return {
        "status": "received",
        "symbol": payload.symbol,
        "side": payload.side,
    }
