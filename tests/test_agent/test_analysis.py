"""Tests for analysis tools."""

import pytest

from keryxflow.agent.analysis_tools import (
    CalculateIndicatorsTool,
    CalculatePositionSizeTool,
    CalculateRiskRewardTool,
    CalculateStopLossTool,
    GetMarketPatternsTool,
    GetTradingRulesTool,
    RecallSimilarTradesTool,
    register_analysis_tools,
)
from keryxflow.agent.tools import ToolCategory, TradingToolkit


class TestAnalysisToolsRegistration:
    """Tests for analysis tools registration."""

    def test_register_analysis_tools(self):
        """Test registering all analysis tools."""
        toolkit = TradingToolkit()
        register_analysis_tools(toolkit)

        # Should have 7 analysis/introspection tools
        analysis_tools = toolkit.get_tools_by_category(ToolCategory.ANALYSIS)
        introspection_tools = toolkit.get_tools_by_category(ToolCategory.INTROSPECTION)

        assert len(analysis_tools) == 4  # indicators, position_size, risk_reward, stop_loss
        assert len(introspection_tools) == 3  # rules, similar_trades, patterns

    def test_analysis_tools_not_guarded(self):
        """Test that analysis tools are not guarded."""
        toolkit = TradingToolkit()
        register_analysis_tools(toolkit)

        all_tools = toolkit.get_tools_by_category(
            ToolCategory.ANALYSIS
        ) + toolkit.get_tools_by_category(ToolCategory.INTROSPECTION)

        for tool in all_tools:
            assert tool.is_guarded is False


class TestCalculateIndicatorsTool:
    """Tests for CalculateIndicatorsTool."""

    def test_tool_properties(self):
        """Test tool properties."""
        tool = CalculateIndicatorsTool()

        assert tool.name == "calculate_indicators"
        assert tool.category == ToolCategory.ANALYSIS
        assert tool.is_guarded is False

    def test_parameters(self):
        """Test tool parameters."""
        tool = CalculateIndicatorsTool()

        assert len(tool.parameters) == 3

        symbol_param = next(p for p in tool.parameters if p.name == "symbol")
        assert symbol_param.required is True

        timeframe_param = next(p for p in tool.parameters if p.name == "timeframe")
        assert timeframe_param.default == "1h"
        assert "4h" in timeframe_param.enum


class TestCalculatePositionSizeTool:
    """Tests for CalculatePositionSizeTool."""

    def test_tool_properties(self):
        """Test tool properties."""
        tool = CalculatePositionSizeTool()

        assert tool.name == "calculate_position_size"
        assert tool.category == ToolCategory.ANALYSIS

    def test_parameters(self):
        """Test tool parameters."""
        tool = CalculatePositionSizeTool()

        param_names = [p.name for p in tool.parameters]
        assert "balance" in param_names
        assert "entry_price" in param_names
        assert "stop_loss" in param_names
        assert "risk_pct" in param_names

    @pytest.mark.asyncio
    async def test_execute_calculates_position_size(self):
        """Test position size calculation."""
        tool = CalculatePositionSizeTool()

        result = await tool.execute(
            balance=10000.0,
            entry_price=45000.0,
            stop_loss=44000.0,
            risk_pct=0.01,  # 1% risk
        )

        assert result.success is True
        assert "quantity" in result.data
        assert "risk_amount" in result.data
        assert result.data["risk_amount"] <= 100.0  # 1% of 10000

    @pytest.mark.asyncio
    async def test_execute_with_invalid_stop_loss(self):
        """Test with stop loss equal to entry (invalid)."""
        tool = CalculatePositionSizeTool()

        result = await tool.execute(
            balance=10000.0,
            entry_price=45000.0,
            stop_loss=45000.0,  # Same as entry
            risk_pct=0.01,
        )

        assert result.success is False


class TestCalculateRiskRewardTool:
    """Tests for CalculateRiskRewardTool."""

    def test_tool_properties(self):
        """Test tool properties."""
        tool = CalculateRiskRewardTool()

        assert tool.name == "calculate_risk_reward"
        assert tool.category == ToolCategory.ANALYSIS

    @pytest.mark.asyncio
    async def test_execute_calculates_ratio(self):
        """Test R:R ratio calculation."""
        tool = CalculateRiskRewardTool()

        result = await tool.execute(
            entry_price=100.0,
            stop_loss=95.0,  # Risk 5
            take_profit=110.0,  # Reward 10
            quantity=10.0,
        )

        assert result.success is True
        assert result.data["ratio"] == 2.0  # 10/5 = 2
        assert result.data["potential_profit"] == 100.0  # 10 * 10
        assert result.data["potential_loss"] == 50.0  # 5 * 10
        assert result.data["is_favorable"] is True

    @pytest.mark.asyncio
    async def test_unfavorable_ratio(self):
        """Test calculation of unfavorable R:R."""
        tool = CalculateRiskRewardTool()

        result = await tool.execute(
            entry_price=100.0,
            stop_loss=90.0,  # Risk 10
            take_profit=105.0,  # Reward 5
        )

        assert result.success is True
        assert result.data["ratio"] == 0.5
        assert result.data["is_favorable"] is False


class TestCalculateStopLossTool:
    """Tests for CalculateStopLossTool."""

    def test_tool_properties(self):
        """Test tool properties."""
        tool = CalculateStopLossTool()

        assert tool.name == "calculate_stop_loss"
        assert tool.category == ToolCategory.ANALYSIS

    @pytest.mark.asyncio
    async def test_fixed_stop_loss_buy(self):
        """Test fixed percentage stop for buy order."""
        tool = CalculateStopLossTool()

        result = await tool.execute(
            entry_price=100.0,
            side="buy",
            method="fixed",
            percentage=0.02,  # 2%
        )

        assert result.success is True
        assert result.data["stop_loss"] == 98.0  # 100 - 2%
        assert result.data["method"] == "Fixed 2.0%"

    @pytest.mark.asyncio
    async def test_fixed_stop_loss_sell(self):
        """Test fixed percentage stop for sell order."""
        tool = CalculateStopLossTool()

        result = await tool.execute(
            entry_price=100.0,
            side="sell",
            method="fixed",
            percentage=0.02,
        )

        assert result.success is True
        assert result.data["stop_loss"] == 102.0  # 100 + 2%

    @pytest.mark.asyncio
    async def test_atr_stop_requires_symbol(self):
        """Test that ATR stop requires symbol."""
        tool = CalculateStopLossTool()

        result = await tool.execute(
            entry_price=100.0,
            side="buy",
            method="atr",
        )

        assert result.success is False
        assert "Symbol is required" in result.error


class TestGetTradingRulesTool:
    """Tests for GetTradingRulesTool."""

    def test_tool_properties(self):
        """Test tool properties."""
        tool = GetTradingRulesTool()

        assert tool.name == "get_trading_rules"
        assert tool.category == ToolCategory.INTROSPECTION

    @pytest.mark.asyncio
    async def test_execute_returns_empty_list(self, _init_db):
        """Test returns empty list when no rules."""
        tool = GetTradingRulesTool()
        result = await tool.execute()

        assert result.success is True
        assert result.data["rules"] == []
        assert result.data["count"] == 0


class TestRecallSimilarTradesTool:
    """Tests for RecallSimilarTradesTool."""

    def test_tool_properties(self):
        """Test tool properties."""
        tool = RecallSimilarTradesTool()

        assert tool.name == "recall_similar_trades"
        assert tool.category == ToolCategory.INTROSPECTION

    def test_parameters(self):
        """Test tool parameters."""
        tool = RecallSimilarTradesTool()

        param_names = [p.name for p in tool.parameters]
        assert "symbol" in param_names
        assert "rsi" in param_names
        assert "trend" in param_names

    @pytest.mark.asyncio
    async def test_execute_returns_empty_list(self, _init_db):
        """Test returns empty list when no similar trades."""
        tool = RecallSimilarTradesTool()
        result = await tool.execute(symbol="BTC/USDT")

        assert result.success is True
        assert result.data["similar_trades"] == []
        assert result.data["count"] == 0


class TestGetMarketPatternsTool:
    """Tests for GetMarketPatternsTool."""

    def test_tool_properties(self):
        """Test tool properties."""
        tool = GetMarketPatternsTool()

        assert tool.name == "get_market_patterns"
        assert tool.category == ToolCategory.INTROSPECTION

    @pytest.mark.asyncio
    async def test_execute_returns_empty_list(self, _init_db):
        """Test returns empty list when no patterns."""
        tool = GetMarketPatternsTool()
        result = await tool.execute()

        assert result.success is True
        assert result.data["patterns"] == []
        assert result.data["count"] == 0


class TestAnalysisToolsIntegration:
    """Integration tests for analysis tools."""

    @pytest.mark.asyncio
    async def test_tools_can_be_executed_through_toolkit(self, _init_db):
        """Test that analysis tools can be executed through toolkit."""
        toolkit = TradingToolkit()
        register_analysis_tools(toolkit)

        # Test calculate_position_size
        result = await toolkit.execute(
            "calculate_position_size",
            balance=10000.0,
            entry_price=45000.0,
            stop_loss=44000.0,
        )
        assert result.success is True

        # Test calculate_risk_reward
        result = await toolkit.execute(
            "calculate_risk_reward",
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=110.0,
        )
        assert result.success is True

        # Test calculate_stop_loss
        result = await toolkit.execute(
            "calculate_stop_loss",
            entry_price=100.0,
            side="buy",
        )
        assert result.success is True

        # Test get_trading_rules
        result = await toolkit.execute("get_trading_rules")
        assert result.success is True

        # Test recall_similar_trades
        result = await toolkit.execute("recall_similar_trades", symbol="BTC/USDT")
        assert result.success is True

        # Test get_market_patterns
        result = await toolkit.execute("get_market_patterns")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_position_size_and_risk_reward_workflow(self):
        """Test typical workflow combining position size and R:R."""
        toolkit = TradingToolkit()
        register_analysis_tools(toolkit)

        # Step 1: Calculate position size
        size_result = await toolkit.execute(
            "calculate_position_size",
            balance=10000.0,
            entry_price=45000.0,
            stop_loss=44000.0,
            risk_pct=0.01,
        )
        assert size_result.success is True
        quantity = size_result.data["quantity"]

        # Step 2: Calculate R:R with take profit
        rr_result = await toolkit.execute(
            "calculate_risk_reward",
            entry_price=45000.0,
            stop_loss=44000.0,
            take_profit=47000.0,  # 2:1 target
            quantity=quantity,
        )
        assert rr_result.success is True
        assert rr_result.data["ratio"] == 2.0
