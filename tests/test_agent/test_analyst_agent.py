"""Tests for the AnalystAgent."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from keryxflow.agent.analyst_agent import AnalystAgent
from keryxflow.agent.base_agent import AgentRole, MarketAnalysis
from keryxflow.agent.tools import ToolCategory, ToolResult


class TestAnalystAgent:
    """Tests for AnalystAgent class."""

    def test_create_analyst(self):
        """Test creating an analyst agent."""
        agent = AnalystAgent()

        assert agent._initialized is False
        assert agent.role == AgentRole.ANALYST
        assert agent.toolkit is not None

    def test_role(self):
        """Test analyst role."""
        agent = AnalystAgent()
        assert agent.role == AgentRole.ANALYST

    def test_allowed_categories(self):
        """Test analyst has correct tool categories."""
        agent = AnalystAgent()
        categories = agent.allowed_categories

        assert ToolCategory.PERCEPTION in categories
        assert ToolCategory.ANALYSIS in categories
        assert ToolCategory.INTROSPECTION in categories
        assert ToolCategory.EXECUTION not in categories

    def test_system_prompt_contains_analysis_focus(self):
        """Test system prompt focuses on analysis."""
        agent = AnalystAgent()
        prompt = agent.system_prompt

        assert "analyst" in prompt.lower() or "analysis" in prompt.lower()
        assert "signal" in prompt.lower()
        assert "do not execute" in prompt.lower() or "not execute" in prompt.lower()

    def test_parse_analysis_long(self):
        """Test parsing long signal from reasoning."""
        agent = AnalystAgent()
        signal, confidence = agent._parse_analysis(
            "Based on the indicators, Signal: LONG with high confidence."
        )
        assert signal == "long"
        assert confidence == 0.8

    def test_parse_analysis_short(self):
        """Test parsing short signal from reasoning."""
        agent = AnalystAgent()
        signal, confidence = agent._parse_analysis(
            "The market is bearish. Signal: SHORT. Confidence: 0.7"
        )
        assert signal == "short"
        assert confidence == 0.7

    def test_parse_analysis_hold(self):
        """Test parsing hold signal from reasoning."""
        agent = AnalystAgent()
        signal, confidence = agent._parse_analysis(
            "No clear direction. I recommend holding for now."
        )
        assert signal == "hold"

    def test_parse_analysis_low_confidence(self):
        """Test parsing low confidence."""
        agent = AnalystAgent()
        signal, confidence = agent._parse_analysis(
            "Signal: LONG but with low confidence due to mixed signals."
        )
        assert signal == "long"
        assert confidence == 0.3

    @pytest.mark.asyncio
    async def test_analyze_no_client(self):
        """Test analyze returns hold when client unavailable."""
        with patch("keryxflow.agent.base_agent.get_settings") as mock_settings:
            mock_settings.return_value.agent = MagicMock()
            mock_settings.return_value.anthropic_api_key.get_secret_value.return_value = ""
            agent = AnalystAgent()
            await agent.initialize()

        result = await agent.analyze("BTC/USDT")

        assert isinstance(result, MarketAnalysis)
        assert result.symbol == "BTC/USDT"
        assert result.signal == "hold"

    @pytest.mark.asyncio
    async def test_analyze_with_mocked_claude(self):
        """Test analyze with mocked Claude API response."""
        agent = AnalystAgent()
        agent._initialized = True

        # Mock _call_claude
        agent._call_claude = AsyncMock(
            return_value=(
                "After analyzing BTC/USDT, Signal: LONG. Confidence: 0.85. "
                "RSI is oversold and MACD shows bullish crossover.",
                [ToolResult(success=True, data={"rsi": 28})],
                500,
            )
        )

        result = await agent.analyze("BTC/USDT")

        assert result.symbol == "BTC/USDT"
        assert result.signal == "long"
        assert result.confidence == 0.85
        assert result.tokens_used == 500
        assert len(result.tool_results) == 1

    @pytest.mark.asyncio
    async def test_analyze_with_context(self):
        """Test analyze with market context."""
        agent = AnalystAgent()
        agent._initialized = True

        agent._call_claude = AsyncMock(
            return_value=(
                "Signal: SHORT. Confidence: 0.6. Bearish divergence on RSI.",
                [],
                300,
            )
        )

        context = {
            "market_data": {
                "ETH/USDT": {"price": {"price": 3000.0}},
            },
            "memory_context": {
                "ETH/USDT": {"similar_episodes": [1], "matching_rules": [1, 2]},
            },
        }

        result = await agent.analyze("ETH/USDT", context)

        assert result.symbol == "ETH/USDT"
        assert result.signal == "short"
        assert result.confidence == 0.6

    def test_get_tool_schemas(self):
        """Test that tool schemas only include allowed categories."""
        agent = AnalystAgent()

        from keryxflow.agent.tools import register_all_tools

        register_all_tools(agent.toolkit)

        schemas = agent._get_tool_schemas()
        tool_names = [s["name"] for s in schemas]

        # Should have perception and analysis tools
        assert "get_current_price" in tool_names
        assert "calculate_indicators" in tool_names

        # Should NOT have execution tools
        assert "place_order" not in tool_names
        assert "close_position" not in tool_names
