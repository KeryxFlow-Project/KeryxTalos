"""Tests for the safe tool executor."""

import pytest

from keryxflow.agent.executor import ExecutorStats, ToolExecutor, get_tool_executor
from keryxflow.agent.tools import (
    BaseTool,
    ToolCategory,
    ToolParameter,
    ToolResult,
    TradingToolkit,
)


class MockPerceptionTool(BaseTool):
    """Mock perception tool for testing."""

    @property
    def name(self) -> str:
        return "mock_perception"

    @property
    def description(self) -> str:
        return "Mock perception tool"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.PERCEPTION

    @property
    def parameters(self) -> list[ToolParameter]:
        return [ToolParameter("value", "number", "A value", required=True)]

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, data={"received": kwargs["value"]})


class MockExecutionTool(BaseTool):
    """Mock execution tool for testing."""

    @property
    def name(self) -> str:
        return "mock_execution"

    @property
    def description(self) -> str:
        return "Mock execution tool"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.EXECUTION

    @property
    def parameters(self) -> list[ToolParameter]:
        return [ToolParameter("action", "string", "An action", required=True)]

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, data={"action": kwargs["action"]})


class FailingTool(BaseTool):
    """Tool that always fails."""

    @property
    def name(self) -> str:
        return "failing_tool"

    @property
    def description(self) -> str:
        return "Always fails"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS

    @property
    def parameters(self) -> list[ToolParameter]:
        return []

    async def execute(self, **kwargs) -> ToolResult:
        raise RuntimeError("Intentional failure")


class TestExecutorStats:
    """Tests for ExecutorStats dataclass."""

    def test_default_values(self):
        """Test default stats values."""
        stats = ExecutorStats()

        assert stats.total_executions == 0
        assert stats.successful_executions == 0
        assert stats.failed_executions == 0
        assert stats.blocked_by_guardrails == 0


class TestToolExecutor:
    """Tests for ToolExecutor."""

    def test_init_with_default_toolkit(self):
        """Test initialization with default toolkit."""
        executor = ToolExecutor()
        assert executor.toolkit is not None

    def test_init_with_custom_toolkit(self):
        """Test initialization with custom toolkit."""
        toolkit = TradingToolkit()
        executor = ToolExecutor(toolkit=toolkit)
        assert executor.toolkit is toolkit

    def test_init_with_rate_limit(self):
        """Test initialization with custom rate limit."""
        executor = ToolExecutor(max_executions_per_minute=10)
        assert executor.max_executions_per_minute == 10

    @pytest.mark.asyncio
    async def test_execute_perception_tool(self):
        """Test executing a perception (unguarded) tool."""
        toolkit = TradingToolkit()
        toolkit.register(MockPerceptionTool())
        executor = ToolExecutor(toolkit=toolkit)

        result = await executor.execute("mock_perception", value=42)

        assert result.success is True
        assert result.data["received"] == 42

    @pytest.mark.asyncio
    async def test_execute_nonexistent_tool(self):
        """Test executing a tool that doesn't exist."""
        executor = ToolExecutor(toolkit=TradingToolkit())

        result = await executor.execute("nonexistent")

        assert result.success is False
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_execute_with_invalid_params(self):
        """Test executing with invalid parameters."""
        toolkit = TradingToolkit()
        toolkit.register(MockPerceptionTool())
        executor = ToolExecutor(toolkit=toolkit)

        # Missing required parameter
        result = await executor.execute("mock_perception")

        assert result.success is False

    @pytest.mark.asyncio
    async def test_execute_handles_tool_exception(self):
        """Test that executor handles tool exceptions gracefully."""
        toolkit = TradingToolkit()
        toolkit.register(FailingTool())
        executor = ToolExecutor(toolkit=toolkit)

        result = await executor.execute("failing_tool")

        assert result.success is False
        assert "failed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_stats_tracking(self):
        """Test that execution stats are tracked."""
        toolkit = TradingToolkit()
        toolkit.register(MockPerceptionTool())
        toolkit.register(FailingTool())
        executor = ToolExecutor(toolkit=toolkit)

        # Successful execution
        await executor.execute("mock_perception", value=1)
        await executor.execute("mock_perception", value=2)

        # Failed execution
        await executor.execute("failing_tool")

        stats = executor.get_stats()
        assert stats["total_executions"] == 3
        assert stats["successful_executions"] == 2
        assert stats["failed_executions"] == 1

    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test rate limiting functionality."""
        toolkit = TradingToolkit()
        toolkit.register(MockPerceptionTool())
        executor = ToolExecutor(toolkit=toolkit, max_executions_per_minute=3)

        # Execute within limits
        for i in range(3):
            result = await executor.execute("mock_perception", value=i)
            assert result.success is True

        # Fourth execution should be rate limited
        result = await executor.execute("mock_perception", value=99)
        assert result.success is False
        assert "Rate limit" in result.error

    @pytest.mark.asyncio
    async def test_execute_guarded_perception_tool(self):
        """Test that perception tools skip guardrail check."""
        toolkit = TradingToolkit()
        toolkit.register(MockPerceptionTool())
        executor = ToolExecutor(toolkit=toolkit)

        # Perception tools should work even with skip_guardrails=False
        result = await executor.execute("mock_perception", skip_guardrails=False, value=42)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_recent_executions(self):
        """Test getting recent execution history."""
        toolkit = TradingToolkit()
        toolkit.register(MockPerceptionTool())
        executor = ToolExecutor(toolkit=toolkit)

        await executor.execute("mock_perception", value=1)
        await executor.execute("mock_perception", value=2)

        recent = executor.get_recent_executions(limit=5)

        assert len(recent) == 2
        assert recent[0]["tool_name"] == "mock_perception"
        assert recent[0]["success"] is True

    def test_clear_stats(self):
        """Test clearing statistics."""
        executor = ToolExecutor()
        executor._stats.total_executions = 10
        executor._stats.successful_executions = 8

        executor.clear_stats()

        stats = executor.get_stats()
        assert stats["total_executions"] == 0
        assert stats["successful_executions"] == 0

    @pytest.mark.asyncio
    async def test_executions_by_category(self):
        """Test tracking executions by category."""
        toolkit = TradingToolkit()
        toolkit.register(MockPerceptionTool())
        toolkit.register(MockExecutionTool())
        executor = ToolExecutor(toolkit=toolkit)

        await executor.execute("mock_perception", value=1)
        await executor.execute("mock_perception", value=2)
        await executor.execute("mock_execution", skip_guardrails=True, action="test")

        stats = executor.get_stats()
        assert stats["executions_by_category"]["perception"] == 2
        assert stats["executions_by_category"]["execution"] == 1


class TestToolExecutorWithGuardrails:
    """Tests for executor with guardrail integration."""

    @pytest.mark.asyncio
    async def test_execute_guarded_tool_with_guardrails(self, init_db):
        """Test executing guarded tool validates against guardrails."""
        from keryxflow.aegis.risk import get_risk_manager
        from keryxflow.agent.execution_tools import register_execution_tools
        from keryxflow.exchange.paper import get_paper_engine

        # Setup
        engine = get_paper_engine(initial_balance=10000.0)
        await engine.initialize()
        engine.update_price("BTC/USDT", 45000.0)

        risk_manager = get_risk_manager(initial_balance=10000.0)

        toolkit = TradingToolkit()
        register_execution_tools(toolkit)
        executor = ToolExecutor(toolkit=toolkit)

        # Execute a valid order
        result = await executor.execute_guarded(
            "place_order",
            symbol="BTC/USDT",
            side="buy",
            quantity=0.01,
            stop_loss=44000.0,
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_guarded_blocks_invalid_order(self, init_db):
        """Test that guarded execution blocks invalid orders."""
        from keryxflow.aegis.risk import get_risk_manager
        from keryxflow.agent.execution_tools import register_execution_tools
        from keryxflow.exchange.paper import get_paper_engine

        engine = get_paper_engine(initial_balance=10000.0)
        await engine.initialize()
        engine.update_price("BTC/USDT", 45000.0)

        risk_manager = get_risk_manager(initial_balance=10000.0)

        toolkit = TradingToolkit()
        register_execution_tools(toolkit)
        executor = ToolExecutor(toolkit=toolkit)

        # Try to execute an order that exceeds limits
        result = await executor.execute_guarded(
            "place_order",
            symbol="BTC/USDT",
            side="buy",
            quantity=10.0,  # Way too much
        )

        assert result.success is False


class TestGlobalExecutor:
    """Tests for global executor instance."""

    def test_get_tool_executor_singleton(self):
        """Test that get_tool_executor returns singleton."""
        # Clear any existing instance
        import keryxflow.agent.executor as executor_module

        executor_module._executor = None

        executor1 = get_tool_executor()
        executor2 = get_tool_executor()

        assert executor1 is executor2
