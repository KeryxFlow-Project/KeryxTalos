"""Exchange - Connectivity layer for exchanges and paper trading."""

from keryxflow.exchange.adapter import ExchangeAdapter
from keryxflow.exchange.bybit import BybitClient, get_bybit_client
from keryxflow.exchange.client import ExchangeClient, get_exchange_client

__all__ = [
    "ExchangeAdapter",
    "ExchangeClient",
    "BybitClient",
    "get_exchange_client",
    "get_bybit_client",
    "get_exchange_adapter",
]


def get_exchange_adapter(sandbox: bool = True) -> ExchangeAdapter:
    """Get the appropriate exchange adapter based on settings.

    Reads ``settings.system.exchange`` and returns the matching adapter singleton.

    Args:
        sandbox: Whether to use sandbox/testnet mode

    Returns:
        An ExchangeAdapter instance for the configured exchange.

    Raises:
        ValueError: If the configured exchange is not supported.
    """
    from keryxflow.config import get_settings

    exchange_name = get_settings().system.exchange.lower()

    if exchange_name == "binance":
        return get_exchange_client(sandbox=sandbox)
    elif exchange_name == "bybit":
        return get_bybit_client(sandbox=sandbox)
    else:
        raise ValueError(
            f"Unsupported exchange: '{exchange_name}'. Supported exchanges: binance, bybit"
        )
