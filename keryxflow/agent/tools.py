"""Agent tool framework for AI-first trading.

This module provides the base framework for creating tools that can be used
by the cognitive agent. Tools are compatible with Anthropic's Tool Use API.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from keryxflow.core.logging import get_logger

logger = get_logger(__name__)


class ToolCategory(str, Enum):
    """Categories of agent tools."""

    PERCEPTION = "perception"  # Read-only market data
    ANALYSIS = "analysis"  # Computation and analysis
    INTROSPECTION = "introspection"  # Memory and rules
    EXECUTION = "execution"  # Order execution (GUARDED)


@dataclass
class ToolParameter:
    """Definition of a tool parameter."""

    name: str
    type: str  # "string", "number", "integer", "boolean", "array", "object"
    description: str
    required: bool = True
    enum: list[str] | None = None
    default: Any = None
    items: dict[str, Any] | None = None  # For array types


@dataclass
class ToolResult:
    """Result of a tool execution."""

    success: bool
    data: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        result = {"success": self.success}
        if self.success:
            result["data"] = self.data
        else:
            result["error"] = self.error
        if self.metadata:
            result["metadata"] = self.metadata
        return result


class BaseTool(ABC):
    """Abstract base class for all agent tools.

    Tools must implement:
    - name: Unique identifier for the tool
    - description: What the tool does (for LLM)
    - category: Tool category (perception, analysis, execution, etc.)
    - parameters: List of ToolParameter definitions
    - execute(): Async method that performs the tool's action
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name of the tool."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what the tool does."""
        ...

    @property
    @abstractmethod
    def category(self) -> ToolCategory:
        """Category of the tool."""
        ...

    @property
    @abstractmethod
    def parameters(self) -> list[ToolParameter]:
        """List of parameters the tool accepts."""
        ...

    @property
    def is_guarded(self) -> bool:
        """Whether the tool requires guardrail validation."""
        return self.category == ToolCategory.EXECUTION

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with the given parameters.

        Args:
            **kwargs: Tool parameters as keyword arguments

        Returns:
            ToolResult with success status and data or error
        """
        ...

    def to_anthropic_schema(self) -> dict[str, Any]:
        """Convert tool to Anthropic Tool Use API format.

        Returns a schema compatible with:
        https://docs.anthropic.com/en/docs/tool-use
        """
        properties = {}
        required = []

        for param in self.parameters:
            prop: dict[str, Any] = {
                "type": param.type,
                "description": param.description,
            }

            if param.enum:
                prop["enum"] = param.enum

            if param.items:
                prop["items"] = param.items

            if param.default is not None:
                prop["default"] = param.default

            properties[param.name] = prop

            if param.required:
                required.append(param.name)

        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }

    def validate_parameters(self, **kwargs: Any) -> tuple[bool, str | None]:
        """Validate that required parameters are provided.

        Returns:
            Tuple of (is_valid, error_message)
        """
        for param in self.parameters:
            if param.required and param.name not in kwargs:
                return False, f"Missing required parameter: {param.name}"

            if param.name in kwargs:
                value = kwargs[param.name]
                # Type validation
                if param.type == "string" and not isinstance(value, str):
                    return False, f"Parameter {param.name} must be a string"
                elif param.type == "number" and not isinstance(value, int | float):
                    return False, f"Parameter {param.name} must be a number"
                elif param.type == "integer" and not isinstance(value, int):
                    return False, f"Parameter {param.name} must be an integer"
                elif param.type == "boolean" and not isinstance(value, bool):
                    return False, f"Parameter {param.name} must be a boolean"
                elif param.type == "array" and not isinstance(value, list):
                    return False, f"Parameter {param.name} must be an array"

                # Enum validation
                if param.enum and value not in param.enum:
                    return False, f"Parameter {param.name} must be one of: {param.enum}"

        return True, None


class TradingToolkit:
    """Registry and manager for trading tools.

    The toolkit manages all available tools and provides methods to:
    - Register tools
    - Get tool schemas for the LLM
    - Execute tools by name
    """

    def __init__(self) -> None:
        """Initialize the toolkit."""
        self._tools: dict[str, BaseTool] = {}
        self._tools_by_category: dict[ToolCategory, list[BaseTool]] = {
            category: [] for category in ToolCategory
        }

    def register(self, tool: BaseTool) -> None:
        """Register a tool with the toolkit.

        Args:
            tool: Tool instance to register

        Raises:
            ValueError: If a tool with the same name is already registered
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")

        self._tools[tool.name] = tool
        self._tools_by_category[tool.category].append(tool)

        logger.debug("tool_registered", name=tool.name, category=tool.category.value)

    def get_tool(self, name: str) -> BaseTool | None:
        """Get a tool by name.

        Args:
            name: Name of the tool

        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)

    def get_tools_by_category(self, category: ToolCategory) -> list[BaseTool]:
        """Get all tools in a category.

        Args:
            category: Tool category

        Returns:
            List of tools in the category
        """
        return self._tools_by_category[category].copy()

    def get_all_tools(self) -> list[BaseTool]:
        """Get all registered tools.

        Returns:
            List of all tools
        """
        return list(self._tools.values())

    def get_guarded_tools(self) -> list[BaseTool]:
        """Get all tools that require guardrail validation.

        Returns:
            List of guarded tools (execution tools)
        """
        return [tool for tool in self._tools.values() if tool.is_guarded]

    def get_anthropic_tools_schema(
        self, categories: list[ToolCategory] | None = None
    ) -> list[dict[str, Any]]:
        """Get tool schemas in Anthropic Tool Use API format.

        Args:
            categories: Optional list of categories to include.
                       If None, all categories are included.

        Returns:
            List of tool schemas for the API
        """
        tools = []

        for tool in self._tools.values():
            if categories is None or tool.category in categories:
                tools.append(tool.to_anthropic_schema())

        return tools

    async def execute(self, tool_name: str, **kwargs: Any) -> ToolResult:
        """Execute a tool by name.

        Note: This method does NOT perform guardrail validation.
        Use ToolExecutor for guarded execution.

        Args:
            tool_name: Name of the tool to execute
            **kwargs: Tool parameters

        Returns:
            ToolResult from the tool execution
        """
        tool = self.get_tool(tool_name)
        if tool is None:
            return ToolResult(
                success=False,
                error=f"Tool '{tool_name}' not found",
            )

        # Validate parameters
        is_valid, error = tool.validate_parameters(**kwargs)
        if not is_valid:
            return ToolResult(
                success=False,
                error=error,
            )

        try:
            result = await tool.execute(**kwargs)
            logger.info(
                "tool_executed",
                tool=tool_name,
                success=result.success,
                category=tool.category.value,
            )
            return result
        except Exception as e:
            logger.error("tool_execution_failed", tool=tool_name, error=str(e))
            return ToolResult(
                success=False,
                error=f"Tool execution failed: {str(e)}",
            )

    def list_tools(self) -> dict[str, list[str]]:
        """List all tools grouped by category.

        Returns:
            Dictionary mapping category names to tool names
        """
        return {
            category.value: [tool.name for tool in tools]
            for category, tools in self._tools_by_category.items()
            if tools
        }

    @property
    def tool_count(self) -> int:
        """Get the number of registered tools."""
        return len(self._tools)


def create_tool(
    name: str,
    description: str,
    category: ToolCategory,
    parameters: list[ToolParameter],
):
    """Decorator to create a tool from an async function.

    Example:
        @create_tool(
            name="get_price",
            description="Get current price for a symbol",
            category=ToolCategory.PERCEPTION,
            parameters=[
                ToolParameter("symbol", "string", "Trading pair symbol", required=True)
            ]
        )
        async def get_price(symbol: str) -> ToolResult:
            price = await fetch_price(symbol)
            return ToolResult(success=True, data={"price": price})
    """

    def decorator(func):
        class FunctionalTool(BaseTool):
            @property
            def name(self) -> str:
                return name

            @property
            def description(self) -> str:
                return description

            @property
            def category(self) -> ToolCategory:
                return category

            @property
            def parameters(self) -> list[ToolParameter]:
                return parameters

            async def execute(self, **kwargs: Any) -> ToolResult:
                return await func(**kwargs)

        return FunctionalTool()

    return decorator


# Global toolkit instance
_toolkit: TradingToolkit | None = None


def get_trading_toolkit() -> TradingToolkit:
    """Get the global trading toolkit instance."""
    global _toolkit
    if _toolkit is None:
        _toolkit = TradingToolkit()
    return _toolkit


def register_all_tools(toolkit: TradingToolkit | None = None) -> TradingToolkit:
    """Register all available tools with the toolkit.

    Args:
        toolkit: Toolkit to register tools with. If None, uses global toolkit.

    Returns:
        The toolkit with all tools registered
    """
    if toolkit is None:
        toolkit = get_trading_toolkit()

    # Import and register tools from each module
    # These imports trigger tool registration
    from keryxflow.agent.analysis_tools import register_analysis_tools
    from keryxflow.agent.execution_tools import register_execution_tools
    from keryxflow.agent.perception_tools import register_perception_tools

    register_perception_tools(toolkit)
    register_analysis_tools(toolkit)
    register_execution_tools(toolkit)

    logger.info("all_tools_registered", count=toolkit.tool_count)

    return toolkit
