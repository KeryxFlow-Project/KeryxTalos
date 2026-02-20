"""Execution tools for order management.

THESE TOOLS ARE GUARDED and require validation through GuardrailEnforcer
before execution. They modify portfolio state and place real/paper orders.
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


class PlaceOrderTool(BaseTool):
    """Place a market or limit order.

    This tool is GUARDED and will validate against guardrails before execution.
    """

    @property
    def name(self) -> str:
        return "place_order"

    @property
    def description(self) -> str:
        return (
            "Place a buy or sell order for a trading pair. "
            "Orders are validated against risk guardrails before execution. "
            "For safety, always use a stop loss."
        )

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.EXECUTION

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
                name="side",
                type="string",
                description="Order side",
                required=True,
                enum=["buy", "sell"],
            ),
            ToolParameter(
                name="quantity",
                type="number",
                description="Quantity to buy/sell in base currency",
                required=True,
            ),
            ToolParameter(
                name="order_type",
                type="string",
                description="Order type",
                required=False,
                default="market",
                enum=["market", "limit"],
            ),
            ToolParameter(
                name="price",
                type="number",
                description="Limit price (required for limit orders)",
                required=False,
            ),
            ToolParameter(
                name="stop_loss",
                type="number",
                description="Stop loss price (strongly recommended)",
                required=False,
            ),
            ToolParameter(
                name="take_profit",
                type="number",
                description="Take profit price (optional)",
                required=False,
            ),
        ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        symbol = kwargs["symbol"]
        side = kwargs["side"]
        quantity = kwargs["quantity"]
        order_type = kwargs.get("order_type", "market")
        price = kwargs.get("price")
        stop_loss = kwargs.get("stop_loss")
        take_profit = kwargs.get("take_profit")

        # Validate limit order has price
        if order_type == "limit" and price is None:
            return ToolResult(
                success=False,
                error="Limit orders require a price parameter",
            )

        try:
            # Get current price if not provided
            if price is None:
                from keryxflow.exchange.orders import get_order_manager

                order_manager = get_order_manager()
                await order_manager.initialize()

                # Get current price from paper engine or fetch it
                if order_manager.is_paper_mode:
                    from keryxflow.exchange.paper import get_paper_engine

                    engine = get_paper_engine()
                    price = engine.get_price(symbol)

                if price is None:
                    from keryxflow.exchange import get_exchange_adapter

                    client = get_exchange_adapter()
                    ticker = await client.fetch_ticker(symbol)
                    price = ticker.get("last", ticker.get("close"))

            if price is None:
                return ToolResult(
                    success=False,
                    error=f"Could not determine current price for {symbol}",
                )

            # Validate against guardrails
            from keryxflow.aegis.guardrails import get_guardrail_enforcer
            from keryxflow.aegis.risk import get_risk_manager

            risk_manager = get_risk_manager()
            enforcer = get_guardrail_enforcer()

            guardrail_result = enforcer.validate_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                entry_price=price,
                stop_loss=stop_loss,
                portfolio=risk_manager.portfolio_state,
            )

            if not guardrail_result.allowed:
                logger.warning(
                    "order_blocked_by_guardrails",
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    violation=guardrail_result.violation.value
                    if guardrail_result.violation
                    else None,
                    message=guardrail_result.message,
                )
                return ToolResult(
                    success=False,
                    error=f"Order blocked by guardrails: {guardrail_result.message}",
                    metadata={
                        "violation": guardrail_result.violation.value
                        if guardrail_result.violation
                        else None,
                        "details": guardrail_result.details,
                    },
                )

            # Validate against risk manager
            from keryxflow.aegis.risk import OrderRequest

            order_request = OrderRequest(
                symbol=symbol,
                side=side,
                quantity=quantity,
                entry_price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )

            approval = risk_manager.approve_order(order_request)

            if not approval.approved:
                logger.warning(
                    "order_rejected_by_risk",
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    reason=approval.reason.value if approval.reason else None,
                )
                return ToolResult(
                    success=False,
                    error=f"Order rejected by risk manager: {approval.simple_message}",
                    metadata={
                        "reason": approval.reason.value if approval.reason else None,
                        "suggested_quantity": approval.suggested_quantity,
                        "suggested_stop_loss": approval.suggested_stop_loss,
                    },
                )

            # Execute the order
            from keryxflow.exchange.orders import get_order_manager

            order_manager = get_order_manager()
            await order_manager.initialize()

            if order_type == "market":
                order = await order_manager.place_market_order(
                    symbol=symbol,
                    side=side,
                    amount=quantity,
                )
            else:
                order = await order_manager.place_limit_order(
                    symbol=symbol,
                    side=side,
                    amount=quantity,
                    price=price,
                )

            # If market order filled, open position with stop/take profit
            if order.status.value == "filled" and order_manager.is_paper_mode:
                from keryxflow.exchange.paper import get_paper_engine

                engine = get_paper_engine()
                await engine.open_position(
                    symbol=symbol,
                    side=side,
                    amount=quantity,
                    entry_price=order.average_price or price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                )

                # Update portfolio state
                risk_manager.add_position_to_portfolio(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    entry_price=order.average_price or price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                )

            logger.info(
                "order_placed",
                order_id=order.id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=order.average_price or price,
                status=order.status.value,
            )

            return ToolResult(
                success=True,
                data={
                    "order_id": order.id,
                    "symbol": symbol,
                    "side": side,
                    "type": order_type,
                    "quantity": quantity,
                    "price": order.average_price or price,
                    "status": order.status.value,
                    "filled": order.filled,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

        except Exception as e:
            logger.exception("place_order_failed", symbol=symbol)
            return ToolResult(
                success=False,
                error=f"Failed to place order: {str(e)}",
            )


class ClosePositionTool(BaseTool):
    """Close an open position.

    This tool is GUARDED.
    """

    @property
    def name(self) -> str:
        return "close_position"

    @property
    def description(self) -> str:
        return (
            "Close an open trading position. "
            "This will sell all holdings for the specified symbol "
            "at the current market price."
        )

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.EXECUTION

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="symbol",
                type="string",
                description="Trading pair symbol to close position for",
                required=True,
            ),
            ToolParameter(
                name="reason",
                type="string",
                description="Reason for closing the position (for logging)",
                required=False,
            ),
        ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        symbol = kwargs["symbol"]
        reason = kwargs.get("reason", "Manual close via agent")

        try:
            from keryxflow.exchange.paper import get_paper_engine

            engine = get_paper_engine()
            await engine.initialize()

            # Check if position exists
            position = await engine.get_position(symbol)
            if position is None:
                return ToolResult(
                    success=False,
                    error=f"No open position for {symbol}",
                )

            # Get current price
            current_price = engine.get_price(symbol) or position.current_price

            # Close the position
            result = await engine.close_position(symbol, current_price)

            if result is None:
                return ToolResult(
                    success=False,
                    error=f"Failed to close position for {symbol}",
                )

            # Update portfolio state
            from keryxflow.aegis.risk import get_risk_manager

            risk_manager = get_risk_manager()
            risk_manager.close_position_in_portfolio(symbol, current_price)

            logger.info(
                "position_closed",
                symbol=symbol,
                exit_price=current_price,
                pnl=result.get("pnl"),
                reason=reason,
            )

            return ToolResult(
                success=True,
                data={
                    "symbol": symbol,
                    "exit_price": current_price,
                    "quantity": result.get("quantity"),
                    "pnl": result.get("pnl"),
                    "pnl_percentage": result.get("pnl_percentage"),
                    "reason": reason,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

        except Exception as e:
            logger.exception("close_position_failed", symbol=symbol)
            return ToolResult(
                success=False,
                error=f"Failed to close position: {str(e)}",
            )


class SetStopLossTool(BaseTool):
    """Update stop loss for an open position.

    This tool is GUARDED.
    """

    @property
    def name(self) -> str:
        return "set_stop_loss"

    @property
    def description(self) -> str:
        return (
            "Update the stop loss price for an open position. "
            "Stop loss orders automatically close the position if price falls below (for longs) "
            "or rises above (for shorts) the specified level."
        )

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.EXECUTION

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="symbol",
                type="string",
                description="Trading pair symbol",
                required=True,
            ),
            ToolParameter(
                name="stop_loss",
                type="number",
                description="New stop loss price",
                required=True,
            ),
        ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        symbol = kwargs["symbol"]
        stop_loss = kwargs["stop_loss"]

        try:
            from keryxflow.exchange.paper import get_paper_engine

            engine = get_paper_engine()
            await engine.initialize()

            # Check if position exists
            position = await engine.get_position(symbol)
            if position is None:
                return ToolResult(
                    success=False,
                    error=f"No open position for {symbol}",
                )

            # Validate stop loss direction
            if position.side.value == "buy":
                # Long position - stop must be below entry
                if stop_loss >= position.entry_price:
                    return ToolResult(
                        success=False,
                        error=f"Stop loss ({stop_loss}) must be below entry price ({position.entry_price}) for long positions",
                    )
            else:
                # Short position - stop must be above entry
                if stop_loss <= position.entry_price:
                    return ToolResult(
                        success=False,
                        error=f"Stop loss ({stop_loss}) must be above entry price ({position.entry_price}) for short positions",
                    )

            # Update the position stop loss in database
            from keryxflow.core.database import get_session_factory
            from keryxflow.core.models import Position as PositionModel

            async_session = get_session_factory()
            async with async_session() as session:
                from sqlmodel import select

                result = await session.execute(
                    select(PositionModel).where(PositionModel.symbol == symbol)
                )
                db_position = result.scalar_one_or_none()

                if db_position:
                    old_stop = db_position.stop_loss
                    db_position.stop_loss = stop_loss
                    await session.commit()

            logger.info(
                "stop_loss_updated",
                symbol=symbol,
                old_stop=old_stop,
                new_stop=stop_loss,
            )

            return ToolResult(
                success=True,
                data={
                    "symbol": symbol,
                    "old_stop_loss": old_stop,
                    "new_stop_loss": stop_loss,
                    "entry_price": position.entry_price,
                    "current_price": position.current_price,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

        except Exception as e:
            logger.exception("set_stop_loss_failed", symbol=symbol)
            return ToolResult(
                success=False,
                error=f"Failed to set stop loss: {str(e)}",
            )


class SetTakeProfitTool(BaseTool):
    """Update take profit for an open position.

    This tool is GUARDED.
    """

    @property
    def name(self) -> str:
        return "set_take_profit"

    @property
    def description(self) -> str:
        return (
            "Update the take profit price for an open position. "
            "Take profit orders automatically close the position when price reaches "
            "the target level to lock in profits."
        )

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.EXECUTION

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="symbol",
                type="string",
                description="Trading pair symbol",
                required=True,
            ),
            ToolParameter(
                name="take_profit",
                type="number",
                description="New take profit price",
                required=True,
            ),
        ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        symbol = kwargs["symbol"]
        take_profit = kwargs["take_profit"]

        try:
            from keryxflow.exchange.paper import get_paper_engine

            engine = get_paper_engine()
            await engine.initialize()

            # Check if position exists
            position = await engine.get_position(symbol)
            if position is None:
                return ToolResult(
                    success=False,
                    error=f"No open position for {symbol}",
                )

            # Validate take profit direction
            if position.side.value == "buy":
                # Long position - TP must be above entry
                if take_profit <= position.entry_price:
                    return ToolResult(
                        success=False,
                        error=f"Take profit ({take_profit}) must be above entry price ({position.entry_price}) for long positions",
                    )
            else:
                # Short position - TP must be below entry
                if take_profit >= position.entry_price:
                    return ToolResult(
                        success=False,
                        error=f"Take profit ({take_profit}) must be below entry price ({position.entry_price}) for short positions",
                    )

            # Update the position take profit in database
            from keryxflow.core.database import get_session_factory
            from keryxflow.core.models import Position as PositionModel

            async_session = get_session_factory()
            async with async_session() as session:
                from sqlmodel import select

                result = await session.execute(
                    select(PositionModel).where(PositionModel.symbol == symbol)
                )
                db_position = result.scalar_one_or_none()

                if db_position:
                    old_tp = db_position.take_profit
                    db_position.take_profit = take_profit
                    await session.commit()

            logger.info(
                "take_profit_updated",
                symbol=symbol,
                old_tp=old_tp,
                new_tp=take_profit,
            )

            return ToolResult(
                success=True,
                data={
                    "symbol": symbol,
                    "old_take_profit": old_tp,
                    "new_take_profit": take_profit,
                    "entry_price": position.entry_price,
                    "current_price": position.current_price,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

        except Exception as e:
            logger.exception("set_take_profit_failed", symbol=symbol)
            return ToolResult(
                success=False,
                error=f"Failed to set take profit: {str(e)}",
            )


class CancelOrderTool(BaseTool):
    """Cancel a pending order.

    This tool is GUARDED.
    """

    @property
    def name(self) -> str:
        return "cancel_order"

    @property
    def description(self) -> str:
        return "Cancel a pending (unfilled) order by its order ID."

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.EXECUTION

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="order_id",
                type="string",
                description="ID of the order to cancel",
                required=True,
            ),
            ToolParameter(
                name="symbol",
                type="string",
                description="Trading pair symbol (required for exchange API)",
                required=True,
            ),
        ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        order_id = kwargs["order_id"]
        symbol = kwargs["symbol"]

        try:
            from keryxflow.exchange.orders import get_order_manager

            order_manager = get_order_manager()
            await order_manager.initialize()

            success = await order_manager.cancel_order(order_id, symbol)

            if success:
                logger.info("order_cancelled", order_id=order_id, symbol=symbol)
                return ToolResult(
                    success=True,
                    data={
                        "order_id": order_id,
                        "symbol": symbol,
                        "cancelled": True,
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                )
            else:
                return ToolResult(
                    success=False,
                    error=f"Could not cancel order {order_id}. It may already be filled or not exist.",
                )

        except Exception as e:
            logger.exception("cancel_order_failed", order_id=order_id)
            return ToolResult(
                success=False,
                error=f"Failed to cancel order: {str(e)}",
            )


class CloseAllPositionsTool(BaseTool):
    """Close all open positions (panic mode).

    This tool is GUARDED.
    """

    @property
    def name(self) -> str:
        return "close_all_positions"

    @property
    def description(self) -> str:
        return (
            "Emergency action to close ALL open positions immediately. "
            "Use this in panic situations or when circuit breaker triggers. "
            "This is an irreversible action."
        )

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.EXECUTION

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="reason",
                type="string",
                description="Reason for closing all positions",
                required=True,
            ),
            ToolParameter(
                name="confirm",
                type="boolean",
                description="Confirmation flag - must be true to execute",
                required=True,
            ),
        ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        reason = kwargs["reason"]
        confirm = kwargs["confirm"]

        if not confirm:
            return ToolResult(
                success=False,
                error="Action not confirmed. Set confirm=true to close all positions.",
            )

        try:
            from keryxflow.exchange.paper import get_paper_engine

            engine = get_paper_engine()
            await engine.initialize()

            # Get all positions before closing
            positions = await engine.get_positions()
            if not positions:
                return ToolResult(
                    success=True,
                    data={
                        "message": "No open positions to close",
                        "closed_count": 0,
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                )

            # Close all positions
            results = await engine.close_all_positions()

            total_pnl = 0
            closed_data = []
            for result in results:
                pnl = result.get("pnl", 0)
                total_pnl += pnl
                closed_data.append(
                    {
                        "symbol": result.get("symbol"),
                        "exit_price": result.get("price"),
                        "pnl": pnl,
                    }
                )

            logger.warning(
                "all_positions_closed",
                reason=reason,
                closed_count=len(results),
                total_pnl=total_pnl,
            )

            return ToolResult(
                success=True,
                data={
                    "reason": reason,
                    "closed_count": len(results),
                    "total_pnl": total_pnl,
                    "positions_closed": closed_data,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

        except Exception as e:
            logger.exception("close_all_positions_failed", reason=reason)
            return ToolResult(
                success=False,
                error=f"Failed to close all positions: {str(e)}",
            )


def register_execution_tools(toolkit: TradingToolkit) -> None:
    """Register all execution tools with the toolkit.

    Args:
        toolkit: The toolkit to register tools with
    """
    tools = [
        PlaceOrderTool(),
        ClosePositionTool(),
        SetStopLossTool(),
        SetTakeProfitTool(),
        CancelOrderTool(),
        CloseAllPositionsTool(),
    ]

    for tool in tools:
        toolkit.register(tool)

    logger.info("execution_tools_registered", count=len(tools))
