"""Tests for the Cognitive Agent."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from keryxflow.agent.cognitive import (
    AgentDecision,
    AgentStats,
    CognitiveAgent,
    CycleResult,
    CycleStatus,
    DecisionType,
    get_cognitive_agent,
)
from keryxflow.agent.tools import ToolResult


class TestCycleStatus:
    """Tests for CycleStatus enum."""

    def test_status_values(self):
        """Test cycle status values."""
        assert CycleStatus.SUCCESS.value == "success"
        assert CycleStatus.NO_ACTION.value == "no_action"
        assert CycleStatus.FALLBACK.value == "fallback"
        assert CycleStatus.ERROR.value == "error"
        assert CycleStatus.RATE_LIMITED.value == "rate_limited"


class TestDecisionType:
    """Tests for DecisionType enum."""

    def test_decision_type_values(self):
        """Test decision type values."""
        assert DecisionType.HOLD.value == "hold"
        assert DecisionType.ENTRY_LONG.value == "entry_long"
        assert DecisionType.ENTRY_SHORT.value == "entry_short"
        assert DecisionType.EXIT.value == "exit"
        assert DecisionType.ADJUST_STOP.value == "adjust_stop"
        assert DecisionType.ADJUST_TARGET.value == "adjust_target"


class TestAgentDecision:
    """Tests for AgentDecision dataclass."""

    def test_create_decision(self):
        """Test creating a decision."""
        decision = AgentDecision(
            decision_type=DecisionType.ENTRY_LONG,
            symbol="BTC/USDT",
            reasoning="Strong bullish signal",
            confidence=0.8,
        )

        assert decision.decision_type == DecisionType.ENTRY_LONG
        assert decision.symbol == "BTC/USDT"
        assert decision.reasoning == "Strong bullish signal"
        assert decision.confidence == 0.8
        assert decision.tool_calls == []
        assert decision.metadata == {}

    def test_decision_defaults(self):
        """Test decision default values."""
        decision = AgentDecision(decision_type=DecisionType.HOLD)

        assert decision.symbol is None
        assert decision.reasoning == ""
        assert decision.confidence == 0.0


class TestCycleResult:
    """Tests for CycleResult dataclass."""

    def test_create_result(self):
        """Test creating a cycle result."""
        decision = AgentDecision(decision_type=DecisionType.HOLD)
        result = CycleResult(
            status=CycleStatus.SUCCESS,
            decision=decision,
            duration_ms=150.5,
            tokens_used=500,
        )

        assert result.status == CycleStatus.SUCCESS
        assert result.decision == decision
        assert result.duration_ms == 150.5
        assert result.tokens_used == 500
        assert result.error is None

    def test_result_to_dict_success(self):
        """Test converting successful result to dict."""
        decision = AgentDecision(
            decision_type=DecisionType.ENTRY_LONG,
            symbol="ETH/USDT",
            reasoning="Test reasoning",
            confidence=0.75,
        )
        result = CycleResult(
            status=CycleStatus.SUCCESS,
            decision=decision,
            duration_ms=100.0,
            tokens_used=300,
        )
        result.completed_at = datetime.now(UTC)

        data = result.to_dict()

        assert data["status"] == "success"
        assert data["decision"]["type"] == "entry_long"
        assert data["decision"]["symbol"] == "ETH/USDT"
        assert data["decision"]["confidence"] == 0.75
        assert data["duration_ms"] == 100.0
        assert data["tokens_used"] == 300
        assert data["error"] is None

    def test_result_to_dict_error(self):
        """Test converting error result to dict."""
        result = CycleResult(
            status=CycleStatus.ERROR,
            error="API error",
        )

        data = result.to_dict()

        assert data["status"] == "error"
        assert data["decision"] is None
        assert data["error"] == "API error"


class TestAgentStats:
    """Tests for AgentStats dataclass."""

    def test_default_stats(self):
        """Test default statistics values."""
        stats = AgentStats()

        assert stats.total_cycles == 0
        assert stats.successful_cycles == 0
        assert stats.fallback_cycles == 0
        assert stats.error_cycles == 0
        assert stats.total_tool_calls == 0
        assert stats.total_tokens_used == 0
        assert stats.decisions_by_type == {}
        assert stats.last_cycle_time is None
        assert stats.consecutive_errors == 0


class TestCognitiveAgent:
    """Tests for CognitiveAgent class."""

    def test_create_agent(self):
        """Test creating a cognitive agent."""
        agent = CognitiveAgent()

        assert agent._initialized is False
        assert agent._running is False
        assert agent.toolkit is not None
        assert agent.executor is not None

    def test_agent_system_prompt(self):
        """Test that system prompt contains required elements."""
        prompt = CognitiveAgent.SYSTEM_PROMPT

        assert "KeryxFlow" in prompt
        assert "guardrails" in prompt.lower()
        assert "gather" in prompt.lower()  # Gather market data
        assert "decision" in prompt.lower()

    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test agent initialization."""
        agent = CognitiveAgent()

        # Mock the anthropic import
        with (
            patch.dict("sys.modules", {"anthropic": MagicMock()}),
            patch("keryxflow.config.get_settings") as mock_settings,
        ):
            mock_settings.return_value.anthropic_api_key.get_secret_value.return_value = ""
            await agent.initialize()

        assert agent._initialized is True
        assert agent.toolkit.tool_count > 0

    @pytest.mark.asyncio
    async def test_initialize_without_api_key(self):
        """Test agent initialization without API key."""
        agent = CognitiveAgent()

        with patch("keryxflow.config.get_settings") as mock_settings:
            mock_settings.return_value.anthropic_api_key.get_secret_value.return_value = ""
            await agent.initialize()

        assert agent._initialized is True
        assert agent._client is None

    @pytest.mark.asyncio
    async def test_run_cycle_no_client_fallback_disabled(self):
        """Test cycle returns error when no client and fallback disabled."""
        agent = CognitiveAgent()
        agent.settings.fallback_to_technical = False

        with patch("keryxflow.config.get_settings") as mock_settings:
            mock_settings.return_value.anthropic_api_key.get_secret_value.return_value = ""
            await agent.initialize()

        result = await agent.run_cycle(["BTC/USDT"])

        assert result.status == CycleStatus.ERROR
        assert "not available" in result.error

    @pytest.mark.asyncio
    async def test_run_cycle_fallback(self):
        """Test cycle falls back to technical signals."""
        agent = CognitiveAgent()
        agent.settings.fallback_to_technical = True

        with patch("keryxflow.config.get_settings") as mock_settings:
            mock_settings.return_value.anthropic_api_key.get_secret_value.return_value = ""
            mock_settings.return_value.system.symbols = ["BTC/USDT"]
            await agent.initialize()

        # Mock the executor
        agent.executor.execute = AsyncMock(
            return_value=ToolResult(
                success=True,
                data={
                    "ohlcv": [
                        [datetime.now(UTC).isoformat(), 50000, 51000, 49000, 50500, 1000]
                        for _ in range(100)
                    ]
                },
            )
        )

        # Mock signal generator
        with patch("keryxflow.oracle.signals.get_signal_generator") as mock_gen:
            mock_signal = MagicMock()
            mock_signal.signal_type.value = "hold"
            mock_signal.confidence = 0.5
            mock_gen.return_value.generate_signal = AsyncMock(return_value=mock_signal)

            result = await agent.run_cycle(["BTC/USDT"])

        assert result.status == CycleStatus.FALLBACK
        assert result.decision is not None

    @pytest.mark.asyncio
    async def test_build_context(self):
        """Test building context for agent."""
        agent = CognitiveAgent()

        with patch("keryxflow.config.get_settings") as mock_settings:
            mock_settings.return_value.anthropic_api_key.get_secret_value.return_value = ""
            await agent.initialize()

        # Mock executor
        agent.executor.execute = AsyncMock(
            return_value=ToolResult(
                success=True,
                data={"price": 50000.0},
            )
        )

        # Mock memory manager
        agent.memory.build_context_for_decision = AsyncMock(
            return_value={"similar_trades": [], "applicable_rules": []}
        )

        context = await agent._build_context(["BTC/USDT"])

        assert "symbols" in context
        assert "BTC/USDT" in context["symbols"]
        assert "market_data" in context
        assert "memory_context" in context

    def test_get_enabled_tools(self):
        """Test getting enabled tool schemas."""
        agent = CognitiveAgent()
        agent.settings.enable_perception = True
        agent.settings.enable_analysis = True
        agent.settings.enable_introspection = True
        agent.settings.enable_execution = True

        # Register tools first
        from keryxflow.agent.tools import register_all_tools

        register_all_tools(agent.toolkit)

        tools = agent._get_enabled_tools()

        assert len(tools) > 0
        assert all("name" in tool for tool in tools)
        assert all("description" in tool for tool in tools)

    def test_get_enabled_tools_subset(self):
        """Test getting subset of enabled tools."""
        agent = CognitiveAgent()
        agent.settings.enable_perception = True
        agent.settings.enable_analysis = False
        agent.settings.enable_introspection = False
        agent.settings.enable_execution = False

        from keryxflow.agent.tools import register_all_tools

        register_all_tools(agent.toolkit)

        tools = agent._get_enabled_tools()

        # Should only have perception tools
        tool_names = [t["name"] for t in tools]
        assert "get_current_price" in tool_names
        assert "calculate_indicators" not in tool_names

    def test_parse_decision_hold(self):
        """Test parsing HOLD decision."""
        agent = CognitiveAgent()

        decision = agent._parse_decision(
            "The market is uncertain, I recommend to HOLD for now.",
            [],
        )

        assert decision.decision_type == DecisionType.HOLD

    def test_parse_decision_with_order(self):
        """Test parsing decision with executed order."""
        agent = CognitiveAgent()

        tool_results = [
            ToolResult(
                success=True,
                data={"order_id": "123", "symbol": "BTC/USDT"},
            )
        ]

        decision = agent._parse_decision(
            "Going long on BTC with high confidence",
            tool_results,
        )

        assert decision.decision_type == DecisionType.ENTRY_LONG
        assert decision.symbol == "BTC/USDT"
        assert decision.confidence == 0.8

    def test_parse_decision_exit(self):
        """Test parsing EXIT decision."""
        agent = CognitiveAgent()

        tool_results = [
            ToolResult(
                success=True,
                data={"closed": True, "symbol": "ETH/USDT"},
            )
        ]

        decision = agent._parse_decision(
            "Closing position due to stop loss",
            tool_results,
        )

        assert decision.decision_type == DecisionType.EXIT

    def test_build_user_message(self):
        """Test building user message from context."""
        agent = CognitiveAgent()

        context = {
            "market_data": {
                "BTC/USDT": {"price": {"price": 50000.0}},
            },
            "memory_context": {
                "BTC/USDT": {"similar_trades": [1, 2], "applicable_rules": [1]},
            },
        }

        message = agent._build_user_message(context)

        assert "BTC/USDT" in message
        assert "$50000" in message
        assert "2 similar trades" in message
        assert "1 rules" in message

    def test_get_stats(self):
        """Test getting agent statistics."""
        agent = CognitiveAgent()
        agent._stats.total_cycles = 10
        agent._stats.successful_cycles = 8
        agent._stats.total_tokens_used = 5000

        stats = agent.get_stats()

        assert stats["total_cycles"] == 10
        assert stats["successful_cycles"] == 8
        assert stats["total_tokens_used"] == 5000
        assert stats["success_rate"] == 0.8

    def test_get_recent_cycles(self):
        """Test getting recent cycle history."""
        agent = CognitiveAgent()

        # Add some cycles
        for _ in range(5):
            agent._cycle_history.append(
                CycleResult(
                    status=CycleStatus.SUCCESS,
                    decision=AgentDecision(decision_type=DecisionType.HOLD),
                    duration_ms=100.0,
                )
            )

        recent = agent.get_recent_cycles(3)

        assert len(recent) == 3
        assert all(r["status"] == "success" for r in recent)

    def test_stop(self):
        """Test stopping the agent."""
        agent = CognitiveAgent()
        agent._running = True

        agent.stop()

        assert agent._running is False

    @pytest.mark.asyncio
    async def test_update_stats(self):
        """Test statistics update after cycle."""
        agent = CognitiveAgent()

        result = CycleResult(
            status=CycleStatus.SUCCESS,
            decision=AgentDecision(
                decision_type=DecisionType.ENTRY_LONG,
                symbol="BTC/USDT",
            ),
            tokens_used=500,
        )
        result.completed_at = datetime.now(UTC)

        agent._update_stats(result)

        assert agent._stats.total_cycles == 1
        assert agent._stats.successful_cycles == 1
        assert agent._stats.total_tokens_used == 500
        assert agent._stats.decisions_by_type.get("entry_long") == 1


class TestGetCognitiveAgent:
    """Tests for get_cognitive_agent function."""

    def test_returns_singleton(self):
        """Test that function returns singleton."""
        agent1 = get_cognitive_agent()
        agent2 = get_cognitive_agent()

        assert agent1 is agent2

    def test_creates_agent(self):
        """Test that function creates agent."""
        agent = get_cognitive_agent()

        assert isinstance(agent, CognitiveAgent)
