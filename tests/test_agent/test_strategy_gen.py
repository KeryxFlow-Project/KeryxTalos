"""Tests for the strategy description parser."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from keryxflow.agent.strategy_gen import StrategyGenerator, get_strategy_generator


class TestStrategyGenerator:
    """Tests for StrategyGenerator."""

    @pytest.mark.asyncio
    async def test_parse_strategy_returns_expected_structure(self):
        """Test that parse_strategy returns structured params from mocked Claude response."""
        expected = {
            "entry_conditions": ["RSI below 30"],
            "exit_conditions": ["RSI above 70"],
            "stop_loss_pct": 2.0,
            "take_profit_pct": 5.0,
            "timeframe": "1h",
            "indicators": ["RSI"],
        }

        tool_use_block = MagicMock()
        tool_use_block.type = "tool_use"
        tool_use_block.input = expected

        mock_response = MagicMock()
        mock_response.content = [tool_use_block]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        generator = StrategyGenerator()
        generator._client = mock_client

        result = await generator.parse_strategy(
            "Buy when RSI below 30, sell when RSI above 70"
        )

        assert result == expected
        assert isinstance(result["entry_conditions"], list)
        assert isinstance(result["exit_conditions"], list)
        assert isinstance(result["stop_loss_pct"], float)
        assert isinstance(result["take_profit_pct"], float)
        assert isinstance(result["timeframe"], str)
        assert isinstance(result["indicators"], list)

        mock_client.messages.create.assert_called_once()


def test_get_strategy_generator_singleton():
    """Test singleton returns the same instance."""
    gen1 = get_strategy_generator()
    gen2 = get_strategy_generator()
    assert gen1 is gen2
