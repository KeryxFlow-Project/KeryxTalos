"""Tests for perception tools."""

import pytest

from keryxflow.agent.perception_tools import (
    GetBalanceTool,
    GetCurrentPriceTool,
    GetOHLCVTool,
    GetOpenOrdersTool,
    GetOrderBookTool,
    GetPortfolioStateTool,
    GetPositionsTool,
    register_perception_tools,
)
from keryxflow.agent.tools import ToolCategory, TradingToolkit


class TestPerceptionToolsRegistration:
    """Tests for perception tools registration."""

    def test_register_perception_tools(self):
        """Test registering all perception tools."""
        toolkit = TradingToolkit()
        register_perception_tools(toolkit)

        # Should have 7 perception tools
        perception_tools = toolkit.get_tools_by_category(ToolCategory.PERCEPTION)
        assert len(perception_tools) == 7

    def test_perception_tools_not_guarded(self):
        """Test that perception tools are not guarded."""
        toolkit = TradingToolkit()
        register_perception_tools(toolkit)

        for tool in toolkit.get_tools_by_category(ToolCategory.PERCEPTION):
            assert tool.is_guarded is False


class TestGetCurrentPriceTool:
    """Tests for GetCurrentPriceTool."""

    def test_tool_properties(self):
        """Test tool properties."""
        tool = GetCurrentPriceTool()

        assert tool.name == "get_current_price"
        assert tool.category == ToolCategory.PERCEPTION
        assert tool.is_guarded is False
        assert len(tool.parameters) == 1
        assert tool.parameters[0].name == "symbol"

    def test_anthropic_schema(self):
        """Test Anthropic schema format."""
        tool = GetCurrentPriceTool()
        schema = tool.to_anthropic_schema()

        assert schema["name"] == "get_current_price"
        assert "symbol" in schema["input_schema"]["properties"]
        assert "symbol" in schema["input_schema"]["required"]

    @pytest.mark.asyncio
    async def test_execute_with_paper_engine(self, init_db):
        """Test execution with paper engine price."""
        from keryxflow.exchange.paper import get_paper_engine

        engine = get_paper_engine()
        await engine.initialize()
        engine.update_price("BTC/USDT", 45000.0)

        tool = GetCurrentPriceTool()
        result = await tool.execute(symbol="BTC/USDT")

        assert result.success is True
        assert result.data["symbol"] == "BTC/USDT"
        assert result.data["price"] == 45000.0
        assert result.data["source"] == "paper_engine"


class TestGetOHLCVTool:
    """Tests for GetOHLCVTool."""

    def test_tool_properties(self):
        """Test tool properties."""
        tool = GetOHLCVTool()

        assert tool.name == "get_ohlcv"
        assert tool.category == ToolCategory.PERCEPTION
        assert len(tool.parameters) == 3

    def test_parameter_defaults(self):
        """Test parameter defaults."""
        tool = GetOHLCVTool()

        timeframe_param = next(p for p in tool.parameters if p.name == "timeframe")
        assert timeframe_param.default == "1h"
        assert "1h" in timeframe_param.enum

        limit_param = next(p for p in tool.parameters if p.name == "limit")
        assert limit_param.default == 100


class TestGetOrderBookTool:
    """Tests for GetOrderBookTool."""

    def test_tool_properties(self):
        """Test tool properties."""
        tool = GetOrderBookTool()

        assert tool.name == "get_order_book"
        assert tool.category == ToolCategory.PERCEPTION


class TestGetPortfolioStateTool:
    """Tests for GetPortfolioStateTool."""

    def test_tool_properties(self):
        """Test tool properties."""
        tool = GetPortfolioStateTool()

        assert tool.name == "get_portfolio_state"
        assert tool.category == ToolCategory.PERCEPTION
        assert len(tool.parameters) == 0  # No parameters

    @pytest.mark.asyncio
    async def test_execute_returns_portfolio_data(self, init_db):
        """Test that execution returns portfolio state."""
        from keryxflow.aegis.risk import get_risk_manager

        # Initialize risk manager with some balance
        risk_manager = get_risk_manager(initial_balance=10000.0)

        tool = GetPortfolioStateTool()
        result = await tool.execute()

        assert result.success is True
        assert "total_value" in result.data
        assert "cash_available" in result.data
        assert "positions" in result.data
        assert "timestamp" in result.data


class TestGetBalanceTool:
    """Tests for GetBalanceTool."""

    def test_tool_properties(self):
        """Test tool properties."""
        tool = GetBalanceTool()

        assert tool.name == "get_balance"
        assert tool.category == ToolCategory.PERCEPTION

    def test_currency_parameter_optional(self):
        """Test that currency parameter is optional."""
        tool = GetBalanceTool()
        param = tool.parameters[0]

        assert param.name == "currency"
        assert param.required is False

    @pytest.mark.asyncio
    async def test_execute_returns_balance(self, init_db):
        """Test that execution returns balance."""
        from keryxflow.exchange.paper import get_paper_engine

        engine = get_paper_engine(initial_balance=10000.0)
        await engine.initialize()

        tool = GetBalanceTool()
        result = await tool.execute()

        assert result.success is True
        assert "total" in result.data
        assert "free" in result.data
        assert "used" in result.data

    @pytest.mark.asyncio
    async def test_execute_with_specific_currency(self, init_db):
        """Test execution filtering by currency."""
        from keryxflow.exchange.paper import get_paper_engine

        engine = get_paper_engine(initial_balance=10000.0)
        await engine.initialize()

        tool = GetBalanceTool()
        result = await tool.execute(currency="USDT")

        assert result.success is True
        assert result.data["currency"] == "USDT"
        assert "total" in result.data


class TestGetPositionsTool:
    """Tests for GetPositionsTool."""

    def test_tool_properties(self):
        """Test tool properties."""
        tool = GetPositionsTool()

        assert tool.name == "get_positions"
        assert tool.category == ToolCategory.PERCEPTION

    @pytest.mark.asyncio
    async def test_execute_returns_empty_list(self, init_db):
        """Test execution returns empty list when no positions."""
        from keryxflow.exchange.paper import get_paper_engine

        engine = get_paper_engine()
        await engine.initialize()

        tool = GetPositionsTool()
        result = await tool.execute()

        assert result.success is True
        assert result.data["positions"] == []
        assert result.data["count"] == 0

    @pytest.mark.asyncio
    async def test_execute_returns_positions(self, init_db):
        """Test execution returns open positions."""
        from keryxflow.exchange.paper import get_paper_engine

        engine = get_paper_engine(initial_balance=10000.0)
        await engine.initialize()
        engine.update_price("BTC/USDT", 45000.0)

        # Open a position
        await engine.open_position(
            symbol="BTC/USDT",
            side="buy",
            amount=0.1,
            entry_price=45000.0,
            stop_loss=44000.0,
        )

        tool = GetPositionsTool()
        result = await tool.execute()

        assert result.success is True
        assert result.data["count"] == 1
        assert result.data["positions"][0]["symbol"] == "BTC/USDT"


class TestGetOpenOrdersTool:
    """Tests for GetOpenOrdersTool."""

    def test_tool_properties(self):
        """Test tool properties."""
        tool = GetOpenOrdersTool()

        assert tool.name == "get_open_orders"
        assert tool.category == ToolCategory.PERCEPTION

    @pytest.mark.asyncio
    async def test_execute_returns_empty_list(self, init_db):
        """Test execution returns empty list when no orders."""
        from keryxflow.exchange.orders import get_order_manager

        manager = get_order_manager()
        await manager.initialize()

        tool = GetOpenOrdersTool()
        result = await tool.execute()

        assert result.success is True
        assert result.data["orders"] == []
        assert result.data["count"] == 0


class TestPerceptionToolsIntegration:
    """Integration tests for perception tools."""

    @pytest.mark.asyncio
    async def test_tools_can_be_executed_through_toolkit(self, init_db):
        """Test that all perception tools can be executed through toolkit."""
        from keryxflow.exchange.paper import get_paper_engine

        engine = get_paper_engine(initial_balance=10000.0)
        await engine.initialize()
        engine.update_price("BTC/USDT", 45000.0)

        toolkit = TradingToolkit()
        register_perception_tools(toolkit)

        # Test get_current_price
        result = await toolkit.execute("get_current_price", symbol="BTC/USDT")
        assert result.success is True

        # Test get_balance
        result = await toolkit.execute("get_balance")
        assert result.success is True

        # Test get_positions
        result = await toolkit.execute("get_positions")
        assert result.success is True

        # Test get_portfolio_state
        result = await toolkit.execute("get_portfolio_state")
        assert result.success is True

        # Test get_open_orders
        result = await toolkit.execute("get_open_orders")
        assert result.success is True
