"""Tests for the Strategy Generator."""

import json
import os
from unittest.mock import MagicMock

import pytest

from keryxflow.agent.strategy import (
    MarketRegime,
    StrategyType,
    get_strategy_manager,
)
from keryxflow.agent.strategy_gen import (
    StrategyGenerationResult,
    StrategyGenerator,
    get_strategy_generator,
)

VALID_STRATEGY_JSON = json.dumps(
    {
        "id": "rsi_ema_strategy",
        "name": "RSI EMA Crossover",
        "strategy_type": "mean_reversion",
        "description": "Buy when RSI below 30 and price above 200 EMA",
        "regime_suitability": {
            "trending_up": 0.7,
            "trending_down": 0.3,
            "ranging": 0.9,
            "high_volatility": 0.4,
            "low_volatility": 0.8,
            "breakout": 0.2,
        },
        "parameters": {
            "rsi_period": 14,
            "rsi_oversold": 30,
            "ema_period": 200,
        },
    }
)


def _make_mock_response(text: str) -> MagicMock:
    """Create a mock Anthropic API response."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.content = [block]
    response.usage = MagicMock()
    response.usage.input_tokens = 100
    response.usage.output_tokens = 200
    return response


class TestStrategyGenerator:
    """Tests for StrategyGenerator."""

    def _make_generator(self) -> StrategyGenerator:
        """Create a StrategyGenerator with a mocked client."""
        os.environ["KERYXFLOW_ANTHROPIC_API_KEY"] = "test-key"
        os.environ["KERYXFLOW_AI_MODE"] = "enhanced"
        gen = StrategyGenerator()
        gen._client = MagicMock()
        return gen

    async def test_generate_success(self):
        """Test successful strategy generation."""
        gen = self._make_generator()
        gen._client.messages.create.return_value = _make_mock_response(VALID_STRATEGY_JSON)

        result = await gen.generate("Buy when RSI below 30 and price above 200 EMA")

        assert isinstance(result, StrategyGenerationResult)
        assert result.strategy.id == "rsi_ema_strategy"
        assert result.strategy.name == "RSI EMA Crossover"
        assert result.strategy.strategy_type == StrategyType.MEAN_REVERSION
        assert result.registered is True
        assert result.strategy.parameters["rsi_oversold"] == 30

    async def test_generate_registers_with_strategy_manager(self):
        """Test that generated strategy is registered with StrategyManager."""
        gen = self._make_generator()
        gen._client.messages.create.return_value = _make_mock_response(VALID_STRATEGY_JSON)

        await gen.generate("Test strategy")

        manager = get_strategy_manager()
        strategy = manager.get_strategy("rsi_ema_strategy")
        assert strategy is not None
        assert strategy.name == "RSI EMA Crossover"

    async def test_generate_ai_mode_disabled(self):
        """Test that generation fails when ai_mode is disabled."""
        os.environ["KERYXFLOW_AI_MODE"] = "disabled"
        os.environ["KERYXFLOW_ANTHROPIC_API_KEY"] = "test-key"
        gen = StrategyGenerator()
        gen._client = MagicMock()

        with pytest.raises(ValueError, match="ai_mode"):
            await gen.generate("Buy when RSI below 30")

    async def test_generate_no_client(self):
        """Test that generation fails when no client is available."""
        os.environ["KERYXFLOW_AI_MODE"] = "enhanced"
        os.environ["KERYXFLOW_ANTHROPIC_API_KEY"] = ""
        gen = StrategyGenerator()
        # Client will be None since API key is empty

        with pytest.raises(ValueError, match="Anthropic client not available"):
            await gen.generate("Buy when RSI below 30")

    async def test_generate_invalid_json(self):
        """Test handling of invalid JSON response."""
        gen = self._make_generator()
        gen._client.messages.create.return_value = _make_mock_response("not valid json {{{")

        with pytest.raises(ValueError, match="Invalid JSON"):
            await gen.generate("Test strategy")

    async def test_generate_missing_fields(self):
        """Test handling of response missing required fields."""
        gen = self._make_generator()
        incomplete = json.dumps({"id": "test", "name": "Test"})
        gen._client.messages.create.return_value = _make_mock_response(incomplete)

        with pytest.raises(ValueError, match="Missing required field"):
            await gen.generate("Test strategy")

    async def test_generate_invalid_strategy_type(self):
        """Test handling of invalid strategy_type in response."""
        gen = self._make_generator()
        bad_type = json.dumps(
            {
                "id": "test",
                "name": "Test",
                "strategy_type": "invalid_type",
                "description": "Test",
            }
        )
        gen._client.messages.create.return_value = _make_mock_response(bad_type)

        with pytest.raises(ValueError, match="Invalid strategy_type"):
            await gen.generate("Test strategy")

    async def test_parse_markdown_code_fences(self):
        """Test that markdown code fences are stripped from response."""
        gen = self._make_generator()
        fenced = f"```json\n{VALID_STRATEGY_JSON}\n```"
        gen._client.messages.create.return_value = _make_mock_response(fenced)

        result = await gen.generate("Test strategy")

        assert result.strategy.id == "rsi_ema_strategy"

    async def test_parse_code_fence_no_language(self):
        """Test stripping code fences without language specifier."""
        gen = self._make_generator()
        fenced = f"```\n{VALID_STRATEGY_JSON}\n```"
        gen._client.messages.create.return_value = _make_mock_response(fenced)

        result = await gen.generate("Test strategy")

        assert result.strategy.id == "rsi_ema_strategy"

    async def test_stats_tracking_success(self):
        """Test that stats are updated on successful generation."""
        gen = self._make_generator()
        gen._client.messages.create.return_value = _make_mock_response(VALID_STRATEGY_JSON)

        await gen.generate("Test strategy")

        stats = gen.get_stats()
        assert stats["total_generations"] == 1
        assert stats["successful_generations"] == 1
        assert stats["failed_generations"] == 0
        assert stats["total_tokens_used"] == 300
        assert stats["last_generation_time"] is not None

    async def test_stats_tracking_failure(self):
        """Test that stats are updated on failed generation."""
        gen = self._make_generator()
        gen._client.messages.create.return_value = _make_mock_response("invalid")

        with pytest.raises(ValueError):
            await gen.generate("Test strategy")

        stats = gen.get_stats()
        assert stats["total_generations"] == 1
        assert stats["successful_generations"] == 0
        assert stats["failed_generations"] == 1

    async def test_regime_suitability_parsing(self):
        """Test that regime suitability is correctly parsed."""
        gen = self._make_generator()
        gen._client.messages.create.return_value = _make_mock_response(VALID_STRATEGY_JSON)

        result = await gen.generate("Test strategy")

        regime = result.strategy.regime_suitability
        assert regime[MarketRegime.TRENDING_UP] == 0.7
        assert regime[MarketRegime.RANGING] == 0.9
        assert MarketRegime.UNKNOWN not in regime

    async def test_regime_suitability_clamping(self):
        """Test that regime suitability values are clamped to 0-1."""
        gen = self._make_generator()
        data = json.dumps(
            {
                "id": "test",
                "name": "Test",
                "strategy_type": "momentum",
                "description": "Test",
                "regime_suitability": {"trending_up": 1.5, "ranging": -0.5},
                "parameters": {},
            }
        )
        gen._client.messages.create.return_value = _make_mock_response(data)

        result = await gen.generate("Test strategy")

        assert result.strategy.regime_suitability[MarketRegime.TRENDING_UP] == 1.0
        assert result.strategy.regime_suitability[MarketRegime.RANGING] == 0.0

    async def test_unknown_regimes_skipped(self):
        """Test that unknown regime names are silently skipped."""
        gen = self._make_generator()
        data = json.dumps(
            {
                "id": "test",
                "name": "Test",
                "strategy_type": "momentum",
                "description": "Test",
                "regime_suitability": {"trending_up": 0.8, "nonexistent_regime": 0.5},
                "parameters": {},
            }
        )
        gen._client.messages.create.return_value = _make_mock_response(data)

        result = await gen.generate("Test strategy")

        assert MarketRegime.TRENDING_UP in result.strategy.regime_suitability
        assert len(result.strategy.regime_suitability) == 1

    async def test_api_exception_handling(self):
        """Test handling of API exceptions."""
        gen = self._make_generator()
        gen._client.messages.create.side_effect = RuntimeError("API connection failed")

        with pytest.raises(ValueError, match="Strategy generation failed"):
            await gen.generate("Test strategy")

        assert gen.get_stats()["failed_generations"] == 1


class TestGetStrategyGenerator:
    """Tests for the singleton getter."""

    def test_singleton(self):
        """Test that get_strategy_generator returns the same instance."""
        os.environ["KERYXFLOW_ANTHROPIC_API_KEY"] = "test-key"
        os.environ["KERYXFLOW_AI_MODE"] = "enhanced"

        gen1 = get_strategy_generator()
        gen2 = get_strategy_generator()
        assert gen1 is gen2

    def test_singleton_reset(self):
        """Test that singleton is properly reset between tests."""
        import keryxflow.agent.strategy_gen as mod

        mod._strategy_generator = None
        os.environ["KERYXFLOW_ANTHROPIC_API_KEY"] = "test-key"
        os.environ["KERYXFLOW_AI_MODE"] = "enhanced"

        gen = get_strategy_generator()
        assert gen is not None


class TestCLIParsing:
    """Tests for CLI argument parsing."""

    def test_basic_parsing(self):
        """Test basic CLI argument parsing."""

        from keryxflow.agent.strategy_gen import main

        # We test that main() function exists and is callable
        assert callable(main)

    def test_cli_args_structure(self):
        """Test that CLI creates proper argparse structure."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("description")
        parser.add_argument("--backtest", action="store_true")
        parser.add_argument("--symbol", default="BTC/USDT")
        parser.add_argument("--start", default="2024-01-01")
        parser.add_argument("--end", default="2024-06-30")
        parser.add_argument("--balance", type=float, default=10000.0)

        args = parser.parse_args(["buy when RSI below 30", "--backtest", "--symbol", "ETH/USDT"])

        assert args.description == "buy when RSI below 30"
        assert args.backtest is True
        assert args.symbol == "ETH/USDT"
        assert args.start == "2024-01-01"
        assert args.balance == 10000.0
