"""Perception tools for market data and portfolio state.

These tools are READ-ONLY and do not require guardrail validation.
They allow the agent to perceive the current market state.
"""

from datetime import UTC, datetime
from typing import Any

from keryxflow.agent.tools import (
    BaseTool,
    ToolCategory,
    ToolParameter,
    ToolResult,
    TradingToolkit,
)
from keryxflow.core.logging import get_logger

logger = get_logger(__name__)


class GetCurrentPriceTool(BaseTool):
    """Get the current price for a trading pair."""

    @property
    def name(self) -> str:
        return "get_current_price"

    @property
    def description(self) -> str:
        return (
            "Get the current market price for a cryptocurrency trading pair. "
            "Returns the latest price from the exchange or paper trading engine."
        )

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.PERCEPTION

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="symbol",
                type="string",
                description="Trading pair symbol (e.g., 'BTC/USDT', 'ETH/USDT')",
                required=True,
            ),
        ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        symbol = kwargs["symbol"]

        try:
            from keryxflow.exchange.orders import get_order_manager

            order_manager = get_order_manager()
            await order_manager.initialize()

            # Try to get from paper engine first
            if order_manager.is_paper_mode:
                from keryxflow.exchange.paper import get_paper_engine

                engine = get_paper_engine()
                price = engine.get_price(symbol)

                if price is not None:
                    return ToolResult(
                        success=True,
                        data={
                            "symbol": symbol,
                            "price": price,
                            "timestamp": datetime.now(UTC).isoformat(),
                            "source": "paper_engine",
                        },
                    )

            # Fall back to fetching from exchange
            from keryxflow.exchange.client import get_exchange_client

            client = get_exchange_client()
            ticker = await client.fetch_ticker(symbol)

            return ToolResult(
                success=True,
                data={
                    "symbol": symbol,
                    "price": ticker.get("last", ticker.get("close")),
                    "bid": ticker.get("bid"),
                    "ask": ticker.get("ask"),
                    "volume_24h": ticker.get("quoteVolume"),
                    "change_24h": ticker.get("percentage"),
                    "timestamp": datetime.now(UTC).isoformat(),
                    "source": "exchange",
                },
            )

        except Exception as e:
            logger.exception("get_current_price_failed", symbol=symbol)
            return ToolResult(
                success=False,
                error=f"Failed to get price for {symbol}: {str(e)}",
            )


class GetOHLCVTool(BaseTool):
    """Get OHLCV (candlestick) data for a trading pair."""

    @property
    def name(self) -> str:
        return "get_ohlcv"

    @property
    def description(self) -> str:
        return (
            "Get historical OHLCV (Open, High, Low, Close, Volume) candlestick data "
            "for a trading pair. Useful for technical analysis."
        )

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.PERCEPTION

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="symbol",
                type="string",
                description="Trading pair symbol (e.g., 'BTC/USDT')",
                required=True,
            ),
            ToolParameter(
                name="timeframe",
                type="string",
                description="Candlestick timeframe",
                required=False,
                default="1h",
                enum=["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
            ),
            ToolParameter(
                name="limit",
                type="integer",
                description="Number of candles to fetch (max 500)",
                required=False,
                default=100,
            ),
        ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        symbol = kwargs["symbol"]
        timeframe = kwargs.get("timeframe", "1h")
        limit = min(kwargs.get("limit", 100), 500)

        try:
            from keryxflow.exchange.client import get_exchange_client

            client = get_exchange_client()
            ohlcv = await client.fetch_ohlcv(symbol, timeframe, limit=limit)

            # Format the data
            candles = []
            for candle in ohlcv:
                candles.append(
                    {
                        "timestamp": datetime.fromtimestamp(candle[0] / 1000, tz=UTC).isoformat(),
                        "open": candle[1],
                        "high": candle[2],
                        "low": candle[3],
                        "close": candle[4],
                        "volume": candle[5],
                    }
                )

            return ToolResult(
                success=True,
                data={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "candles": candles,
                    "count": len(candles),
                },
            )

        except Exception as e:
            logger.exception("get_ohlcv_failed", symbol=symbol)
            return ToolResult(
                success=False,
                error=f"Failed to get OHLCV for {symbol}: {str(e)}",
            )


class GetOrderBookTool(BaseTool):
    """Get order book depth for a trading pair."""

    @property
    def name(self) -> str:
        return "get_order_book"

    @property
    def description(self) -> str:
        return (
            "Get the current order book (bids and asks) for a trading pair. "
            "Shows market depth and liquidity."
        )

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.PERCEPTION

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="symbol",
                type="string",
                description="Trading pair symbol (e.g., 'BTC/USDT')",
                required=True,
            ),
            ToolParameter(
                name="limit",
                type="integer",
                description="Number of price levels to fetch (max 100)",
                required=False,
                default=20,
            ),
        ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        symbol = kwargs["symbol"]
        limit = min(kwargs.get("limit", 20), 100)

        try:
            from keryxflow.exchange.client import get_exchange_client

            client = get_exchange_client()
            order_book = await client.fetch_order_book(symbol, limit=limit)

            # Calculate metrics
            bids = order_book.get("bids", [])[:limit]
            asks = order_book.get("asks", [])[:limit]

            total_bid_volume = sum(b[1] for b in bids) if bids else 0
            total_ask_volume = sum(a[1] for a in asks) if asks else 0

            best_bid = bids[0][0] if bids else None
            best_ask = asks[0][0] if asks else None
            spread = (best_ask - best_bid) if best_bid and best_ask else None
            spread_pct = (spread / best_bid * 100) if spread and best_bid else None

            return ToolResult(
                success=True,
                data={
                    "symbol": symbol,
                    "bids": [{"price": b[0], "quantity": b[1]} for b in bids],
                    "asks": [{"price": a[0], "quantity": a[1]} for a in asks],
                    "best_bid": best_bid,
                    "best_ask": best_ask,
                    "spread": spread,
                    "spread_pct": spread_pct,
                    "total_bid_volume": total_bid_volume,
                    "total_ask_volume": total_ask_volume,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

        except Exception as e:
            logger.exception("get_order_book_failed", symbol=symbol)
            return ToolResult(
                success=False,
                error=f"Failed to get order book for {symbol}: {str(e)}",
            )


class GetPortfolioStateTool(BaseTool):
    """Get the current portfolio state including positions and exposure."""

    @property
    def name(self) -> str:
        return "get_portfolio_state"

    @property
    def description(self) -> str:
        return (
            "Get the current portfolio state including total value, cash, "
            "open positions, exposure, and risk metrics."
        )

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.PERCEPTION

    @property
    def parameters(self) -> list[ToolParameter]:
        return []  # No parameters needed

    async def execute(self, **kwargs: Any) -> ToolResult:  # noqa: ARG002
        try:
            from keryxflow.aegis.risk import get_risk_manager

            risk_manager = get_risk_manager()
            portfolio = risk_manager.portfolio_state

            # Get positions data
            positions_data = []
            for pos in portfolio.positions:
                positions_data.append(
                    {
                        "symbol": pos.symbol,
                        "side": pos.side,
                        "quantity": float(pos.quantity),
                        "entry_price": float(pos.entry_price),
                        "current_price": float(pos.current_price),
                        "unrealized_pnl": float(pos.unrealized_pnl),
                        "unrealized_pnl_pct": float(pos.unrealized_pnl_pct) * 100,
                        "stop_loss": float(pos.stop_loss) if pos.stop_loss else None,
                        "take_profit": float(pos.take_profit) if pos.take_profit else None,
                    }
                )

            return ToolResult(
                success=True,
                data={
                    "total_value": float(portfolio.total_value),
                    "cash_available": float(portfolio.cash_available),
                    "total_exposure": float(portfolio.total_exposure),
                    "exposure_pct": float(portfolio.exposure_pct) * 100,
                    "cash_reserve_pct": float(portfolio.cash_reserve_pct) * 100,
                    "unrealized_pnl": float(portfolio.unrealized_pnl),
                    "daily_pnl": float(portfolio.daily_pnl),
                    "drawdown_pct": float(portfolio.drawdown_pct) * 100,
                    "position_count": portfolio.position_count,
                    "positions": positions_data,
                    "consecutive_losses": portfolio.consecutive_losses,
                    "trades_today": portfolio.trades_today,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

        except Exception as e:
            logger.exception("get_portfolio_state_failed")
            return ToolResult(
                success=False,
                error=f"Failed to get portfolio state: {str(e)}",
            )


class GetBalanceTool(BaseTool):
    """Get the current account balance."""

    @property
    def name(self) -> str:
        return "get_balance"

    @property
    def description(self) -> str:
        return (
            "Get the current account balance showing total, free (available), "
            "and used (in orders/positions) amounts for each currency."
        )

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.PERCEPTION

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="currency",
                type="string",
                description="Specific currency to get balance for (optional, returns all if not specified)",
                required=False,
            ),
        ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        currency = kwargs.get("currency")

        try:
            from keryxflow.exchange.orders import get_order_manager

            order_manager = get_order_manager()
            await order_manager.initialize()
            balance = await order_manager.get_balance()

            if currency:
                total = balance.get("total", {}).get(currency, 0)
                free = balance.get("free", {}).get(currency, 0)
                used = balance.get("used", {}).get(currency, 0)

                return ToolResult(
                    success=True,
                    data={
                        "currency": currency,
                        "total": total,
                        "free": free,
                        "used": used,
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                )
            else:
                return ToolResult(
                    success=True,
                    data={
                        "total": balance.get("total", {}),
                        "free": balance.get("free", {}),
                        "used": balance.get("used", {}),
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                )

        except Exception as e:
            logger.exception("get_balance_failed")
            return ToolResult(
                success=False,
                error=f"Failed to get balance: {str(e)}",
            )


class GetPositionsTool(BaseTool):
    """Get all open positions."""

    @property
    def name(self) -> str:
        return "get_positions"

    @property
    def description(self) -> str:
        return (
            "Get all currently open trading positions with their entry prices, "
            "current prices, unrealized P&L, and stop/take profit levels."
        )

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.PERCEPTION

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="symbol",
                type="string",
                description="Filter by specific symbol (optional)",
                required=False,
            ),
        ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        symbol = kwargs.get("symbol")

        try:
            from keryxflow.exchange.paper import get_paper_engine

            engine = get_paper_engine()
            await engine.initialize()

            if symbol:
                position = await engine.get_position(symbol)
                positions = [position] if position else []
            else:
                positions = await engine.get_positions()

            positions_data = []
            for pos in positions:
                positions_data.append(
                    {
                        "id": pos.id,
                        "symbol": pos.symbol,
                        "side": pos.side.value,
                        "quantity": pos.quantity,
                        "entry_price": pos.entry_price,
                        "current_price": pos.current_price,
                        "unrealized_pnl": pos.unrealized_pnl,
                        "unrealized_pnl_pct": pos.unrealized_pnl_percentage,
                        "stop_loss": pos.stop_loss,
                        "take_profit": pos.take_profit,
                        "opened_at": pos.opened_at.isoformat() if pos.opened_at else None,
                    }
                )

            return ToolResult(
                success=True,
                data={
                    "positions": positions_data,
                    "count": len(positions_data),
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

        except Exception as e:
            logger.exception("get_positions_failed")
            return ToolResult(
                success=False,
                error=f"Failed to get positions: {str(e)}",
            )


class GetOpenOrdersTool(BaseTool):
    """Get all open (pending) orders."""

    @property
    def name(self) -> str:
        return "get_open_orders"

    @property
    def description(self) -> str:
        return "Get all open (pending) orders that have not yet been filled."

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.PERCEPTION

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="symbol",
                type="string",
                description="Filter by specific symbol (optional)",
                required=False,
            ),
        ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        symbol = kwargs.get("symbol")

        try:
            from keryxflow.exchange.orders import get_order_manager

            order_manager = get_order_manager()
            await order_manager.initialize()
            orders = await order_manager.get_open_orders(symbol)

            orders_data = []
            for order in orders:
                orders_data.append(
                    {
                        "id": order.id,
                        "symbol": order.symbol,
                        "type": order.order_type.value,
                        "side": order.side,
                        "amount": order.amount,
                        "price": order.price,
                        "filled": order.filled,
                        "remaining": order.remaining,
                        "status": order.status.value,
                        "created_at": order.created_at.isoformat() if order.created_at else None,
                    }
                )

            return ToolResult(
                success=True,
                data={
                    "orders": orders_data,
                    "count": len(orders_data),
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

        except Exception as e:
            logger.exception("get_open_orders_failed")
            return ToolResult(
                success=False,
                error=f"Failed to get open orders: {str(e)}",
            )


def register_perception_tools(toolkit: TradingToolkit) -> None:
    """Register all perception tools with the toolkit.

    Args:
        toolkit: The toolkit to register tools with
    """
    tools = [
        GetCurrentPriceTool(),
        GetOHLCVTool(),
        GetOrderBookTool(),
        GetPortfolioStateTool(),
        GetBalanceTool(),
        GetPositionsTool(),
        GetOpenOrdersTool(),
    ]

    for tool in tools:
        toolkit.register(tool)

    logger.info("perception_tools_registered", count=len(tools))
