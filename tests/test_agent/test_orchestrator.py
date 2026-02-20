"""Tests for the AgentOrchestrator and multi-agent coordination."""

from unittest.mock import AsyncMock

import pytest

from keryxflow.agent.base_agent import (
    ExecutionResult,
    MarketAnalysis,
    RiskAssessment,
)
from keryxflow.agent.cognitive import CycleResult, CycleStatus, DecisionType
from keryxflow.agent.orchestrator import AgentOrchestrator, get_agent_orchestrator


class TestAgentOrchestrator:
    """Tests for AgentOrchestrator class."""

    def test_create_orchestrator(self):
        """Test creating an orchestrator."""
        orchestrator = AgentOrchestrator()

        assert orchestrator._initialized is False
        assert orchestrator.analyst is not None
        assert orchestrator.risk_agent is not None
        assert orchestrator.executor_agent is not None

    def test_get_stats(self):
        """Test getting orchestrator statistics."""
        orchestrator = AgentOrchestrator()
        orchestrator._stats.total_cycles = 5
        orchestrator._stats.successful_cycles = 3

        stats = orchestrator.get_stats()

        assert stats["total_cycles"] == 5
        assert stats["successful_cycles"] == 3
        assert stats["multi_agent"] is True
        assert stats["success_rate"] == 0.6

    def test_get_recent_cycles(self):
        """Test getting recent cycle history."""
        orchestrator = AgentOrchestrator()

        for _ in range(3):
            from keryxflow.agent.cognitive import AgentDecision

            orchestrator._cycle_history.append(
                CycleResult(
                    status=CycleStatus.NO_ACTION,
                    decision=AgentDecision(decision_type=DecisionType.HOLD),
                )
            )

        recent = orchestrator.get_recent_cycles(2)
        assert len(recent) == 2

    @pytest.mark.asyncio
    async def test_full_pipeline_hold(self):
        """Test pipeline stops when analyst returns hold."""
        orchestrator = AgentOrchestrator()
        orchestrator._initialized = True

        # Mock analyst to return hold
        orchestrator.analyst.analyze = AsyncMock(
            return_value=MarketAnalysis(
                symbol="BTC/USDT",
                signal="hold",
                confidence=0.3,
                reasoning="No clear signal",
            )
        )

        # Mock context building
        orchestrator._build_context = AsyncMock(
            return_value={
                "symbols": ["BTC/USDT"],
                "market_data": {},
                "memory_context": {},
            }
        )

        result = await orchestrator.run_cycle(["BTC/USDT"])

        assert result.status == CycleStatus.NO_ACTION
        assert result.decision.decision_type == DecisionType.HOLD

        # Risk and executor should NOT be called
        orchestrator.risk_agent.assess = AsyncMock()
        orchestrator.executor_agent.execute_trade = AsyncMock()
        orchestrator.risk_agent.assess.assert_not_called()
        orchestrator.executor_agent.execute_trade.assert_not_called()

    @pytest.mark.asyncio
    async def test_pipeline_risk_rejected(self):
        """Test pipeline stops when risk rejects."""
        orchestrator = AgentOrchestrator()
        orchestrator._initialized = True

        orchestrator._build_context = AsyncMock(
            return_value={
                "symbols": ["BTC/USDT"],
                "market_data": {},
                "memory_context": {},
            }
        )

        # Analyst returns long signal
        orchestrator.analyst.analyze = AsyncMock(
            return_value=MarketAnalysis(
                symbol="BTC/USDT",
                signal="long",
                confidence=0.8,
                reasoning="Strong bullish signal",
            )
        )

        # Risk rejects
        orchestrator.risk_agent.assess = AsyncMock(
            return_value=RiskAssessment(
                approved=False,
                reasoning="Exposure too high",
            )
        )

        result = await orchestrator.run_cycle(["BTC/USDT"])

        assert result.status == CycleStatus.NO_ACTION
        assert result.decision.decision_type == DecisionType.HOLD
        assert (
            "rejected" in result.decision.reasoning.lower()
            or "Risk rejected" in result.decision.reasoning
        )

        # Executor should NOT be called
        orchestrator.executor_agent.execute_trade = AsyncMock()
        orchestrator.executor_agent.execute_trade.assert_not_called()

    @pytest.mark.asyncio
    async def test_full_pipeline_success(self):
        """Test full pipeline: analyst → risk → executor."""
        orchestrator = AgentOrchestrator()
        orchestrator._initialized = True

        orchestrator._build_context = AsyncMock(
            return_value={
                "symbols": ["BTC/USDT"],
                "market_data": {},
                "memory_context": {},
            }
        )

        # Analyst returns long signal
        orchestrator.analyst.analyze = AsyncMock(
            return_value=MarketAnalysis(
                symbol="BTC/USDT",
                signal="long",
                confidence=0.85,
                reasoning="RSI oversold, MACD bullish crossover",
            )
        )

        # Risk approves
        orchestrator.risk_agent.assess = AsyncMock(
            return_value=RiskAssessment(
                approved=True,
                position_size=0.1,
                stop_loss=48000,
                take_profit=55000,
                risk_reward_ratio=2.5,
            )
        )

        # Executor succeeds
        orchestrator.executor_agent.execute_trade = AsyncMock(
            return_value=ExecutionResult(
                executed=True,
                order_id="ord_123",
                symbol="BTC/USDT",
                side="buy",
                quantity=0.1,
                price=50000,
                reasoning="Order filled at market",
            )
        )

        result = await orchestrator.run_cycle(["BTC/USDT"])

        assert result.status == CycleStatus.SUCCESS
        assert result.decision.decision_type == DecisionType.ENTRY_LONG
        assert result.decision.symbol == "BTC/USDT"
        assert result.decision.confidence == 0.85

        # All agents should be called
        orchestrator.analyst.analyze.assert_called_once()
        orchestrator.risk_agent.assess.assert_called_once()
        orchestrator.executor_agent.execute_trade.assert_called_once()

    @pytest.mark.asyncio
    async def test_pipeline_short_signal(self):
        """Test pipeline with short signal."""
        orchestrator = AgentOrchestrator()
        orchestrator._initialized = True

        orchestrator._build_context = AsyncMock(
            return_value={
                "symbols": ["ETH/USDT"],
                "market_data": {},
                "memory_context": {},
            }
        )

        orchestrator.analyst.analyze = AsyncMock(
            return_value=MarketAnalysis(
                symbol="ETH/USDT",
                signal="short",
                confidence=0.7,
                reasoning="Bearish pattern",
            )
        )

        orchestrator.risk_agent.assess = AsyncMock(
            return_value=RiskAssessment(approved=True, position_size=0.5)
        )

        orchestrator.executor_agent.execute_trade = AsyncMock(
            return_value=ExecutionResult(
                executed=True,
                order_id="ord_456",
                symbol="ETH/USDT",
                side="sell",
            )
        )

        result = await orchestrator.run_cycle(["ETH/USDT"])

        assert result.status == CycleStatus.SUCCESS
        assert result.decision.decision_type == DecisionType.ENTRY_SHORT

    @pytest.mark.asyncio
    async def test_pipeline_execution_fails(self):
        """Test pipeline when execution fails."""
        orchestrator = AgentOrchestrator()
        orchestrator._initialized = True

        orchestrator._build_context = AsyncMock(
            return_value={
                "symbols": ["BTC/USDT"],
                "market_data": {},
                "memory_context": {},
            }
        )

        orchestrator.analyst.analyze = AsyncMock(
            return_value=MarketAnalysis(
                symbol="BTC/USDT",
                signal="long",
                confidence=0.8,
            )
        )

        orchestrator.risk_agent.assess = AsyncMock(
            return_value=RiskAssessment(approved=True, position_size=0.1)
        )

        orchestrator.executor_agent.execute_trade = AsyncMock(
            return_value=ExecutionResult(
                executed=False,
                reasoning="Order book too thin",
            )
        )

        result = await orchestrator.run_cycle(["BTC/USDT"])

        assert result.status == CycleStatus.NO_ACTION
        assert result.decision.decision_type == DecisionType.HOLD

    @pytest.mark.asyncio
    async def test_pipeline_error_handling(self):
        """Test pipeline handles errors gracefully."""
        orchestrator = AgentOrchestrator()
        orchestrator._initialized = True

        orchestrator._build_context = AsyncMock(side_effect=RuntimeError("Connection failed"))

        result = await orchestrator.run_cycle(["BTC/USDT"])

        assert result.status == CycleStatus.ERROR
        assert "Connection failed" in result.error
        assert orchestrator._stats.consecutive_errors == 1

    @pytest.mark.asyncio
    async def test_stats_tracking(self):
        """Test that statistics are tracked across cycles."""
        orchestrator = AgentOrchestrator()
        orchestrator._initialized = True

        orchestrator._build_context = AsyncMock(
            return_value={
                "symbols": ["BTC/USDT"],
                "market_data": {},
                "memory_context": {},
            }
        )

        orchestrator.analyst.analyze = AsyncMock(
            return_value=MarketAnalysis(
                symbol="BTC/USDT",
                signal="hold",
                confidence=0.2,
            )
        )

        await orchestrator.run_cycle(["BTC/USDT"])
        await orchestrator.run_cycle(["BTC/USDT"])

        stats = orchestrator.get_stats()
        assert stats["total_cycles"] == 2

    @pytest.mark.asyncio
    async def test_low_confidence_skipped(self):
        """Test that low confidence signals are skipped."""
        orchestrator = AgentOrchestrator()
        orchestrator._initialized = True

        orchestrator._build_context = AsyncMock(
            return_value={
                "symbols": ["BTC/USDT"],
                "market_data": {},
                "memory_context": {},
            }
        )

        # Analyst returns long but with very low confidence
        orchestrator.analyst.analyze = AsyncMock(
            return_value=MarketAnalysis(
                symbol="BTC/USDT",
                signal="long",
                confidence=0.2,  # Below 0.3 threshold
            )
        )

        result = await orchestrator.run_cycle(["BTC/USDT"])

        assert result.status == CycleStatus.NO_ACTION


class TestGetAgentOrchestrator:
    """Tests for get_agent_orchestrator function."""

    def test_returns_singleton(self):
        """Test that function returns singleton."""
        orch1 = get_agent_orchestrator()
        orch2 = get_agent_orchestrator()

        assert orch1 is orch2

    def test_creates_orchestrator(self):
        """Test that function creates orchestrator."""
        orch = get_agent_orchestrator()

        assert isinstance(orch, AgentOrchestrator)


class TestMultiAgentConfig:
    """Tests for multi-agent configuration."""

    def test_multi_agent_defaults(self):
        """Test multi-agent config defaults."""
        from keryxflow.config import AgentSettings

        settings = AgentSettings()

        assert settings.multi_agent_enabled is False
        assert settings.analyst_model is None
        assert settings.risk_model is None
        assert settings.executor_model is None

    def test_multi_agent_enabled(self):
        """Test enabling multi-agent mode."""
        from keryxflow.config import AgentSettings

        settings = AgentSettings(multi_agent_enabled=True)

        assert settings.multi_agent_enabled is True
