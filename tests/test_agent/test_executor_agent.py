"""Tests for the ExecutorAgent."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from keryxflow.agent.base_agent import (
    AgentRole,
    ExecutionResult,
    MarketAnalysis,
    RiskAssessment,
)
from keryxflow.agent.executor_agent import ExecutorAgent
from keryxflow.agent.tools import ToolCategory, ToolResult


class TestExecutorAgent:
    """Tests for ExecutorAgent class."""

    def test_create_executor_agent(self):
        """Test creating an executor agent."""
        agent = ExecutorAgent()

        assert agent._initialized is False
        assert agent.role == AgentRole.EXECUTOR

    def test_role(self):
        """Test executor role."""
        agent = ExecutorAgent()
        assert agent.role == AgentRole.EXECUTOR

    def test_allowed_categories(self):
        """Test executor has correct tool categories."""
        agent = ExecutorAgent()
        categories = agent.allowed_categories

        assert ToolCategory.PERCEPTION in categories
        assert ToolCategory.EXECUTION in categories
        assert ToolCategory.ANALYSIS not in categories
        assert ToolCategory.INTROSPECTION not in categories

    def test_system_prompt_contains_execution_focus(self):
        """Test system prompt focuses on execution."""
        agent = ExecutorAgent()
        prompt = agent.system_prompt

        assert "executor" in prompt.lower() or "execute" in prompt.lower()
        assert "order" in prompt.lower()
        assert "stop loss" in prompt.lower()

    def test_parse_execution_with_order(self):
        """Test parsing execution with successful order."""
        agent = ExecutorAgent()
        tool_results = [
            ToolResult(
                success=True,
                data={"order_id": "ord_123", "quantity": 0.05, "price": 50000},
            )
        ]

        result = agent._parse_execution(
            "Order placed successfully at market price.",
            tool_results,
            "BTC/USDT",
            "buy",
        )

        assert result.executed is True
        assert result.order_id == "ord_123"
        assert result.quantity == 0.05
        assert result.price == 50000

    def test_parse_execution_no_order(self):
        """Test parsing execution when no order was placed."""
        agent = ExecutorAgent()

        result = agent._parse_execution(
            "Could not execute, spread too wide.",
            [],
            "BTC/USDT",
            "buy",
        )

        assert result.executed is False
        assert result.order_id is None

    @pytest.mark.asyncio
    async def test_execute_not_approved(self):
        """Test execute_trade rejects non-approved trades."""
        agent = ExecutorAgent()
        agent._initialized = True

        analysis = MarketAnalysis(symbol="BTC/USDT", signal="long", confidence=0.8)
        assessment = RiskAssessment(approved=False, reasoning="Too risky")

        result = await agent.execute_trade(analysis, assessment)

        assert isinstance(result, ExecutionResult)
        assert result.executed is False
        assert "not approved" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_execute_trade_with_mocked_claude(self):
        """Test execute_trade with mocked Claude API response."""
        agent = ExecutorAgent()
        agent._initialized = True

        agent._call_claude = AsyncMock(
            return_value=(
                "Order executed at market price. Set stop loss at 48000.",
                [
                    ToolResult(
                        success=True,
                        data={"order_id": "ord_456", "quantity": 0.1, "price": 50500},
                    ),
                ],
                300,
            )
        )

        analysis = MarketAnalysis(symbol="BTC/USDT", signal="long", confidence=0.85)
        assessment = RiskAssessment(
            approved=True,
            position_size=0.1,
            stop_loss=48000,
            take_profit=55000,
            risk_reward_ratio=2.5,
        )

        result = await agent.execute_trade(analysis, assessment)

        assert result.executed is True
        assert result.order_id == "ord_456"
        assert result.tokens_used == 300
        assert result.symbol == "BTC/USDT"
        assert result.side == "buy"

    @pytest.mark.asyncio
    async def test_execute_trade_short(self):
        """Test execute_trade for short signal."""
        agent = ExecutorAgent()
        agent._initialized = True

        agent._call_claude = AsyncMock(
            return_value=(
                "Short order placed.",
                [
                    ToolResult(
                        success=True,
                        data={"order_id": "ord_789", "quantity": 0.05, "price": 50000},
                    ),
                ],
                250,
            )
        )

        analysis = MarketAnalysis(symbol="ETH/USDT", signal="short", confidence=0.7)
        assessment = RiskAssessment(
            approved=True,
            position_size=0.05,
            stop_loss=52000,
            take_profit=46000,
            risk_reward_ratio=2.0,
        )

        result = await agent.execute_trade(analysis, assessment)

        assert result.executed is True
        assert result.side == "sell"

    @pytest.mark.asyncio
    async def test_execute_trade_no_client(self):
        """Test execute_trade returns not executed when client unavailable."""
        with patch("keryxflow.agent.base_agent.get_settings") as mock_settings:
            mock_settings.return_value.agent = MagicMock()
            mock_settings.return_value.anthropic_api_key.get_secret_value.return_value = ""
            agent = ExecutorAgent()
            await agent.initialize()

        analysis = MarketAnalysis(symbol="BTC/USDT", signal="long", confidence=0.8)
        assessment = RiskAssessment(approved=True, position_size=0.1)

        result = await agent.execute_trade(analysis, assessment)

        assert result.executed is False

    def test_get_tool_schemas(self):
        """Test that tool schemas only include allowed categories."""
        agent = ExecutorAgent()

        from keryxflow.agent.tools import register_all_tools

        register_all_tools(agent.toolkit)

        schemas = agent._get_tool_schemas()
        tool_names = [s["name"] for s in schemas]

        # Should have perception and execution tools
        assert "get_current_price" in tool_names
        assert "place_order" in tool_names
        assert "close_position" in tool_names

        # Should NOT have analysis tools
        assert "calculate_indicators" not in tool_names
