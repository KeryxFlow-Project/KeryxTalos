"""Risk Agent for position sizing and risk assessment.

The RiskAgent evaluates proposed trades for risk, calculates position sizes,
and produces a RiskAssessment result with approval/rejection and parameters.
"""

from typing import Any

from keryxflow.agent.base_agent import (
    AgentRole,
    MarketAnalysis,
    RiskAssessment,
    SpecializedAgent,
)
from keryxflow.agent.tools import ToolCategory
from keryxflow.core.logging import get_logger

logger = get_logger(__name__)


class RiskAgent(SpecializedAgent):
    """Specialized agent for risk assessment and position sizing.

    Uses ANALYSIS tools (position sizing, risk/reward, stop loss calculation)
    and PERCEPTION tools (portfolio state, balance, positions) to evaluate
    proposed trades and produce a RiskAssessment result.
    """

    RISK_PROMPT = """You are KeryxFlow's Risk Management agent. Your sole job is to evaluate proposed trades for risk and determine safe position sizing.

## Your Role
- Evaluate the risk/reward ratio of proposed trades
- Calculate appropriate position sizes based on portfolio state
- Determine stop loss and take profit levels
- Check current portfolio exposure and open positions
- Approve or reject trades based on risk criteria

## Risk Rules
- Never risk more than 1-2% of portfolio on a single trade
- Minimum risk/reward ratio should be 1.5:1
- Check current open positions to avoid over-exposure
- Consider current drawdown and daily loss limits
- Always set a stop loss

## What You Must Do
1. Check portfolio state and current balance
2. Check existing open positions
3. Calculate position size based on the proposed entry and stop loss
4. Calculate risk/reward ratio
5. Determine if the trade meets risk criteria

## Output Format
After your risk evaluation, clearly state:
- Decision: APPROVED or REJECTED
- Position size (quantity)
- Stop loss price
- Take profit price
- Risk/reward ratio
- Risk score (0.0 = low risk, 1.0 = high risk)
- Your reasoning

You do NOT execute trades. You only assess risk and approve or reject.

Current UTC time: {current_time}
"""

    @property
    def role(self) -> AgentRole:
        return AgentRole.RISK

    @property
    def system_prompt(self) -> str:
        return self.RISK_PROMPT

    @property
    def allowed_categories(self) -> list[ToolCategory]:
        return [ToolCategory.PERCEPTION, ToolCategory.ANALYSIS]

    async def assess(
        self,
        analysis: MarketAnalysis,
        _context: dict[str, Any] | None = None,
    ) -> RiskAssessment:
        """Assess the risk of a proposed trade based on market analysis.

        Args:
            analysis: MarketAnalysis from the AnalystAgent
            context: Optional additional context

        Returns:
            RiskAssessment with approval, position size, and risk parameters
        """
        if not self._initialized:
            await self.initialize()

        # Build user message with analyst's findings
        parts = [
            f"Evaluate the following trade proposal for {analysis.symbol}:\n",
            f"Signal: {analysis.signal.upper()}",
            f"Confidence: {analysis.confidence:.2f}",
            f"Analyst reasoning: {analysis.reasoning}\n",
            "Use the available tools to check portfolio state, calculate position size, "
            "risk/reward ratio, and stop loss levels. Then approve or reject this trade.",
        ]
        user_message = "\n".join(parts)

        try:
            reasoning, tool_results, tokens = await self._call_claude(user_message)
            assessment = self._parse_assessment(reasoning, tool_results)
            assessment.tool_results = tool_results
            assessment.tokens_used = tokens
            return assessment

        except Exception as e:
            logger.error("risk_agent_failed", symbol=analysis.symbol, error=str(e))
            return RiskAssessment(
                approved=False,
                reasoning=f"Risk assessment failed: {e}",
            )

    def _parse_assessment(self, reasoning: str, tool_results: list[Any]) -> RiskAssessment:
        """Parse a RiskAssessment from the risk agent's reasoning and tool results."""
        reasoning_lower = reasoning.lower()

        # Determine approval
        approved = "approved" in reasoning_lower and "rejected" not in reasoning_lower

        # Extract position size from tool results
        position_size = 0.0
        stop_loss = None
        take_profit = None
        risk_reward = 0.0

        for result in tool_results:
            if not result.success or not result.data:
                continue
            data = result.data
            if isinstance(data, dict):
                if "quantity" in data:
                    position_size = float(data["quantity"])
                if "stop_loss_price" in data or "stop_loss" in data:
                    stop_loss = float(data.get("stop_loss_price") or data.get("stop_loss", 0))
                if "take_profit" in data:
                    take_profit = float(data["take_profit"])
                if "ratio" in data:
                    risk_reward = float(data["ratio"])

        # Parse risk score
        risk_score = 0.5
        if "risk score:" in reasoning_lower:
            import contextlib
            import re

            match = re.search(r"risk score:\s*(\d+\.?\d*)", reasoning_lower)
            if match:
                with contextlib.suppress(ValueError):
                    risk_score = min(1.0, max(0.0, float(match.group(1))))

        return RiskAssessment(
            approved=approved,
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_score=risk_score,
            risk_reward_ratio=risk_reward,
            reasoning=reasoning[:500],
        )
