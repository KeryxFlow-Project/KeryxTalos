"""Pydantic v2 request/response models for webhook signal ingestion."""

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class WebhookSignalRequest(BaseModel):
    """TradingView-compatible webhook signal payload."""

    symbol: str
    action: Literal["buy", "sell", "close"]
    price: float = Field(gt=0)
    stop_loss: float | None = Field(default=None, gt=0)
    take_profit: float | None = Field(default=None, gt=0)
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    strategy: str = ""
    message: str = ""
    timestamp: str | None = None

    @field_validator("symbol")
    @classmethod
    def validate_symbol_format(cls, v: str) -> str:
        """Validate symbol matches XXX/YYY format."""
        if not re.match(r"^[A-Z0-9]+/[A-Z0-9]+$", v):
            msg = f"Symbol must match 'XXX/YYY' format (e.g., 'BTC/USDT'), got '{v}'"
            raise ValueError(msg)
        return v


class WebhookSignalResponse(BaseModel):
    """Structured response for webhook signal processing."""

    status: Literal["accepted", "rejected", "executed", "error"]
    signal_id: str
    message: str
    details: dict[str, Any] | None = None
