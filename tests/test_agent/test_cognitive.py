"""Tests for the Cognitive Agent."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from keryxflow.agent.cognitive import (
    AgentDecision,
    AgentResponse,
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
            input_tokens=200,
            output_tokens=100,
            total_cost=0.0021,
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
        assert data["total_cost"] == 0.0021
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
        assert stats.total_cost == 0.0
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
            mock_agent_settings.daily_token_budget = 0
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
            mock_agent_settings.daily_token_budget = 0  # Unlimited for test
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
                "BTC/USDT": {"similar_episodes": [1, 2], "matching_rules": [1]},
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
            input_tokens=300,
            output_tokens=200,
            total_cost=0.0039,
        )
        result.completed_at = datetime.now(UTC)

        agent._update_stats(result)

        assert agent._stats.total_cycles == 1
        assert agent._stats.successful_cycles == 1
        assert agent._stats.total_tokens_used == 500
        assert agent._stats.total_input_tokens == 300
        assert agent._stats.total_output_tokens == 200
        assert agent._stats.total_cost == pytest.approx(0.0039)
        assert agent._stats.decisions_by_type.get("entry_long") == 1

    @pytest.mark.asyncio
    async def test_update_stats_accumulates(self):
        """Test that stats accumulate across multiple cycles."""
        agent = CognitiveAgent()

        for _ in range(3):
            result = CycleResult(
                status=CycleStatus.SUCCESS,
                decision=AgentDecision(decision_type=DecisionType.HOLD),
                tokens_used=1000,
                input_tokens=700,
                output_tokens=300,
                total_cost=0.0066,
            )
            result.completed_at = datetime.now(UTC)
            agent._update_stats(result)

        assert agent._stats.total_cycles == 3
        assert agent._stats.total_tokens_used == 3000
        assert agent._stats.total_input_tokens == 2100
        assert agent._stats.total_output_tokens == 900
        assert agent._stats.total_cost == pytest.approx(0.0198)

    def test_calculate_cost(self):
        """Test cost calculation from token counts."""
        agent = CognitiveAgent()
        # Default pricing: $3/1M input, $15/1M output
        cost = agent._calculate_cost(1_000_000, 1_000_000)
        assert cost == pytest.approx(18.0)

        cost = agent._calculate_cost(500, 100)
        expected = (500 / 1_000_000) * 3.0 + (100 / 1_000_000) * 15.0
        assert cost == pytest.approx(expected)

    def test_calculate_cost_zero(self):
        """Test cost calculation with zero tokens."""
        agent = CognitiveAgent()
        cost = agent._calculate_cost(0, 0)
        assert cost == 0.0

    def test_get_token_stats(self):
        """Test get_token_stats returns correct dict."""
        agent = CognitiveAgent()
        agent._stats.total_tokens_used = 5000
        agent._stats.total_input_tokens = 3000
        agent._stats.total_output_tokens = 2000
        agent._stats.total_cost = 0.039
        agent._stats.total_cycles = 5

        stats = agent.get_token_stats()

        assert stats["total_tokens"] == 5000
        assert stats["total_input_tokens"] == 3000
        assert stats["total_output_tokens"] == 2000
        assert stats["total_cost"] == 0.039
        assert stats["avg_tokens_per_cycle"] == 1000
        assert stats["budget_exceeded"] is False
        assert stats["daily_token_budget"] == 1_000_000

    def test_get_token_stats_no_cycles(self):
        """Test get_token_stats with no cycles."""
        agent = CognitiveAgent()
        stats = agent.get_token_stats()

        assert stats["total_tokens"] == 0
        assert stats["avg_tokens_per_cycle"] == 0

    def test_budget_exceeded_flag(self):
        """Test that budget_exceeded flag triggers when budget is hit."""
        from keryxflow.config import AgentSettings

        settings = AgentSettings(daily_token_budget=1000)
        agent = CognitiveAgent(settings=settings)

        assert agent.budget_exceeded is False

        result = CycleResult(
            status=CycleStatus.SUCCESS,
            decision=AgentDecision(decision_type=DecisionType.HOLD),
            tokens_used=1000,
            input_tokens=700,
            output_tokens=300,
            total_cost=0.0066,
        )
        result.completed_at = datetime.now(UTC)
        agent._update_stats(result)

        assert agent.budget_exceeded is True

    def test_budget_exceeded_flag_unlimited(self):
        """Test that budget_exceeded stays False when budget is 0 (unlimited)."""
        from keryxflow.config import AgentSettings

        settings = AgentSettings(daily_token_budget=0)
        agent = CognitiveAgent(settings=settings)

        result = CycleResult(
            status=CycleStatus.SUCCESS,
            decision=AgentDecision(decision_type=DecisionType.HOLD),
            tokens_used=10_000_000,
            input_tokens=7_000_000,
            output_tokens=3_000_000,
            total_cost=66.0,
        )
        result.completed_at = datetime.now(UTC)
        agent._update_stats(result)

        assert agent.budget_exceeded is False

    def test_get_stats_includes_token_cost_fields(self):
        """Test that get_stats includes new token cost fields."""
        agent = CognitiveAgent()
        agent._stats.total_cycles = 10
        agent._stats.successful_cycles = 8
        agent._stats.total_tokens_used = 5000
        agent._stats.total_input_tokens = 3000
        agent._stats.total_output_tokens = 2000
        agent._stats.total_cost = 0.039

        stats = agent.get_stats()

        assert stats["total_input_tokens"] == 3000
        assert stats["total_output_tokens"] == 2000
        assert stats["total_cost"] == 0.039
        assert stats["avg_tokens_per_cycle"] == 500
        assert stats["budget_exceeded"] is False


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


class TestAgentResponse:
    """Tests for AgentResponse Pydantic model."""

    def test_valid_response(self):
        """Test creating a valid AgentResponse."""
        resp = AgentResponse(
            decision="hold",
            reasoning="Market is uncertain",
            confidence=0.5,
            symbol="BTC/USDT",
        )
        assert resp.decision == "hold"
        assert resp.reasoning == "Market is uncertain"
        assert resp.confidence == 0.5
        assert resp.symbol == "BTC/USDT"

    def test_valid_response_no_symbol(self):
        """Test AgentResponse without symbol."""
        resp = AgentResponse(
            decision="hold",
            reasoning="No action needed",
            confidence=0.3,
        )
        assert resp.symbol is None

    def test_invalid_confidence_too_high(self):
        """Test AgentResponse rejects confidence > 1.0."""
        with pytest.raises(ValidationError):
            AgentResponse(
                decision="hold",
                reasoning="test",
                confidence=1.5,
            )

    def test_invalid_confidence_too_low(self):
        """Test AgentResponse rejects confidence < 0.0."""
        with pytest.raises(ValidationError):
            AgentResponse(
                decision="hold",
                reasoning="test",
                confidence=-0.1,
            )

    def test_missing_required_fields(self):
        """Test AgentResponse requires decision and reasoning."""
        with pytest.raises(ValidationError):
            AgentResponse(confidence=0.5)


class TestStructuredParsing:
    """Tests for structured JSON parsing in _parse_decision."""

    def test_parse_json_code_block(self):
        """Test parsing decision from JSON code block."""
        agent = CognitiveAgent()
        reasoning = """Based on my analysis, I recommend holding.

```json
{"decision": "hold", "reasoning": "Market is ranging", "confidence": 0.6, "symbol": "BTC/USDT"}
```
"""
        decision = agent._parse_decision(reasoning, [])
        assert decision.decision_type == DecisionType.HOLD
        assert decision.confidence == 0.6
        assert decision.symbol == "BTC/USDT"
        assert "Market is ranging" in decision.reasoning

    def test_parse_inline_json(self):
        """Test parsing decision from inline JSON."""
        agent = CognitiveAgent()
        reasoning = 'I recommend: {"decision": "entry_long", "reasoning": "Bullish breakout", "confidence": 0.85, "symbol": "ETH/USDT"}'

        decision = agent._parse_decision(reasoning, [])
        assert decision.decision_type == DecisionType.ENTRY_LONG
        assert decision.confidence == 0.85
        assert decision.symbol == "ETH/USDT"

    def test_fallback_to_text_when_no_json(self):
        """Test fallback to text parsing when no JSON present."""
        agent = CognitiveAgent()
        reasoning = "The market is uncertain, I recommend to HOLD for now."

        decision = agent._parse_decision(reasoning, [])
        assert decision.decision_type == DecisionType.HOLD
        # Text fallback uses heuristic confidence
        assert decision.confidence == 0.5

    def test_fallback_on_invalid_json(self):
        """Test fallback when JSON is malformed."""
        agent = CognitiveAgent()
        reasoning = (
            '```json\n{"decision": "hold", "confidence": "not_a_number"}\n```\nI recommend holding.'
        )

        decision = agent._parse_decision(reasoning, [])
        # Should fall back to text parsing
        assert decision.decision_type == DecisionType.HOLD
        assert agent._stats.total_parse_failures == 1

    def test_fallback_on_invalid_schema(self):
        """Test fallback when JSON doesn't match schema."""
        agent = CognitiveAgent()
        reasoning = '```json\n{"action": "buy", "reason": "bullish"}\n```\nI think we should hold.'

        decision = agent._parse_decision(reasoning, [])
        # No "decision" key in JSON, so inline match fails, falls back to text
        assert decision.decision_type == DecisionType.HOLD

    def test_parse_failure_counter_increments(self):
        """Test that parse failures increment the counter."""
        agent = CognitiveAgent()

        # First failure
        agent._try_parse_structured('```json\n{"decision": "hold", "confidence": 999}\n```')
        assert agent._stats.total_parse_failures == 1

        # Second failure
        agent._try_parse_structured('```json\n{"decision": "hold", "confidence": -1}\n```')
        assert agent._stats.total_parse_failures == 2


class TestRetryLogic:
    """Tests for _call_claude retry behavior."""

    def test_call_claude_success(self):
        """Test _call_claude succeeds on first try."""
        agent = CognitiveAgent()
        mock_response = MagicMock()
        agent._client = MagicMock()
        agent._client.messages.create.return_value = mock_response

        result = agent._call_claude(
            system_prompt="test",
            tools=[],
            messages=[{"role": "user", "content": "hello"}],
        )

        assert result is mock_response
        assert agent._stats.total_retries == 0

    def test_call_claude_retries_on_failure(self):
        """Test _call_claude retries and succeeds."""
        agent = CognitiveAgent()
        mock_response = MagicMock()
        agent._client = MagicMock()
        agent._client.messages.create.side_effect = [
            ConnectionError("API error"),
            mock_response,
        ]

        result = agent._call_claude(
            system_prompt="test",
            tools=[],
            messages=[{"role": "user", "content": "hello"}],
        )

        assert result is mock_response
        assert agent._stats.total_retries == 1

    def test_call_claude_exhausts_retries(self):
        """Test _call_claude raises after retries exhausted."""
        agent = CognitiveAgent()
        agent._client = MagicMock()
        agent._client.messages.create.side_effect = ConnectionError("API down")

        with pytest.raises(ConnectionError):
            agent._call_claude(
                system_prompt="test",
                tools=[],
                messages=[{"role": "user", "content": "hello"}],
            )

        # Each failed attempt increments retry counter
        assert agent._stats.total_retries == 3


class TestTokenBudgetPreCheck:
    """Tests for token budget pre-check in run_cycle."""

    @pytest.mark.asyncio
    async def test_rate_limited_when_budget_exceeded(self):
        """Test run_cycle returns RATE_LIMITED when budget exceeded."""
        from keryxflow.config import AgentSettings

        settings = AgentSettings(daily_token_budget=1000, fallback_to_technical=False)
        agent = CognitiveAgent(settings=settings)
        agent._initialized = True
        agent._client = MagicMock()  # Client exists but budget exceeded
        agent.budget_exceeded = True

        result = await agent.run_cycle(["BTC/USDT"])

        assert result.status == CycleStatus.RATE_LIMITED
        assert "budget exceeded" in result.error.lower()

    @pytest.mark.asyncio
    async def test_fallback_when_budget_exceeded(self):
        """Test run_cycle falls back to technical when budget exceeded and fallback enabled."""
        from keryxflow.config import AgentSettings

        settings = AgentSettings(daily_token_budget=1000, fallback_to_technical=True)
        agent = CognitiveAgent(settings=settings)
        agent._initialized = True
        agent._client = MagicMock()
        agent.budget_exceeded = True

        # Mock the fallback cycle
        agent._run_fallback_cycle = AsyncMock(
            return_value=CycleResult(
                status=CycleStatus.FALLBACK,
                decision=AgentDecision(decision_type=DecisionType.HOLD),
            )
        )

        result = await agent.run_cycle(["BTC/USDT"])

        assert result.status == CycleStatus.FALLBACK
        agent._run_fallback_cycle.assert_called_once()


class TestNewStatsFields:
    """Tests for new stats fields."""

    def test_default_stats_include_new_fields(self):
        """Test that AgentStats includes retry and parse failure counters."""
        stats = AgentStats()
        assert stats.total_retries == 0
        assert stats.total_parse_failures == 0

    def test_get_stats_includes_new_fields(self):
        """Test that get_stats output includes retry and parse failure counts."""
        agent = CognitiveAgent()
        agent._stats.total_retries = 5
        agent._stats.total_parse_failures = 2

        stats = agent.get_stats()

        assert stats["total_retries"] == 5
        assert stats["total_parse_failures"] == 2

    def test_system_prompt_includes_json_format(self):
        """Test that SYSTEM_PROMPT includes JSON output format instructions."""
        prompt = CognitiveAgent.SYSTEM_PROMPT
        assert "```json" in prompt
        assert '"decision"' in prompt
        assert '"reasoning"' in prompt
        assert '"confidence"' in prompt
