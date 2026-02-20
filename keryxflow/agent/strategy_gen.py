"""Natural language strategy generation via LLM.

This module allows users to describe trading strategies in plain English
and have Claude generate a validated StrategyConfig. The generated strategy
is registered with StrategyManager and can optionally be backtested.
"""

import argparse
import asyncio
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from keryxflow.agent.strategy import (
    MarketRegime,
    StrategyConfig,
    StrategyType,
    get_strategy_manager,
)
from keryxflow.config import get_settings
from keryxflow.core.logging import get_logger

logger = get_logger(__name__)

STRATEGY_GEN_SYSTEM_PROMPT = """\
You are a trading strategy designer. Given a natural language description of a trading strategy, \
generate a JSON object representing a StrategyConfig.

The JSON must have exactly these fields:
- "id": a snake_case unique identifier (e.g., "rsi_ema_crossover")
- "name": a human-readable name (e.g., "RSI EMA Crossover")
- "strategy_type": one of: "trend_following", "mean_reversion", "breakout", "scalping", "swing", "momentum"
- "description": a clear description of the strategy
- "regime_suitability": an object mapping market regimes to suitability scores (0.0-1.0). \
Regimes: "trending_up", "trending_down", "ranging", "high_volatility", "low_volatility", "breakout"
- "parameters": an object with indicator thresholds and periods that define entry/exit conditions. \
Use standard keys like "rsi_period", "rsi_oversold", "rsi_overbought", "ema_fast", "ema_slow", \
"bb_period", "bb_std", "macd_fast", "macd_slow", "macd_signal", etc.

Respond with ONLY the JSON object. No explanation, no markdown fences."""

STRATEGY_GEN_USER_PROMPT = "Create a trading strategy based on this description: {description}"


@dataclass
class StrategyGenerationResult:
    """Result of strategy generation."""

    strategy: StrategyConfig
    registered: bool
    backtest_result: dict[str, Any] | None = None


@dataclass
class StrategyGenStats:
    """Statistics for the strategy generator."""

    total_generations: int = 0
    successful_generations: int = 0
    failed_generations: int = 0
    total_tokens_used: int = 0
    last_generation_time: datetime | None = None


class StrategyGenerator:
    """Generates trading strategies from natural language descriptions using Claude.

    Example:
        generator = StrategyGenerator()
        result = await generator.generate("Buy when RSI below 30 and price above 200 EMA")
        print(result.strategy.to_dict())
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: Any = None
        self._stats = StrategyGenStats()
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize the Anthropic client."""
        try:
            import anthropic

            api_key = self.settings.anthropic_api_key.get_secret_value()
            if api_key:
                self._client = anthropic.Anthropic(api_key=api_key)
                logger.info("strategy_generator_initialized")
            else:
                logger.warning("anthropic_api_key_not_configured_for_strategy_gen")
        except ImportError:
            logger.error("anthropic_package_not_installed")

    async def generate(self, description: str) -> StrategyGenerationResult:
        """Generate a strategy from a natural language description.

        Args:
            description: Natural language description of the strategy.

        Returns:
            StrategyGenerationResult with the generated strategy.

        Raises:
            ValueError: If ai_mode is disabled or generation fails.
        """
        if self.settings.system.ai_mode == "disabled":
            raise ValueError(
                "Strategy generation requires ai_mode to be 'enhanced' or 'autonomous'"
            )

        if self._client is None:
            raise ValueError("Anthropic client not available. Check API key configuration.")

        self._stats.total_generations += 1

        try:
            response = self._client.messages.create(
                model=self.settings.agent.model,
                max_tokens=1024,
                temperature=0.2,
                system=STRATEGY_GEN_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": STRATEGY_GEN_USER_PROMPT.format(description=description),
                    }
                ],
            )

            self._stats.total_tokens_used += (
                response.usage.input_tokens + response.usage.output_tokens
            )

            text_blocks = [block.text for block in response.content if block.type == "text"]
            raw_text = " ".join(text_blocks).strip()

            strategy = self._parse_response(raw_text)

            # Register with StrategyManager
            manager = get_strategy_manager()
            manager.register_strategy(strategy)

            self._stats.successful_generations += 1
            self._stats.last_generation_time = datetime.now(UTC)

            logger.info(
                "strategy_generated",
                strategy_id=strategy.id,
                strategy_type=strategy.strategy_type.value,
            )

            return StrategyGenerationResult(strategy=strategy, registered=True)

        except ValueError:
            self._stats.failed_generations += 1
            raise
        except Exception as e:
            self._stats.failed_generations += 1
            logger.exception("strategy_generation_failed")
            raise ValueError(f"Strategy generation failed: {e}") from e

    def _parse_response(self, raw_text: str) -> StrategyConfig:
        """Parse the LLM response into a StrategyConfig.

        Args:
            raw_text: Raw text from the LLM response.

        Returns:
            StrategyConfig parsed from the response.

        Raises:
            ValueError: If parsing or validation fails.
        """
        # Strip markdown code fences if present
        text = raw_text.strip()
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in LLM response: {e}") from e

        return self._validate_and_build(data)

    def _validate_and_build(self, data: dict[str, Any]) -> StrategyConfig:
        """Validate parsed JSON and build a StrategyConfig.

        Args:
            data: Parsed JSON dict.

        Returns:
            Validated StrategyConfig.

        Raises:
            ValueError: If required fields are missing or invalid.
        """
        required_fields = ["id", "name", "strategy_type", "description"]
        for f in required_fields:
            if f not in data:
                raise ValueError(f"Missing required field: {f}")

        # Validate strategy_type
        try:
            strategy_type = StrategyType(data["strategy_type"])
        except ValueError as e:
            valid = [t.value for t in StrategyType]
            raise ValueError(
                f"Invalid strategy_type '{data['strategy_type']}'. Must be one of: {valid}"
            ) from e

        # Parse regime_suitability
        regime_suitability: dict[MarketRegime, float] = {}
        raw_regimes = data.get("regime_suitability", {})
        for regime_str, score in raw_regimes.items():
            try:
                regime = MarketRegime(regime_str)
            except ValueError:
                continue  # skip unknown regimes
            score_val = float(score)
            if not 0.0 <= score_val <= 1.0:
                score_val = max(0.0, min(1.0, score_val))
            regime_suitability[regime] = score_val

        return StrategyConfig(
            id=data["id"],
            name=data["name"],
            strategy_type=strategy_type,
            description=data["description"],
            regime_suitability=regime_suitability,
            parameters=data.get("parameters", {}),
        )

    async def generate_and_backtest(
        self,
        description: str,
        symbol: str = "BTC/USDT",
        start_date: str = "2024-01-01",
        end_date: str = "2024-06-30",
        initial_balance: float = 10000.0,
    ) -> StrategyGenerationResult:
        """Generate a strategy and optionally backtest it.

        Args:
            description: Natural language strategy description.
            symbol: Trading symbol for backtest.
            start_date: Backtest start date (YYYY-MM-DD).
            end_date: Backtest end date (YYYY-MM-DD).
            initial_balance: Initial balance for backtest.

        Returns:
            StrategyGenerationResult with strategy and optional backtest results.
        """
        result = await self.generate(description)

        try:
            from keryxflow.backtester.runner import run_backtest

            backtest_result = await run_backtest(
                symbols=[symbol],
                start=datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=UTC),
                end=datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=UTC),
                initial_balance=initial_balance,
            )
            result.backtest_result = {
                "total_return": backtest_result.total_return,
                "total_trades": backtest_result.total_trades,
                "win_rate": backtest_result.win_rate,
                "max_drawdown": backtest_result.max_drawdown,
                "sharpe_ratio": backtest_result.sharpe_ratio,
            }
        except Exception as e:
            logger.warning("backtest_after_generation_failed", error=str(e))
            result.backtest_result = {"error": str(e)}

        return result

    def get_stats(self) -> dict[str, Any]:
        """Get strategy generator statistics."""
        return {
            "total_generations": self._stats.total_generations,
            "successful_generations": self._stats.successful_generations,
            "failed_generations": self._stats.failed_generations,
            "total_tokens_used": self._stats.total_tokens_used,
            "last_generation_time": (
                self._stats.last_generation_time.isoformat()
                if self._stats.last_generation_time
                else None
            ),
        }


# Global instance
_strategy_generator: StrategyGenerator | None = None


def get_strategy_generator() -> StrategyGenerator:
    """Get the global strategy generator instance."""
    global _strategy_generator
    if _strategy_generator is None:
        _strategy_generator = StrategyGenerator()
    return _strategy_generator


def main() -> None:
    """CLI entry point for natural language strategy generation."""
    parser = argparse.ArgumentParser(
        description="KeryxFlow Strategy Generator - Create strategies from natural language",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate a strategy from description
  %(prog)s "buy when RSI below 30 and price above 200 EMA"

  # Generate and backtest
  %(prog)s "momentum strategy using MACD crossover" --backtest \\
           --symbol BTC/USDT --start 2024-01-01 --end 2024-06-30

  # Generate with custom backtest balance
  %(prog)s "mean reversion on Bollinger Band extremes" --backtest --balance 50000
        """,
    )

    parser.add_argument(
        "description",
        help="Natural language description of the trading strategy",
    )

    parser.add_argument(
        "--backtest",
        action="store_true",
        help="Run a backtest after generating the strategy",
    )

    parser.add_argument(
        "--symbol",
        "-s",
        default="BTC/USDT",
        help="Trading symbol for backtest (default: BTC/USDT)",
    )

    parser.add_argument(
        "--start",
        default="2024-01-01",
        help="Backtest start date (default: 2024-01-01)",
    )

    parser.add_argument(
        "--end",
        default="2024-06-30",
        help="Backtest end date (default: 2024-06-30)",
    )

    parser.add_argument(
        "--balance",
        "-b",
        type=float,
        default=10000.0,
        help="Initial balance for backtest (default: 10000)",
    )

    args = parser.parse_args()

    print("\nKeryxFlow Strategy Generator")
    print(f"Description: {args.description}")
    print("\nGenerating strategy...")

    async def _run() -> None:
        generator = StrategyGenerator()

        if args.backtest:
            result = await generator.generate_and_backtest(
                description=args.description,
                symbol=args.symbol,
                start_date=args.start,
                end_date=args.end,
                initial_balance=args.balance,
            )
        else:
            result = await generator.generate(args.description)

        print("\nGenerated Strategy:")
        print(f"  ID: {result.strategy.id}")
        print(f"  Name: {result.strategy.name}")
        print(f"  Type: {result.strategy.strategy_type.value}")
        print(f"  Description: {result.strategy.description}")
        print(f"  Parameters: {json.dumps(result.strategy.parameters, indent=4)}")
        print(f"  Registered: {result.registered}")

        if result.strategy.regime_suitability:
            print("  Regime Suitability:")
            for regime, score in result.strategy.regime_suitability.items():
                print(f"    {regime.value}: {score:.2f}")

        if result.backtest_result:
            print("\nBacktest Results:")
            for key, value in result.backtest_result.items():
                if isinstance(value, float):
                    print(f"  {key}: {value:.4f}")
                else:
                    print(f"  {key}: {value}")

    try:
        asyncio.run(_run())
    except ValueError as e:
        print(f"\nError: {e}")
    except KeyboardInterrupt:
        print("\nAborted.")


if __name__ == "__main__":
    main()
