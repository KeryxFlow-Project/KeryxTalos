"""Tests for the Cognitive Agent."""

import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from keryxflow.agent.cognitive import (
    MAKE_DECISION_TOOL,
    AgentDecision,
    AgentStats,
    CircuitState,
    CognitiveAgent,
    CycleResult,
    CycleStatus,
    DecisionType,
    _is_retryable_api_error,
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


class TestCircuitState:
    """Tests for CircuitState enum."""

    def test_circuit_state_values(self):
        """Test circuit state values."""
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"


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
            input_tokens=200,
            output_tokens=100,
            cost_usd=0.002,
        )
        result.completed_at = datetime.now(UTC)

        data = result.to_dict()

        assert data["status"] == "success"
        assert data["decision"]["type"] == "entry_long"
        assert data["decision"]["symbol"] == "ETH/USDT"
        assert data["decision"]["confidence"] == 0.75
        assert data["duration_ms"] == 100.0
        assert data["tokens_used"] == 300
        assert data["input_tokens"] == 200
        assert data["output_tokens"] == 100
        assert data["cost_usd"] == 0.002
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
        assert stats.total_input_tokens == 0
        assert stats.total_output_tokens == 0
        assert stats.total_cost_usd == 0.0
        assert stats.decisions_by_type == {}
        assert stats.last_cycle_time is None
        assert stats.consecutive_errors == 0
        assert stats.circuit_state == CircuitState.CLOSED
        assert stats.circuit_opened_at is None


class TestIsRetryableApiError:
    """Tests for _is_retryable_api_error."""

    def test_rate_limit_error(self):
        """Test rate limit errors are retryable."""
        assert _is_retryable_api_error(Exception("429 rate limit exceeded"))

    def test_server_errors_retryable(self):
        """Test server errors are retryable."""
        assert _is_retryable_api_error(Exception("500 internal server error"))
        assert _is_retryable_api_error(Exception("502 bad gateway"))
        assert _is_retryable_api_error(Exception("503 service unavailable"))
        assert _is_retryable_api_error(Exception("504 gateway timeout"))

    def test_connection_errors_retryable(self):
        """Test connection errors are retryable."""
        assert _is_retryable_api_error(Exception("connection refused"))
        assert _is_retryable_api_error(Exception("timeout"))
        assert _is_retryable_api_error(Exception("overloaded"))

    def test_exception_type_names_retryable(self):
        """Test exception type names trigger retry."""

        class RateLimitError(Exception):
            pass

        class InternalServerError(Exception):
            pass

        class APIConnectionError(Exception):
            pass

        class APITimeoutError(Exception):
            pass

        class OverloadedError(Exception):
            pass

        assert _is_retryable_api_error(RateLimitError("test"))
        assert _is_retryable_api_error(InternalServerError("test"))
        assert _is_retryable_api_error(APIConnectionError("test"))
        assert _is_retryable_api_error(APITimeoutError("test"))
        assert _is_retryable_api_error(OverloadedError("test"))

    def test_non_retryable_errors(self):
        """Test non-retryable errors."""
        assert not _is_retryable_api_error(Exception("invalid api key"))
        assert not _is_retryable_api_error(Exception("bad request"))
        assert not _is_retryable_api_error(ValueError("wrong value"))


class TestMakeDecisionTool:
    """Tests for MAKE_DECISION_TOOL schema."""

    def test_schema_structure(self):
        """Test make_decision tool schema is well-formed."""
        assert MAKE_DECISION_TOOL["name"] == "make_decision"
        assert "description" in MAKE_DECISION_TOOL
        schema = MAKE_DECISION_TOOL["input_schema"]
        assert schema["type"] == "object"
        assert "decision_type" in schema["properties"]
        assert "confidence" in schema["properties"]
        assert "reasoning" in schema["properties"]
        assert "symbol" in schema["properties"]
        assert set(schema["required"]) == {"decision_type", "confidence", "reasoning"}

    def test_decision_type_enum(self):
        """Test decision_type has correct enum values."""
        enum_values = MAKE_DECISION_TOOL["input_schema"]["properties"]["decision_type"]["enum"]
        expected = ["hold", "entry_long", "entry_short", "exit", "adjust_stop", "adjust_target"]
        assert enum_values == expected


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
        assert "make_decision" in prompt  # References structured tool

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
        with patch("keryxflow.agent.cognitive.get_settings") as mock_settings:
            mock_settings.return_value.agent = MagicMock()
            mock_settings.return_value.anthropic_api_key.get_secret_value.return_value = ""
            agent = CognitiveAgent()
            await agent.initialize()

        assert agent._initialized is True
        assert agent._client is None

    @pytest.mark.asyncio
    async def test_run_cycle_no_client_fallback_disabled(self):
        """Test cycle returns error when no client and fallback disabled."""
        with patch("keryxflow.agent.cognitive.get_settings") as mock_settings:
            mock_agent_settings = MagicMock()
            mock_agent_settings.fallback_to_technical = False
            mock_settings.return_value.agent = mock_agent_settings
            mock_settings.return_value.anthropic_api_key.get_secret_value.return_value = ""
            mock_settings.return_value.system.symbols = ["BTC/USDT"]

            agent = CognitiveAgent()
            await agent.initialize()

            result = await agent.run_cycle(["BTC/USDT"])

        assert result.status == CycleStatus.ERROR
        assert "not available" in result.error

    @pytest.mark.asyncio
    async def test_run_cycle_fallback(self):
        """Test cycle falls back to technical signals."""
        with patch("keryxflow.agent.cognitive.get_settings") as mock_settings:
            mock_agent_settings = MagicMock()
            mock_agent_settings.fallback_to_technical = True
            mock_agent_settings.max_consecutive_errors = 1
            mock_settings.return_value.agent = mock_agent_settings
            mock_settings.return_value.anthropic_api_key.get_secret_value.return_value = ""
            mock_settings.return_value.system.symbols = ["BTC/USDT"]

            agent = CognitiveAgent()
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
        with patch("keryxflow.agent.cognitive.get_settings") as mock_settings:
            mock_settings.return_value.agent = MagicMock()
            mock_settings.return_value.anthropic_api_key.get_secret_value.return_value = ""

            agent = CognitiveAgent()
            await agent.initialize()

        # Mock executor
        agent.executor.execute = AsyncMock(
            return_value=ToolResult(
                success=True,
                data={"price": 50000.0},
            )
        )

        # Mock memory manager - return object with to_dict method
        mock_memory_context = MagicMock()
        mock_memory_context.to_dict.return_value = {
            "similar_episodes": [],
            "matching_rules": [],
        }
        agent.memory.build_context_for_decision = AsyncMock(return_value=mock_memory_context)

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

    def test_parse_structured_decision_valid(self):
        """Test parsing a valid structured decision."""
        agent = CognitiveAgent()

        decision = agent._parse_structured_decision(
            {
                "decision_type": "entry_long",
                "symbol": "BTC/USDT",
                "confidence": 0.85,
                "reasoning": "Strong bullish divergence on RSI",
            }
        )

        assert decision.decision_type == DecisionType.ENTRY_LONG
        assert decision.symbol == "BTC/USDT"
        assert decision.confidence == 0.85
        assert "bullish divergence" in decision.reasoning

    def test_parse_structured_decision_hold(self):
        """Test parsing a HOLD decision."""
        agent = CognitiveAgent()

        decision = agent._parse_structured_decision(
            {
                "decision_type": "hold",
                "confidence": 0.6,
                "reasoning": "No clear signal",
            }
        )

        assert decision.decision_type == DecisionType.HOLD
        assert decision.symbol is None
        assert decision.confidence == 0.6

    def test_parse_structured_decision_invalid_type_defaults_hold(self):
        """Test invalid decision_type defaults to HOLD."""
        agent = CognitiveAgent()

        decision = agent._parse_structured_decision(
            {
                "decision_type": "invalid_type",
                "confidence": 0.5,
                "reasoning": "Test",
            }
        )

        assert decision.decision_type == DecisionType.HOLD

    def test_parse_structured_decision_missing_type_defaults_hold(self):
        """Test missing decision_type defaults to HOLD."""
        agent = CognitiveAgent()

        decision = agent._parse_structured_decision(
            {
                "confidence": 0.5,
                "reasoning": "Test",
            }
        )

        assert decision.decision_type == DecisionType.HOLD

    def test_parse_structured_decision_confidence_clamped(self):
        """Test confidence is clamped to [0, 1]."""
        agent = CognitiveAgent()

        # Over 1.0
        decision = agent._parse_structured_decision(
            {
                "decision_type": "hold",
                "confidence": 1.5,
                "reasoning": "Test",
            }
        )
        assert decision.confidence == 1.0

        # Below 0.0
        decision = agent._parse_structured_decision(
            {
                "decision_type": "hold",
                "confidence": -0.5,
                "reasoning": "Test",
            }
        )
        assert decision.confidence == 0.0

    def test_parse_structured_decision_non_numeric_confidence(self):
        """Test non-numeric confidence defaults to 0.0."""
        agent = CognitiveAgent()

        decision = agent._parse_structured_decision(
            {
                "decision_type": "hold",
                "confidence": "high",
                "reasoning": "Test",
            }
        )
        assert decision.confidence == 0.0

    def test_parse_structured_decision_reasoning_truncated(self):
        """Test reasoning is truncated to 500 chars."""
        agent = CognitiveAgent()

        long_reasoning = "x" * 1000
        decision = agent._parse_structured_decision(
            {
                "decision_type": "hold",
                "confidence": 0.5,
                "reasoning": long_reasoning,
            }
        )
        assert len(decision.reasoning) == 500

    def test_parse_structured_decision_all_types(self):
        """Test all valid decision types."""
        agent = CognitiveAgent()

        for dt in DecisionType:
            decision = agent._parse_structured_decision(
                {
                    "decision_type": dt.value,
                    "confidence": 0.5,
                    "reasoning": f"Test {dt.value}",
                }
            )
            assert decision.decision_type == dt

    def test_calculate_cost(self):
        """Test cost calculation."""
        agent = CognitiveAgent()
        agent.settings.input_cost_per_1k = 0.003
        agent.settings.output_cost_per_1k = 0.015

        cost = agent._calculate_cost(1000, 1000)
        assert cost == pytest.approx(0.018, abs=0.0001)

    def test_calculate_cost_zero_tokens(self):
        """Test cost with zero tokens."""
        agent = CognitiveAgent()
        cost = agent._calculate_cost(0, 0)
        assert cost == 0.0

    def test_build_user_message(self):
        """Test building user message from context."""
        agent = CognitiveAgent()

        context = {
            "market_data": {
                "BTC/USDT": {"price": {"price": 50000.0}},
            },
            "memory_context": {
                "BTC/USDT": {"similar_episodes": [1, 2], "matching_rules": [1]},
            },
        }

        message = agent._build_user_message(context)

        assert "BTC/USDT" in message
        assert "$50000" in message
        assert "2 similar trades" in message
        assert "1 rules" in message
        assert "make_decision" in message

    def test_get_stats(self):
        """Test getting agent statistics."""
        agent = CognitiveAgent()
        agent._stats.total_cycles = 10
        agent._stats.successful_cycles = 8
        agent._stats.total_tokens_used = 5000
        agent._stats.total_input_tokens = 3000
        agent._stats.total_output_tokens = 2000
        agent._stats.total_cost_usd = 0.15

        stats = agent.get_stats()

        assert stats["total_cycles"] == 10
        assert stats["successful_cycles"] == 8
        assert stats["total_tokens_used"] == 5000
        assert stats["total_input_tokens"] == 3000
        assert stats["total_output_tokens"] == 2000
        assert stats["total_cost_usd"] == 0.15
        assert stats["success_rate"] == 0.8
        assert stats["circuit_state"] == "closed"

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
            input_tokens=300,
            output_tokens=200,
            cost_usd=0.01,
        )
        result.completed_at = datetime.now(UTC)

        agent._update_stats(result)

        assert agent._stats.total_cycles == 1
        assert agent._stats.successful_cycles == 1
        assert agent._stats.total_tokens_used == 500
        assert agent._stats.total_input_tokens == 300
        assert agent._stats.total_output_tokens == 200
        assert agent._stats.total_cost_usd == 0.01
        assert agent._stats.decisions_by_type.get("entry_long") == 1


class TestCircuitBreaker:
    """Tests for circuit breaker functionality."""

    def test_circuit_starts_closed(self):
        """Test circuit breaker starts in CLOSED state."""
        agent = CognitiveAgent()
        assert agent._stats.circuit_state == CircuitState.CLOSED

    def test_check_circuit_breaker_closed(self):
        """Test CLOSED state allows calls."""
        agent = CognitiveAgent()
        assert agent._check_circuit_breaker() is True

    def test_trip_circuit_breaker(self):
        """Test tripping the circuit breaker."""
        agent = CognitiveAgent()
        agent._stats.consecutive_errors = 3
        agent._trip_circuit_breaker()

        assert agent._stats.circuit_state == CircuitState.OPEN
        assert agent._stats.circuit_opened_at is not None

    def test_open_circuit_blocks_calls(self):
        """Test OPEN state blocks calls."""
        agent = CognitiveAgent()
        agent._stats.circuit_state = CircuitState.OPEN
        agent._stats.circuit_opened_at = time.monotonic()
        agent.settings.circuit_breaker_cooldown = 300

        assert agent._check_circuit_breaker() is False

    def test_open_circuit_transitions_to_half_open_after_cooldown(self):
        """Test OPEN -> HALF_OPEN transition after cooldown."""
        agent = CognitiveAgent()
        agent._stats.circuit_state = CircuitState.OPEN
        # Set opened_at to past time (beyond cooldown)
        agent._stats.circuit_opened_at = time.monotonic() - 400
        agent.settings.circuit_breaker_cooldown = 300

        assert agent._check_circuit_breaker() is True
        assert agent._stats.circuit_state == CircuitState.HALF_OPEN

    def test_half_open_allows_probe(self):
        """Test HALF_OPEN state allows a probe call."""
        agent = CognitiveAgent()
        agent._stats.circuit_state = CircuitState.HALF_OPEN

        assert agent._check_circuit_breaker() is True

    def test_reset_circuit_breaker(self):
        """Test resetting the circuit breaker."""
        agent = CognitiveAgent()
        agent._stats.circuit_state = CircuitState.OPEN
        agent._stats.circuit_opened_at = time.monotonic()

        agent._reset_circuit_breaker()

        assert agent._stats.circuit_state == CircuitState.CLOSED
        assert agent._stats.circuit_opened_at is None

    @pytest.mark.asyncio
    async def test_circuit_trips_after_consecutive_errors(self):
        """Test circuit breaker trips after max consecutive errors."""
        with patch("keryxflow.agent.cognitive.get_settings") as mock_settings:
            mock_agent_settings = MagicMock()
            mock_agent_settings.fallback_to_technical = False
            mock_agent_settings.max_consecutive_errors = 3
            mock_agent_settings.circuit_breaker_cooldown = 300
            mock_agent_settings.model = "test-model"
            mock_agent_settings.max_tokens = 100
            mock_agent_settings.temperature = 0.3
            mock_agent_settings.max_tool_calls_per_cycle = 5
            mock_agent_settings.enable_perception = True
            mock_agent_settings.enable_analysis = False
            mock_agent_settings.enable_introspection = False
            mock_agent_settings.enable_execution = False
            mock_agent_settings.input_cost_per_1k = 0.003
            mock_agent_settings.output_cost_per_1k = 0.015
            mock_settings.return_value.agent = mock_agent_settings
            mock_settings.return_value.anthropic_api_key.get_secret_value.return_value = "test-key"
            mock_settings.return_value.system.symbols = ["BTC/USDT"]

            agent = CognitiveAgent()
            await agent.initialize()

            # Mock client to always fail
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = Exception("API error")
            agent._client = mock_client

            # Run cycles that fail
            for _ in range(3):
                await agent.run_cycle(["BTC/USDT"])

            assert agent._stats.consecutive_errors == 3
            assert agent._stats.circuit_state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_circuit_open_falls_back(self):
        """Test open circuit falls back to technical signals."""
        with patch("keryxflow.agent.cognitive.get_settings") as mock_settings:
            mock_agent_settings = MagicMock()
            mock_agent_settings.fallback_to_technical = True
            mock_agent_settings.circuit_breaker_cooldown = 300
            mock_settings.return_value.agent = mock_agent_settings
            mock_settings.return_value.anthropic_api_key.get_secret_value.return_value = "test-key"
            mock_settings.return_value.system.symbols = ["BTC/USDT"]

            agent = CognitiveAgent()
            await agent.initialize()
            agent._client = MagicMock()  # Has client but circuit is open

            # Set circuit to open
            agent._stats.circuit_state = CircuitState.OPEN
            agent._stats.circuit_opened_at = time.monotonic()

            # Mock fallback
            agent.executor.execute = AsyncMock(
                return_value=ToolResult(success=True, data={"ohlcv": []})
            )

            result = await agent.run_cycle(["BTC/USDT"])

            assert result.status == CycleStatus.FALLBACK

    @pytest.mark.asyncio
    async def test_circuit_resets_on_success(self):
        """Test circuit breaker resets on successful cycle."""
        agent = CognitiveAgent()
        agent._stats.circuit_state = CircuitState.HALF_OPEN
        agent._stats.consecutive_errors = 2

        # Simulate a successful cycle resetting the breaker
        agent._stats.consecutive_errors = 0
        agent._reset_circuit_breaker()

        assert agent._stats.circuit_state == CircuitState.CLOSED
        assert agent._stats.consecutive_errors == 0


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
