"""Strategy description parser using Anthropic tool use."""
from typing import Any

from keryxflow.config import get_settings
from keryxflow.core.logging import get_logger

logger = get_logger(__name__)

STRATEGY_TOOL = {
    "name": "extract_strategy_parameters",
    "description": "Extract structured trading parameters from a strategy description.",
    "input_schema": {
        "type": "object",
        "properties": {
            "entry_conditions": {"type": "array", "items": {"type": "string"}, "description": "Entry conditions."},
            "exit_conditions": {"type": "array", "items": {"type": "string"}, "description": "Exit conditions."},
            "stop_loss_pct": {"type": "number", "description": "Stop loss percentage (e.g. 2.0 for 2%)."},
            "take_profit_pct": {"type": "number", "description": "Take profit percentage (e.g. 5.0 for 5%)."},
            "timeframe": {"type": "string", "description": "Candle timeframe (e.g. '1h', '4h', '1d')."},
            "indicators": {"type": "array", "items": {"type": "string"}, "description": "Technical indicators."},
        },
        "required": ["entry_conditions", "exit_conditions", "stop_loss_pct", "take_profit_pct", "timeframe", "indicators"],
    },
}

SYSTEM_PROMPT = (
    "You are a trading strategy parser. Extract structured parameters from the "
    "user's strategy description. Use the extract_strategy_parameters tool to "
    "return the result. Infer reasonable defaults for any values not explicitly stated."
)


class StrategyGenerator:
    """Parses plain English strategy descriptions into structured parameters."""

    def __init__(self) -> None:
        self._client: Any = None

    async def parse_strategy(self, description: str) -> dict[str, Any]:
        """Parse a strategy description into structured parameters."""
        if self._client is None:
            try:
                import anthropic
                api_key = get_settings().anthropic_api_key.get_secret_value()
                if not api_key:
                    return {"error": "anthropic_api_key_not_configured"}
                self._client = anthropic.AsyncAnthropic(api_key=api_key)
            except (ImportError, Exception) as e:
                logger.warning("strategy_generator_client_init_failed", error=str(e))
                return {"error": str(e)}
        try:
            response = await self._client.messages.create(
                model=get_settings().agent.model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=[STRATEGY_TOOL],
                tool_choice={"type": "tool", "name": "extract_strategy_parameters"},
                messages=[{"role": "user", "content": description}],
            )
            for block in response.content:
                if block.type == "tool_use":
                    return block.input
            return {"error": "no_tool_use_in_response"}
        except Exception as e:
            logger.error("strategy_parse_failed", error=str(e))
            return {"error": str(e)}


_strategy_generator: StrategyGenerator | None = None


def get_strategy_generator() -> StrategyGenerator:
    """Get or create the global StrategyGenerator instance."""
    global _strategy_generator
    if _strategy_generator is None:
        _strategy_generator = StrategyGenerator()
    return _strategy_generator
