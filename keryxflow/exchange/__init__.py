"""Exchange - Connectivity layer for exchanges and paper trading."""

from keryxflow.exchange.adapter import ExchangeAdapter
from keryxflow.exchange.client import (
    ExchangeClient,
    get_exchange_adapter,
    get_exchange_client,
)
from keryxflow.exchange.kraken import KrakenAdapter, get_kraken_client
from keryxflow.exchange.okx import OKXAdapter, get_okx_client
from keryxflow.exchange.orders import Order, OrderManager, OrderStatus, OrderType, get_order_manager
from keryxflow.exchange.paper import PaperTradingEngine, get_paper_engine

__all__ = [
    # ABC
    "ExchangeAdapter",
    # Binance
    "ExchangeClient",
    "get_exchange_client",
    # Kraken
    "KrakenAdapter",
    "get_kraken_client",
    # OKX
    "OKXAdapter",
    "get_okx_client",
    # Factory
    "get_exchange_adapter",
    # Paper trading
    "PaperTradingEngine",
    "get_paper_engine",
    # Order management
    "Order",
    "OrderManager",
    "OrderStatus",
    "OrderType",
    "get_order_manager",
]
