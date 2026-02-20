"""Tests for ai_mode configuration and engine branching logic."""

import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from keryxflow.config import SystemSettings


class TestAiModeConfig:
    """Tests for ai_mode field on SystemSettings."""

    def test_default_ai_mode_is_disabled(self):
        settings = SystemSettings()
        assert settings.ai_mode == "disabled"

    def test_ai_mode_accepts_disabled(self):
        settings = SystemSettings(ai_mode="disabled")
        assert settings.ai_mode == "disabled"

    def test_ai_mode_accepts_enhanced(self):
        settings = SystemSettings(ai_mode="enhanced")
        assert settings.ai_mode == "enhanced"

    def test_ai_mode_accepts_autonomous(self):
        settings = SystemSettings(ai_mode="autonomous")
        assert settings.ai_mode == "autonomous"

    def test_ai_mode_rejects_invalid_value(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SystemSettings(ai_mode="turbo")

    def test_ai_mode_from_env_var(self):
        os.environ["KERYXFLOW_AI_MODE"] = "enhanced"
        try:
            settings = SystemSettings()
            assert settings.ai_mode == "enhanced"
        finally:
            del os.environ["KERYXFLOW_AI_MODE"]


class TestEngineAiMode:
    """Tests for TradingEngine ai_mode branching."""

    def _make_engine(self, ai_mode: str = "disabled", agent_enabled: bool = False):
        """Create a TradingEngine with mocked dependencies."""
        from keryxflow.core.engine import TradingEngine

        os.environ["KERYXFLOW_AI_MODE"] = ai_mode
        if agent_enabled:
            os.environ["KERYXFLOW_AGENT_ENABLED"] = "true"
        else:
            os.environ.pop("KERYXFLOW_AGENT_ENABLED", None)

        # Reset settings singleton so new env vars take effect
        import keryxflow.config as config_module

        config_module._settings = None

        exchange = MagicMock()
        paper = MagicMock()
        signal_gen = MagicMock()
        risk = MagicMock()
        risk.is_circuit_breaker_active = False
        memory = MagicMock()

        engine = TradingEngine(
            exchange_client=exchange,
            paper_engine=paper,
            signal_generator=signal_gen,
            risk_manager=risk,
            memory_manager=memory,
        )
        return engine

    def test_disabled_mode_sets_ai_mode(self):
        engine = self._make_engine("disabled")
        assert engine._ai_mode == "disabled"
        assert engine._agent_mode is False

    def test_enhanced_mode_sets_ai_mode(self):
        engine = self._make_engine("enhanced")
        assert engine._ai_mode == "enhanced"
        assert engine._agent_mode is False

    def test_autonomous_mode_sets_ai_mode(self):
        engine = self._make_engine("autonomous")
        assert engine._ai_mode == "autonomous"
        assert engine._agent_mode is True

    def test_backward_compat_agent_enabled_promotes_to_autonomous(self):
        """When ai_mode=disabled but agent.enabled=True, promote to autonomous."""
        engine = self._make_engine("disabled", agent_enabled=True)
        assert engine._ai_mode == "autonomous"
        assert engine._agent_mode is True

    def test_explicit_ai_mode_overrides_agent_enabled(self):
        """When ai_mode=enhanced, agent.enabled=True should not promote to autonomous."""
        engine = self._make_engine("enhanced", agent_enabled=True)
        assert engine._ai_mode == "enhanced"
        assert engine._agent_mode is False

    @pytest.mark.asyncio
    async def test_analyze_symbol_disabled_uses_no_llm(self):
        engine = self._make_engine("disabled")
        engine._ohlcv_buffer = MagicMock()
        engine._ohlcv_buffer.get_ohlcv.return_value = MagicMock(__len__=lambda _: 50)
        engine.signals.generate_signal = AsyncMock(
            return_value=MagicMock(
                is_actionable=False,
                signal_type=MagicMock(value="hold"),
                confidence=0.5,
                to_dict=lambda: {},
            )
        )
        engine.event_bus = MagicMock()
        engine.event_bus.publish = AsyncMock()

        await engine._analyze_symbol("BTC/USDT", 42000.0)

        engine.signals.generate_signal.assert_awaited_once()
        call_kwargs = engine.signals.generate_signal.call_args.kwargs
        assert call_kwargs["include_llm"] is False

    @pytest.mark.asyncio
    async def test_analyze_symbol_enhanced_uses_llm(self):
        engine = self._make_engine("enhanced")
        engine._ohlcv_buffer = MagicMock()
        engine._ohlcv_buffer.get_ohlcv.return_value = MagicMock(__len__=lambda _: 50)
        engine.signals.generate_signal = AsyncMock(
            return_value=MagicMock(
                is_actionable=False,
                signal_type=MagicMock(value="hold"),
                confidence=0.5,
                to_dict=lambda: {},
            )
        )
        engine.event_bus = MagicMock()
        engine.event_bus.publish = AsyncMock()

        await engine._analyze_symbol("BTC/USDT", 42000.0)

        engine.signals.generate_signal.assert_awaited_once()
        call_kwargs = engine.signals.generate_signal.call_args.kwargs
        assert call_kwargs["include_llm"] is True

    @pytest.mark.asyncio
    async def test_analyze_symbol_autonomous_runs_agent_cycle(self):
        engine = self._make_engine("autonomous")
        engine._cognitive_agent = MagicMock()
        engine._cognitive_agent._initialized = True
        engine._cognitive_agent.run_cycle = AsyncMock(
            return_value=MagicMock(
                status=MagicMock(value="success"),
                decision=None,
                duration_ms=100,
            )
        )
        engine._cognitive_agent._stats = MagicMock(consecutive_errors=0)
        engine._cognitive_agent.get_stats.return_value = {}

        await engine._analyze_symbol("BTC/USDT", 42000.0)

        engine._cognitive_agent.run_cycle.assert_awaited_once_with(["BTC/USDT"])

    def test_get_status_includes_ai_mode(self):
        engine = self._make_engine("enhanced")
        engine._ohlcv_buffer = MagicMock()
        engine._ohlcv_buffer._candles = {"BTC/USDT": []}
        status = engine.get_status()
        assert status["ai_mode"] == "enhanced"


class TestBrainAiMode:
    """Tests for OracleBrain respecting ai_mode."""

    @pytest.mark.asyncio
    async def test_brain_returns_fallback_when_disabled(self):
        os.environ["KERYXFLOW_AI_MODE"] = "disabled"
        import keryxflow.config as config_module

        config_module._settings = None

        from keryxflow.oracle.brain import OracleBrain

        brain = OracleBrain()
        result = await brain.analyze("BTC/USDT")

        assert result.symbol == "BTC/USDT"
        # Should be a fallback context (no LLM call)
        assert "LLM unavailable" in result.reasoning or "LLM" in result.risks[0]
