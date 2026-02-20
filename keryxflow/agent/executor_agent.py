"""Executor Agent for order execution and timing.

The ExecutorAgent handles order execution, selecting order types,
and optimal entry timing. It only executes if risk is approved.
"""

from typing import Any

from keryxflow.agent.base_agent import (
    AgentRole,
    ExecutionResult,
    MarketAnalysis,
    RiskAssessment,
    SpecializedAgent,
)
from keryxflow.agent.tools import ToolCategory
from keryxflow.core.logging import get_logger

logger = get_logger(__name__)


class ExecutorAgent(SpecializedAgent):
    """Specialized agent for order execution and timing.

    Uses EXECUTION tools (place_order, close_position, set_stop_loss, etc.)
    and minimal PERCEPTION tools (price, order book) for timing.
    Still goes through ToolExecutor guardrails for all execution tools.
    """

    EXECUTOR_PROMPT = """You are KeryxFlow's Trade Executor agent. Your sole job is to execute approved trades with optimal timing and order management.

## Your Role
- Execute trades that have been approved by the Risk agent
- Choose optimal order type (market or limit)
- Set stop loss and take profit orders after entry
- Monitor order book for optimal entry timing

## Execution Rules
- ONLY execute trades that have been approved with specific parameters
- Use the exact position size provided by the Risk agent
- Always set stop loss immediately after entry
- Set take profit if provided
- Use market orders for immediate execution unless conditions favor limit orders

## What You Must Do
1. Check current price and order book for timing
2. Place the order with approved parameters
3. Set stop loss after the order fills
4. Set take profit if a target was provided

## Output Format
After execution, report:
- Whether the order was executed
- Order ID and fill details
- Stop loss and take profit levels set
- Your reasoning for execution timing

Current UTC time: {current_time}
"""

    @property
    def role(self) -> AgentRole:
        return AgentRole.EXECUTOR

    @property
    def system_prompt(self) -> str:
        return self.EXECUTOR_PROMPT

    @property
    def allowed_categories(self) -> list[ToolCategory]:
        return [ToolCategory.PERCEPTION, ToolCategory.EXECUTION]

    async def execute_trade(
        self,
        analysis: MarketAnalysis,
        assessment: RiskAssessment,
        _context: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        """Execute a trade based on analysis and risk assessment.

        Args:
            analysis: MarketAnalysis from the AnalystAgent
            assessment: RiskAssessment from the RiskAgent (must be approved)
            context: Optional additional context

        Returns:
            ExecutionResult with execution details
        """
        if not self._initialized:
            await self.initialize()

        if not assessment.approved:
            return ExecutionResult(
                executed=False,
                reasoning="Trade not approved by risk assessment",
            )

        # Build user message with full context
        side = "buy" if analysis.signal == "long" else "sell"
        parts = [
            f"Execute the following approved trade for {analysis.symbol}:\n",
            f"Side: {side}",
            f"Quantity: {assessment.position_size}",
            f"Stop loss: {assessment.stop_loss}",
            f"Take profit: {assessment.take_profit}",
            f"Risk/reward ratio: {assessment.risk_reward_ratio:.2f}\n",
            f"Analyst signal: {analysis.signal} (confidence: {analysis.confidence:.2f})",
            f"Analyst reasoning: {analysis.reasoning[:200]}\n",
            "Check the current price and order book, then execute the trade with the approved parameters.",
        ]
        user_message = "\n".join(parts)

        try:
            reasoning, tool_results, tokens = await self._call_claude(user_message)
            result = self._parse_execution(reasoning, tool_results, analysis.symbol, side)
            result.tool_results = tool_results
            result.tokens_used = tokens
            return result

        except Exception as e:
            logger.error("executor_agent_failed", symbol=analysis.symbol, error=str(e))
            return ExecutionResult(
                executed=False,
                reasoning=f"Execution failed: {e}",
            )

    def _parse_execution(
        self,
        reasoning: str,
        tool_results: list[Any],
        symbol: str,
        side: str,
    ) -> ExecutionResult:
        """Parse an ExecutionResult from the executor's reasoning and tool results."""
        order_id = None
        executed = False
        quantity = 0.0
        price = 0.0

        for result in tool_results:
            if not result.success or not result.data:
                continue
            data = result.data
            if isinstance(data, dict) and "order_id" in data:
                order_id = data["order_id"]
                executed = True
                quantity = float(data.get("quantity", 0))
                price = float(data.get("price", 0))

        return ExecutionResult(
            executed=executed,
            order_id=order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            reasoning=reasoning[:500],
        )
