"""Base class for specialized trading agents.

Provides the SpecializedAgent ABC, AgentRole enum, and shared data structures
for the multi-agent architecture (Analyst → Risk → Executor pipeline).
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from keryxflow.agent.executor import ToolExecutor, get_tool_executor
from keryxflow.agent.tools import (
    ToolCategory,
    ToolResult,
    TradingToolkit,
    get_trading_toolkit,
    register_all_tools,
)
from keryxflow.config import AgentSettings, get_settings
from keryxflow.core.events import get_event_bus
from keryxflow.core.logging import get_logger

logger = get_logger(__name__)


class AgentRole(StrEnum):
    """Roles for specialized agents."""

    ANALYST = "analyst"
    RISK = "risk"
    EXECUTOR = "executor"


@dataclass
class MarketAnalysis:
    """Result from the AnalystAgent."""

    symbol: str
    signal: str  # "long", "short", "hold"
    confidence: float = 0.0
    key_indicators: dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""
    tool_results: list[ToolResult] = field(default_factory=list)
    tokens_used: int = 0


@dataclass
class RiskAssessment:
    """Result from the RiskAgent."""

    approved: bool = False
    position_size: float = 0.0
    stop_loss: float | None = None
    take_profit: float | None = None
    risk_score: float = 0.0
    risk_reward_ratio: float = 0.0
    reasoning: str = ""
    tool_results: list[ToolResult] = field(default_factory=list)
    tokens_used: int = 0


@dataclass
class ExecutionResult:
    """Result from the ExecutorAgent."""

    executed: bool = False
    order_id: str | None = None
    symbol: str | None = None
    side: str | None = None
    quantity: float = 0.0
    price: float = 0.0
    reasoning: str = ""
    tool_results: list[ToolResult] = field(default_factory=list)
    tokens_used: int = 0


class SpecializedAgent(ABC):
    """Abstract base class for specialized trading agents.

    Each specialized agent:
    - Has a defined role (analyst, risk, executor)
    - Accesses only its allowed tool categories
    - Has a focused system prompt for its role
    - Calls Claude with scoped tools and returns structured results
    """

    def __init__(
        self,
        toolkit: TradingToolkit | None = None,
        executor: ToolExecutor | None = None,
        settings: AgentSettings | None = None,
    ):
        self.settings = settings or get_settings().agent
        self.toolkit = toolkit or get_trading_toolkit()
        self.executor = executor or get_tool_executor()
        self._event_bus = get_event_bus()
        self._initialized = False
        self._client: Any = None

    @property
    @abstractmethod
    def role(self) -> AgentRole:
        """The role of this agent."""
        ...

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """The system prompt for this agent."""
        ...

    @property
    @abstractmethod
    def allowed_categories(self) -> list[ToolCategory]:
        """Tool categories this agent can use."""
        ...

    async def initialize(self) -> None:
        """Initialize the agent and Anthropic client."""
        if self._initialized:
            return

        # Ensure tools are registered
        if self.toolkit.tool_count == 0:
            register_all_tools(self.toolkit)

        try:
            import anthropic

            settings = get_settings()
            api_key = settings.anthropic_api_key.get_secret_value()

            if not api_key:
                logger.warning("anthropic_api_key_not_configured", role=self.role.value)
                self._client = None
            else:
                self._client = anthropic.Anthropic(api_key=api_key)

        except ImportError:
            logger.error("anthropic_package_not_installed")
            self._client = None

        self._initialized = True
        logger.info(
            "specialized_agent_initialized",
            role=self.role.value,
            tools=len(self._get_tool_schemas()),
        )

    def _get_model(self) -> str:
        """Get the model to use for this agent."""
        model_attr = f"{self.role.value}_model"
        model = getattr(self.settings, model_attr, None)
        return model or self.settings.model

    def _get_tool_schemas(self) -> list[dict[str, Any]]:
        """Get Anthropic tool schemas for allowed categories."""
        return self.toolkit.get_anthropic_tools_schema(self.allowed_categories)

    async def _call_claude(
        self,
        user_message: str,
        max_iterations: int | None = None,
    ) -> tuple[str, list[ToolResult], int]:
        """Call Claude with the agent's scoped tools and iterate on tool use.

        Args:
            user_message: The user message to send
            max_iterations: Max tool-use iterations (defaults to settings)

        Returns:
            Tuple of (final_text, tool_results, tokens_used)
        """
        if self._client is None:
            raise RuntimeError(f"{self.role.value} agent: Anthropic client not available")

        system = self.system_prompt.format(
            current_time=datetime.now(UTC).isoformat(),
        )
        tools = self._get_tool_schemas()
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
        tool_results: list[ToolResult] = []
        total_tokens = 0
        max_iter = max_iterations or self.settings.max_tool_calls_per_cycle

        for _iteration in range(max_iter):
            response = self._client.messages.create(
                model=self._get_model(),
                max_tokens=self.settings.max_tokens,
                temperature=self.settings.temperature,
                system=system,
                tools=tools,
                messages=messages,
            )

            total_tokens += response.usage.input_tokens + response.usage.output_tokens

            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

            if not tool_use_blocks:
                text_blocks = [b for b in response.content if b.type == "text"]
                reasoning = " ".join(b.text for b in text_blocks)
                return reasoning, tool_results, total_tokens

            # Execute tool calls
            tool_call_results = []
            for tool_block in tool_use_blocks:
                # Verify the tool is in our allowed categories
                tool = self.toolkit.get_tool(tool_block.name)
                if tool and tool.category in self.allowed_categories:
                    result = await self.executor.execute(tool_block.name, **tool_block.input)
                else:
                    result = ToolResult(
                        success=False,
                        error=f"Tool '{tool_block.name}' is not available to {self.role.value} agent",
                    )
                tool_results.append(result)

                tool_call_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_block.id,
                        "content": json.dumps(result.to_dict()),
                    }
                )

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_call_results})

            if response.stop_reason == "end_turn":
                break

        # Max iterations reached
        logger.warning(
            "agent_max_iterations",
            role=self.role.value,
            iterations=max_iter,
        )
        return "", tool_results, total_tokens
