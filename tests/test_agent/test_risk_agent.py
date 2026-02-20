"""Tests for the RiskAgent."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from keryxflow.agent.base_agent import AgentRole, MarketAnalysis, RiskAssessment
from keryxflow.agent.risk_agent import RiskAgent
from keryxflow.agent.tools import ToolCategory, ToolResult


class TestRiskAgent:
    """Tests for RiskAgent class."""

    def test_create_risk_agent(self):
        """Test creating a risk agent."""
        agent = RiskAgent()

        assert agent._initialized is False
        assert agent.role == AgentRole.RISK

    def test_role(self):
        """Test risk agent role."""
        agent = RiskAgent()
        assert agent.role == AgentRole.RISK

    def test_allowed_categories(self):
        """Test risk agent has correct tool categories."""
        agent = RiskAgent()
        categories = agent.allowed_categories

        assert ToolCategory.PERCEPTION in categories
        assert ToolCategory.ANALYSIS in categories
        assert ToolCategory.EXECUTION not in categories
        assert ToolCategory.INTROSPECTION not in categories

    def test_system_prompt_contains_risk_focus(self):
        """Test system prompt focuses on risk."""
        agent = RiskAgent()
        prompt = agent.system_prompt

        assert "risk" in prompt.lower()
        assert "position size" in prompt.lower() or "position sizing" in prompt.lower()
        assert "stop loss" in prompt.lower()
        assert "not execute" in prompt.lower() or "do not execute" in prompt.lower()

    def test_parse_assessment_approved(self):
        """Test parsing approved assessment."""
        agent = RiskAgent()
        tool_results = [
            ToolResult(
                success=True,
                data={"quantity": 0.05, "stop_loss_price": 48000.0},
            ),
            ToolResult(
                success=True,
                data={"ratio": 2.5},
            ),
        ]

        assessment = agent._parse_assessment(
            "Decision: APPROVED. Risk score: 0.3. Position size is within limits.",
            tool_results,
        )

        assert assessment.approved is True
        assert assessment.position_size == 0.05
        assert assessment.stop_loss == 48000.0
        assert assessment.risk_reward_ratio == 2.5
        assert assessment.risk_score == 0.3

    def test_parse_assessment_rejected(self):
        """Test parsing rejected assessment."""
        agent = RiskAgent()

        assessment = agent._parse_assessment(
            "Decision: REJECTED. Risk is too high, current exposure exceeds limits.",
            [],
        )

        assert assessment.approved is False

    @pytest.mark.asyncio
    async def test_assess_no_client(self):
        """Test assess returns not approved when client unavailable."""
        with patch("keryxflow.agent.base_agent.get_settings") as mock_settings:
            mock_settings.return_value.agent = MagicMock()
            mock_settings.return_value.anthropic_api_key.get_secret_value.return_value = ""
            agent = RiskAgent()
            await agent.initialize()

        analysis = MarketAnalysis(
            symbol="BTC/USDT",
            signal="long",
            confidence=0.8,
            reasoning="Bullish signal detected",
        )

        result = await agent.assess(analysis)

        assert isinstance(result, RiskAssessment)
        assert result.approved is False

    @pytest.mark.asyncio
    async def test_assess_with_mocked_claude(self):
        """Test assess with mocked Claude API response."""
        agent = RiskAgent()
        agent._initialized = True

        agent._call_claude = AsyncMock(
            return_value=(
                "Decision: APPROVED. Position size is safe. Risk score: 0.25.",
                [
                    ToolResult(success=True, data={"quantity": 0.1, "risk_amount": 100}),
                    ToolResult(success=True, data={"ratio": 3.0, "stop_loss_price": 47000}),
                ],
                400,
            )
        )

        analysis = MarketAnalysis(
            symbol="BTC/USDT",
            signal="long",
            confidence=0.85,
            reasoning="Strong bullish signal",
        )

        result = await agent.assess(analysis)

        assert result.approved is True
        assert result.position_size == 0.1
        assert result.risk_reward_ratio == 3.0
        assert result.tokens_used == 400

    def test_get_tool_schemas(self):
        """Test that tool schemas only include allowed categories."""
        agent = RiskAgent()

        from keryxflow.agent.tools import register_all_tools

        register_all_tools(agent.toolkit)

        schemas = agent._get_tool_schemas()
        tool_names = [s["name"] for s in schemas]

        # Should have perception and analysis tools
        assert "get_portfolio_state" in tool_names
        assert "calculate_position_size" in tool_names

        # Should NOT have execution tools
        assert "place_order" not in tool_names
