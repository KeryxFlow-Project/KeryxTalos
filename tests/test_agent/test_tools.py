"""Tests for the agent tool framework."""

import pytest

from keryxflow.agent.tools import (
    BaseTool,
    ToolCategory,
    ToolParameter,
    ToolResult,
    TradingToolkit,
    create_tool,
)


class TestToolResult:
    """Tests for ToolResult dataclass."""

    def test_tool_result_success(self):
        """Test successful tool result."""
        result = ToolResult(success=True, data={"price": 45000.0})

        assert result.success is True
        assert result.data == {"price": 45000.0}
        assert result.error is None

    def test_tool_result_failure(self):
        """Test failed tool result."""
        result = ToolResult(success=False, error="Connection timeout")

        assert result.success is False
        assert result.error == "Connection timeout"
        assert result.data is None

    def test_tool_result_to_dict_success(self):
        """Test to_dict for successful result."""
        result = ToolResult(success=True, data={"value": 123})
        d = result.to_dict()

        assert d["success"] is True
        assert d["data"] == {"value": 123}
        assert "error" not in d

    def test_tool_result_to_dict_failure(self):
        """Test to_dict for failed result."""
        result = ToolResult(success=False, error="Test error")
        d = result.to_dict()

        assert d["success"] is False
        assert d["error"] == "Test error"

    def test_tool_result_with_metadata(self):
        """Test tool result with metadata."""
        result = ToolResult(
            success=True,
            data={"price": 100},
            metadata={"source": "paper_engine"},
        )
        d = result.to_dict()

        assert d["metadata"] == {"source": "paper_engine"}


class TestToolParameter:
    """Tests for ToolParameter dataclass."""

    def test_basic_parameter(self):
        """Test basic parameter creation."""
        param = ToolParameter(
            name="symbol",
            type="string",
            description="Trading pair",
            required=True,
        )

        assert param.name == "symbol"
        assert param.type == "string"
        assert param.required is True
        assert param.enum is None

    def test_parameter_with_enum(self):
        """Test parameter with enum values."""
        param = ToolParameter(
            name="side",
            type="string",
            description="Order side",
            required=True,
            enum=["buy", "sell"],
        )

        assert param.enum == ["buy", "sell"]

    def test_parameter_with_default(self):
        """Test parameter with default value."""
        param = ToolParameter(
            name="limit",
            type="integer",
            description="Limit",
            required=False,
            default=100,
        )

        assert param.required is False
        assert param.default == 100


class TestBaseTool:
    """Tests for BaseTool abstract class."""

    def test_create_concrete_tool(self):
        """Test creating a concrete tool implementation."""

        class MockTool(BaseTool):
            @property
            def name(self) -> str:
                return "mock_tool"

            @property
            def description(self) -> str:
                return "A mock tool for testing"

            @property
            def category(self) -> ToolCategory:
                return ToolCategory.PERCEPTION

            @property
            def parameters(self) -> list[ToolParameter]:
                return [
                    ToolParameter("param1", "string", "First param", required=True),
                    ToolParameter("param2", "number", "Second param", required=False),
                ]

            async def execute(self, **kwargs):
                return ToolResult(success=True, data={"received": kwargs})

        tool = MockTool()

        assert tool.name == "mock_tool"
        assert tool.category == ToolCategory.PERCEPTION
        assert tool.is_guarded is False
        assert len(tool.parameters) == 2

    def test_execution_tool_is_guarded(self):
        """Test that execution tools are guarded."""

        class ExecutionTool(BaseTool):
            @property
            def name(self) -> str:
                return "exec_tool"

            @property
            def description(self) -> str:
                return "Execution tool"

            @property
            def category(self) -> ToolCategory:
                return ToolCategory.EXECUTION

            @property
            def parameters(self) -> list[ToolParameter]:
                return []

            async def execute(self, **_kwargs):
                return ToolResult(success=True)

        tool = ExecutionTool()
        assert tool.is_guarded is True

    def test_to_anthropic_schema(self):
        """Test conversion to Anthropic Tool Use API format."""

        class TestTool(BaseTool):
            @property
            def name(self) -> str:
                return "test_tool"

            @property
            def description(self) -> str:
                return "Test tool description"

            @property
            def category(self) -> ToolCategory:
                return ToolCategory.ANALYSIS

            @property
            def parameters(self) -> list[ToolParameter]:
                return [
                    ToolParameter("symbol", "string", "Trading pair", required=True),
                    ToolParameter("side", "string", "Side", required=True, enum=["buy", "sell"]),
                    ToolParameter("limit", "integer", "Limit", required=False, default=10),
                ]

            async def execute(self, **_kwargs):
                return ToolResult(success=True)

        tool = TestTool()
        schema = tool.to_anthropic_schema()

        assert schema["name"] == "test_tool"
        assert schema["description"] == "Test tool description"
        assert schema["input_schema"]["type"] == "object"
        assert "symbol" in schema["input_schema"]["properties"]
        assert schema["input_schema"]["properties"]["side"]["enum"] == ["buy", "sell"]
        assert schema["input_schema"]["required"] == ["symbol", "side"]

    def test_validate_parameters_success(self):
        """Test parameter validation success."""

        class TestTool(BaseTool):
            @property
            def name(self) -> str:
                return "test"

            @property
            def description(self) -> str:
                return "Test"

            @property
            def category(self) -> ToolCategory:
                return ToolCategory.PERCEPTION

            @property
            def parameters(self) -> list[ToolParameter]:
                return [
                    ToolParameter("symbol", "string", "Symbol", required=True),
                    ToolParameter("limit", "integer", "Limit", required=False),
                ]

            async def execute(self, **_kwargs):
                return ToolResult(success=True)

        tool = TestTool()
        is_valid, error = tool.validate_parameters(symbol="BTC/USDT", limit=50)

        assert is_valid is True
        assert error is None

    def test_validate_parameters_missing_required(self):
        """Test parameter validation with missing required param."""

        class TestTool(BaseTool):
            @property
            def name(self) -> str:
                return "test"

            @property
            def description(self) -> str:
                return "Test"

            @property
            def category(self) -> ToolCategory:
                return ToolCategory.PERCEPTION

            @property
            def parameters(self) -> list[ToolParameter]:
                return [
                    ToolParameter("symbol", "string", "Symbol", required=True),
                ]

            async def execute(self, **_kwargs):
                return ToolResult(success=True)

        tool = TestTool()
        is_valid, error = tool.validate_parameters()

        assert is_valid is False
        assert "symbol" in error

    def test_validate_parameters_invalid_enum(self):
        """Test parameter validation with invalid enum value."""

        class TestTool(BaseTool):
            @property
            def name(self) -> str:
                return "test"

            @property
            def description(self) -> str:
                return "Test"

            @property
            def category(self) -> ToolCategory:
                return ToolCategory.PERCEPTION

            @property
            def parameters(self) -> list[ToolParameter]:
                return [
                    ToolParameter("side", "string", "Side", required=True, enum=["buy", "sell"]),
                ]

            async def execute(self, **_kwargs):
                return ToolResult(success=True)

        tool = TestTool()
        is_valid, error = tool.validate_parameters(side="invalid")

        assert is_valid is False
        assert "must be one of" in error


class TestTradingToolkit:
    """Tests for TradingToolkit."""

    def test_register_tool(self):
        """Test registering a tool."""
        toolkit = TradingToolkit()

        class MockTool(BaseTool):
            @property
            def name(self) -> str:
                return "mock"

            @property
            def description(self) -> str:
                return "Mock"

            @property
            def category(self) -> ToolCategory:
                return ToolCategory.PERCEPTION

            @property
            def parameters(self) -> list[ToolParameter]:
                return []

            async def execute(self, **_kwargs):
                return ToolResult(success=True)

        tool = MockTool()
        toolkit.register(tool)

        assert toolkit.tool_count == 1
        assert toolkit.get_tool("mock") is tool

    def test_register_duplicate_raises(self):
        """Test that registering duplicate tool raises error."""
        toolkit = TradingToolkit()

        class MockTool(BaseTool):
            @property
            def name(self) -> str:
                return "mock"

            @property
            def description(self) -> str:
                return "Mock"

            @property
            def category(self) -> ToolCategory:
                return ToolCategory.PERCEPTION

            @property
            def parameters(self) -> list[ToolParameter]:
                return []

            async def execute(self, **_kwargs):
                return ToolResult(success=True)

        toolkit.register(MockTool())

        with pytest.raises(ValueError, match="already registered"):
            toolkit.register(MockTool())

    def test_get_tools_by_category(self):
        """Test getting tools by category."""
        toolkit = TradingToolkit()

        class PerceptionTool(BaseTool):
            @property
            def name(self) -> str:
                return "perception"

            @property
            def description(self) -> str:
                return "Perception"

            @property
            def category(self) -> ToolCategory:
                return ToolCategory.PERCEPTION

            @property
            def parameters(self) -> list[ToolParameter]:
                return []

            async def execute(self, **_kwargs):
                return ToolResult(success=True)

        class ExecutionTool(BaseTool):
            @property
            def name(self) -> str:
                return "execution"

            @property
            def description(self) -> str:
                return "Execution"

            @property
            def category(self) -> ToolCategory:
                return ToolCategory.EXECUTION

            @property
            def parameters(self) -> list[ToolParameter]:
                return []

            async def execute(self, **_kwargs):
                return ToolResult(success=True)

        toolkit.register(PerceptionTool())
        toolkit.register(ExecutionTool())

        perception_tools = toolkit.get_tools_by_category(ToolCategory.PERCEPTION)
        execution_tools = toolkit.get_tools_by_category(ToolCategory.EXECUTION)

        assert len(perception_tools) == 1
        assert len(execution_tools) == 1
        assert perception_tools[0].name == "perception"

    def test_get_guarded_tools(self):
        """Test getting guarded tools."""
        toolkit = TradingToolkit()

        class SafeTool(BaseTool):
            @property
            def name(self) -> str:
                return "safe"

            @property
            def description(self) -> str:
                return "Safe"

            @property
            def category(self) -> ToolCategory:
                return ToolCategory.ANALYSIS

            @property
            def parameters(self) -> list[ToolParameter]:
                return []

            async def execute(self, **_kwargs):
                return ToolResult(success=True)

        class GuardedTool(BaseTool):
            @property
            def name(self) -> str:
                return "guarded"

            @property
            def description(self) -> str:
                return "Guarded"

            @property
            def category(self) -> ToolCategory:
                return ToolCategory.EXECUTION

            @property
            def parameters(self) -> list[ToolParameter]:
                return []

            async def execute(self, **_kwargs):
                return ToolResult(success=True)

        toolkit.register(SafeTool())
        toolkit.register(GuardedTool())

        guarded = toolkit.get_guarded_tools()
        assert len(guarded) == 1
        assert guarded[0].name == "guarded"

    def test_get_anthropic_tools_schema(self):
        """Test getting Anthropic API format schemas."""
        toolkit = TradingToolkit()

        class Tool1(BaseTool):
            @property
            def name(self) -> str:
                return "tool1"

            @property
            def description(self) -> str:
                return "Tool 1"

            @property
            def category(self) -> ToolCategory:
                return ToolCategory.PERCEPTION

            @property
            def parameters(self) -> list[ToolParameter]:
                return [ToolParameter("param", "string", "Param", required=True)]

            async def execute(self, **_kwargs):
                return ToolResult(success=True)

        toolkit.register(Tool1())
        schemas = toolkit.get_anthropic_tools_schema()

        assert len(schemas) == 1
        assert schemas[0]["name"] == "tool1"
        assert "input_schema" in schemas[0]

    @pytest.mark.asyncio
    async def test_execute_tool(self):
        """Test executing a tool through the toolkit."""
        toolkit = TradingToolkit()

        class AddTool(BaseTool):
            @property
            def name(self) -> str:
                return "add"

            @property
            def description(self) -> str:
                return "Add two numbers"

            @property
            def category(self) -> ToolCategory:
                return ToolCategory.ANALYSIS

            @property
            def parameters(self) -> list[ToolParameter]:
                return [
                    ToolParameter("a", "number", "First number", required=True),
                    ToolParameter("b", "number", "Second number", required=True),
                ]

            async def execute(self, **kwargs):
                return ToolResult(success=True, data={"sum": kwargs["a"] + kwargs["b"]})

        toolkit.register(AddTool())
        result = await toolkit.execute("add", a=5, b=3)

        assert result.success is True
        assert result.data["sum"] == 8

    @pytest.mark.asyncio
    async def test_execute_nonexistent_tool(self):
        """Test executing a tool that doesn't exist."""
        toolkit = TradingToolkit()
        result = await toolkit.execute("nonexistent")

        assert result.success is False
        assert "not found" in result.error

    def test_list_tools(self):
        """Test listing tools by category."""
        toolkit = TradingToolkit()

        class Tool1(BaseTool):
            @property
            def name(self) -> str:
                return "tool1"

            @property
            def description(self) -> str:
                return "Tool1"

            @property
            def category(self) -> ToolCategory:
                return ToolCategory.PERCEPTION

            @property
            def parameters(self) -> list[ToolParameter]:
                return []

            async def execute(self, **_kwargs):
                return ToolResult(success=True)

        class Tool2(BaseTool):
            @property
            def name(self) -> str:
                return "tool2"

            @property
            def description(self) -> str:
                return "Tool2"

            @property
            def category(self) -> ToolCategory:
                return ToolCategory.PERCEPTION

            @property
            def parameters(self) -> list[ToolParameter]:
                return []

            async def execute(self, **_kwargs):
                return ToolResult(success=True)

        toolkit.register(Tool1())
        toolkit.register(Tool2())

        tools_list = toolkit.list_tools()
        assert "perception" in tools_list
        assert "tool1" in tools_list["perception"]
        assert "tool2" in tools_list["perception"]


class TestCreateToolDecorator:
    """Tests for the create_tool decorator."""

    @pytest.mark.asyncio
    async def test_create_tool_decorator(self):
        """Test creating a tool with the decorator."""

        @create_tool(
            name="get_answer",
            description="Returns the answer to everything",
            category=ToolCategory.ANALYSIS,
            parameters=[],
        )
        async def get_answer() -> ToolResult:
            return ToolResult(success=True, data={"answer": 42})

        tool = get_answer  # The decorator returns the tool instance

        assert tool.name == "get_answer"
        assert tool.category == ToolCategory.ANALYSIS

        result = await tool.execute()
        assert result.success is True
        assert result.data["answer"] == 42

    @pytest.mark.asyncio
    async def test_create_tool_with_params(self):
        """Test creating a tool with parameters."""

        @create_tool(
            name="multiply",
            description="Multiply two numbers",
            category=ToolCategory.ANALYSIS,
            parameters=[
                ToolParameter("a", "number", "First number", required=True),
                ToolParameter("b", "number", "Second number", required=True),
            ],
        )
        async def multiply(a: float, b: float) -> ToolResult:
            return ToolResult(success=True, data={"result": a * b})

        tool = multiply
        result = await tool.execute(a=7, b=6)

        assert result.success is True
        assert result.data["result"] == 42
