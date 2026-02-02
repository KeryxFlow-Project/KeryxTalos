"""Tests for execution tools (GUARDED)."""

import pytest

from keryxflow.agent.execution_tools import (
    CancelOrderTool,
    CloseAllPositionsTool,
    ClosePositionTool,
    PlaceOrderTool,
    SetStopLossTool,
    SetTakeProfitTool,
    register_execution_tools,
)
from keryxflow.agent.tools import ToolCategory, TradingToolkit


class TestExecutionToolsRegistration:
    """Tests for execution tools registration."""

    def test_register_execution_tools(self):
        """Test registering all execution tools."""
        toolkit = TradingToolkit()
        register_execution_tools(toolkit)

        execution_tools = toolkit.get_tools_by_category(ToolCategory.EXECUTION)
        assert len(execution_tools) == 6

    def test_all_execution_tools_are_guarded(self):
        """Test that all execution tools are guarded."""
        toolkit = TradingToolkit()
        register_execution_tools(toolkit)

        for tool in toolkit.get_tools_by_category(ToolCategory.EXECUTION):
            assert tool.is_guarded is True, f"{tool.name} should be guarded"


class TestPlaceOrderTool:
    """Tests for PlaceOrderTool."""

    def test_tool_properties(self):
        """Test tool properties."""
        tool = PlaceOrderTool()

        assert tool.name == "place_order"
        assert tool.category == ToolCategory.EXECUTION
        assert tool.is_guarded is True

    def test_parameters(self):
        """Test tool parameters."""
        tool = PlaceOrderTool()

        param_names = [p.name for p in tool.parameters]
        assert "symbol" in param_names
        assert "side" in param_names
        assert "quantity" in param_names
        assert "order_type" in param_names
        assert "stop_loss" in param_names
        assert "take_profit" in param_names

    def test_side_enum(self):
        """Test side parameter enum values."""
        tool = PlaceOrderTool()
        side_param = next(p for p in tool.parameters if p.name == "side")
        assert side_param.enum == ["buy", "sell"]

    @pytest.mark.asyncio
    async def test_execute_requires_guardrail_validation(self, init_db):
        """Test that execution validates against guardrails."""
        from keryxflow.aegis.risk import get_risk_manager
        from keryxflow.exchange.paper import get_paper_engine

        # Initialize
        engine = get_paper_engine(initial_balance=10000.0)
        await engine.initialize()
        engine.update_price("BTC/USDT", 45000.0)

        risk_manager = get_risk_manager(initial_balance=10000.0)

        tool = PlaceOrderTool()

        # This should work - small position within limits
        result = await tool.execute(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.01,  # Small position
            stop_loss=44000.0,
        )

        assert result.success is True
        assert result.data["symbol"] == "BTC/USDT"

    @pytest.mark.asyncio
    async def test_execute_blocks_excessive_position(self, init_db):
        """Test that excessive positions are blocked by guardrails."""
        from keryxflow.aegis.risk import get_risk_manager
        from keryxflow.exchange.paper import get_paper_engine

        engine = get_paper_engine(initial_balance=10000.0)
        await engine.initialize()
        engine.update_price("BTC/USDT", 45000.0)

        risk_manager = get_risk_manager(initial_balance=10000.0)

        tool = PlaceOrderTool()

        # Try to buy way too much - should be blocked
        result = await tool.execute(
            symbol="BTC/USDT",
            side="buy",
            quantity=10.0,  # $450,000 worth - way over limits
        )

        assert result.success is False
        assert "guardrail" in result.error.lower() or "risk" in result.error.lower()

    @pytest.mark.asyncio
    async def test_limit_order_requires_price(self):
        """Test that limit orders require price parameter."""
        tool = PlaceOrderTool()

        result = await tool.execute(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.1,
            order_type="limit",
            # Missing price
        )

        assert result.success is False
        assert "price" in result.error.lower()


class TestClosePositionTool:
    """Tests for ClosePositionTool."""

    def test_tool_properties(self):
        """Test tool properties."""
        tool = ClosePositionTool()

        assert tool.name == "close_position"
        assert tool.category == ToolCategory.EXECUTION
        assert tool.is_guarded is True

    @pytest.mark.asyncio
    async def test_execute_no_position(self, init_db):
        """Test closing non-existent position."""
        from keryxflow.exchange.paper import get_paper_engine

        engine = get_paper_engine()
        await engine.initialize()

        tool = ClosePositionTool()
        result = await tool.execute(symbol="BTC/USDT")

        assert result.success is False
        assert "No open position" in result.error

    @pytest.mark.asyncio
    async def test_execute_closes_position(self, init_db):
        """Test closing an existing position."""
        from keryxflow.exchange.paper import get_paper_engine

        engine = get_paper_engine(initial_balance=10000.0)
        await engine.initialize()
        engine.update_price("BTC/USDT", 45000.0)

        # Open a position first
        await engine.open_position(
            symbol="BTC/USDT",
            side="buy",
            amount=0.1,
            entry_price=45000.0,
        )

        # Update price for profit
        engine.update_price("BTC/USDT", 46000.0)

        tool = ClosePositionTool()
        result = await tool.execute(symbol="BTC/USDT", reason="Test close")

        assert result.success is True
        assert result.data["symbol"] == "BTC/USDT"
        assert "pnl" in result.data


class TestSetStopLossTool:
    """Tests for SetStopLossTool."""

    def test_tool_properties(self):
        """Test tool properties."""
        tool = SetStopLossTool()

        assert tool.name == "set_stop_loss"
        assert tool.category == ToolCategory.EXECUTION
        assert tool.is_guarded is True

    @pytest.mark.asyncio
    async def test_execute_no_position(self, init_db):
        """Test setting stop loss on non-existent position."""
        from keryxflow.exchange.paper import get_paper_engine

        engine = get_paper_engine()
        await engine.initialize()

        tool = SetStopLossTool()
        result = await tool.execute(symbol="BTC/USDT", stop_loss=44000.0)

        assert result.success is False
        assert "No open position" in result.error

    @pytest.mark.asyncio
    async def test_execute_invalid_stop_direction(self, init_db):
        """Test setting invalid stop loss direction for long."""
        from keryxflow.exchange.paper import get_paper_engine

        engine = get_paper_engine(initial_balance=10000.0)
        await engine.initialize()
        engine.update_price("BTC/USDT", 45000.0)

        await engine.open_position(
            symbol="BTC/USDT",
            side="buy",
            amount=0.1,
            entry_price=45000.0,
        )

        tool = SetStopLossTool()
        # Stop above entry for long is invalid
        result = await tool.execute(symbol="BTC/USDT", stop_loss=46000.0)

        assert result.success is False
        assert "must be below" in result.error.lower()


class TestSetTakeProfitTool:
    """Tests for SetTakeProfitTool."""

    def test_tool_properties(self):
        """Test tool properties."""
        tool = SetTakeProfitTool()

        assert tool.name == "set_take_profit"
        assert tool.category == ToolCategory.EXECUTION
        assert tool.is_guarded is True

    @pytest.mark.asyncio
    async def test_execute_invalid_tp_direction(self, init_db):
        """Test setting invalid take profit direction for long."""
        from keryxflow.exchange.paper import get_paper_engine

        engine = get_paper_engine(initial_balance=10000.0)
        await engine.initialize()
        engine.update_price("BTC/USDT", 45000.0)

        await engine.open_position(
            symbol="BTC/USDT",
            side="buy",
            amount=0.1,
            entry_price=45000.0,
        )

        tool = SetTakeProfitTool()
        # TP below entry for long is invalid
        result = await tool.execute(symbol="BTC/USDT", take_profit=44000.0)

        assert result.success is False
        assert "must be above" in result.error.lower()


class TestCancelOrderTool:
    """Tests for CancelOrderTool."""

    def test_tool_properties(self):
        """Test tool properties."""
        tool = CancelOrderTool()

        assert tool.name == "cancel_order"
        assert tool.category == ToolCategory.EXECUTION
        assert tool.is_guarded is True

    def test_requires_order_id_and_symbol(self):
        """Test that order_id and symbol are required."""
        tool = CancelOrderTool()

        required_params = [p.name for p in tool.parameters if p.required]
        assert "order_id" in required_params
        assert "symbol" in required_params


class TestCloseAllPositionsTool:
    """Tests for CloseAllPositionsTool (panic mode)."""

    def test_tool_properties(self):
        """Test tool properties."""
        tool = CloseAllPositionsTool()

        assert tool.name == "close_all_positions"
        assert tool.category == ToolCategory.EXECUTION
        assert tool.is_guarded is True

    def test_requires_confirmation(self):
        """Test that confirmation is required."""
        tool = CloseAllPositionsTool()

        confirm_param = next(p for p in tool.parameters if p.name == "confirm")
        assert confirm_param.required is True
        assert confirm_param.type == "boolean"

    @pytest.mark.asyncio
    async def test_execute_requires_confirmation(self, init_db):
        """Test that execution requires confirm=true."""
        tool = CloseAllPositionsTool()

        result = await tool.execute(reason="Test", confirm=False)

        assert result.success is False
        assert "not confirmed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_closes_all(self, init_db):
        """Test closing all positions."""
        from keryxflow.exchange.paper import get_paper_engine

        engine = get_paper_engine(initial_balance=100000.0)
        await engine.initialize()

        # Open multiple positions
        engine.update_price("BTC/USDT", 45000.0)
        await engine.open_position(
            symbol="BTC/USDT",
            side="buy",
            amount=0.1,
            entry_price=45000.0,
        )

        engine.update_price("ETH/USDT", 3000.0)
        await engine.open_position(
            symbol="ETH/USDT",
            side="buy",
            amount=1.0,
            entry_price=3000.0,
        )

        tool = CloseAllPositionsTool()
        result = await tool.execute(reason="Emergency exit", confirm=True)

        assert result.success is True
        assert result.data["closed_count"] == 2

        # Verify no positions remain
        positions = await engine.get_positions()
        assert len(positions) == 0


class TestExecutionToolsGuardrailIntegration:
    """Integration tests for execution tools with guardrails."""

    @pytest.mark.asyncio
    async def test_place_order_respects_max_position_size(self, init_db):
        """Test that place_order respects MAX_POSITION_SIZE_PCT guardrail."""
        from keryxflow.aegis.guardrails import get_guardrails
        from keryxflow.aegis.risk import get_risk_manager
        from keryxflow.exchange.paper import get_paper_engine

        engine = get_paper_engine(initial_balance=10000.0)
        await engine.initialize()
        engine.update_price("BTC/USDT", 100.0)  # Low price for easier math

        risk_manager = get_risk_manager(initial_balance=10000.0)
        guardrails = get_guardrails()

        tool = PlaceOrderTool()

        # Try to place order larger than MAX_POSITION_SIZE_PCT (10%)
        # 10000 * 0.10 = 1000 max position value
        # At $100/BTC, max is 10 BTC
        # Try to buy 15 BTC ($1500 = 15%)
        result = await tool.execute(
            symbol="BTC/USDT",
            side="buy",
            quantity=15.0,
        )

        assert result.success is False
        # Should be blocked by guardrails or risk manager

    @pytest.mark.asyncio
    async def test_tools_through_toolkit_with_guardrails(self, init_db):
        """Test execution tools work through toolkit with guardrails."""
        from keryxflow.aegis.risk import get_risk_manager
        from keryxflow.exchange.paper import get_paper_engine

        engine = get_paper_engine(initial_balance=10000.0)
        await engine.initialize()
        engine.update_price("BTC/USDT", 45000.0)

        risk_manager = get_risk_manager(initial_balance=10000.0)

        toolkit = TradingToolkit()
        register_execution_tools(toolkit)

        # Small order should work
        result = await toolkit.execute(
            "place_order",
            symbol="BTC/USDT",
            side="buy",
            quantity=0.01,  # ~$450, well under limits
            stop_loss=44000.0,
        )

        assert result.success is True
