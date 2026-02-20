"""Strategy selection and adaptation for the cognitive agent.

This module provides capabilities for:
- Defining trading strategies
- Selecting strategies based on market conditions
- Adapting strategy parameters based on performance
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from keryxflow.core.logging import get_logger
from keryxflow.memory.semantic import SemanticMemory, get_semantic_memory

logger = get_logger(__name__)


class MarketRegime(str, Enum):
    """Classification of market conditions."""

    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    BREAKOUT = "breakout"
    UNKNOWN = "unknown"


class StrategyType(str, Enum):
    """Type of trading strategy."""

    TREND_FOLLOWING = "trend_following"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    SCALPING = "scalping"
    SWING = "swing"
    MOMENTUM = "momentum"
    GRID = "grid"


@dataclass
class StrategyConfig:
    """Configuration for a trading strategy."""

    id: str
    name: str
    strategy_type: StrategyType
    description: str

    # Market regime suitability (0-1 score for each regime)
    regime_suitability: dict[MarketRegime, float] = field(default_factory=dict)

    # Parameters
    parameters: dict[str, Any] = field(default_factory=dict)

    # Performance metrics
    total_trades: int = 0
    winning_trades: int = 0
    total_pnl: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0

    # State
    is_active: bool = True
    last_used: datetime | None = None

    def win_rate(self) -> float:
        """Calculate win rate."""
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades

    def avg_pnl(self) -> float:
        """Calculate average P&L per trade."""
        if self.total_trades == 0:
            return 0.0
        return self.total_pnl / self.total_trades

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "strategy_type": self.strategy_type.value,
            "description": self.description,
            "regime_suitability": {k.value: v for k, v in self.regime_suitability.items()},
            "parameters": self.parameters,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "win_rate": self.win_rate(),
            "total_pnl": self.total_pnl,
            "avg_pnl": self.avg_pnl(),
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "is_active": self.is_active,
            "last_used": self.last_used.isoformat() if self.last_used else None,
        }


@dataclass
class StrategySelection:
    """Result of strategy selection."""

    strategy: StrategyConfig
    confidence: float
    reasoning: str
    detected_regime: MarketRegime
    alternative_strategies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "strategy_id": self.strategy.id,
            "strategy_name": self.strategy.name,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "detected_regime": self.detected_regime.value,
            "alternative_strategies": self.alternative_strategies,
        }


@dataclass
class StrategyManagerStats:
    """Statistics for the strategy manager."""

    total_selections: int = 0
    selections_by_strategy: dict[str, int] = field(default_factory=dict)
    selections_by_regime: dict[str, int] = field(default_factory=dict)
    last_selection_time: datetime | None = None


class StrategyManager:
    """Manager for trading strategy selection and adaptation.

    The StrategyManager:
    - Maintains a catalog of available strategies
    - Detects market regimes
    - Selects optimal strategies for current conditions
    - Tracks strategy performance
    - Adapts strategy parameters based on results

    Example:
        manager = StrategyManager()

        # Register strategies
        manager.register_strategy(trend_strategy)
        manager.register_strategy(reversion_strategy)

        # Select best strategy for current conditions
        selection = await manager.select_strategy(
            symbol="BTC/USDT",
            market_data=ohlcv_data,
        )

        # Update performance after trade
        await manager.record_trade_result(
            strategy_id=selection.strategy.id,
            pnl_percentage=2.5,
            won=True,
        )
    """

    # Default strategy configurations
    DEFAULT_STRATEGIES = [
        StrategyConfig(
            id="trend_following_basic",
            name="Basic Trend Following",
            strategy_type=StrategyType.TREND_FOLLOWING,
            description="Follow established trends using EMA crossovers",
            regime_suitability={
                MarketRegime.TRENDING_UP: 0.9,
                MarketRegime.TRENDING_DOWN: 0.9,
                MarketRegime.RANGING: 0.2,
                MarketRegime.HIGH_VOLATILITY: 0.5,
                MarketRegime.LOW_VOLATILITY: 0.6,
                MarketRegime.BREAKOUT: 0.7,
            },
            parameters={
                "fast_ema": 9,
                "slow_ema": 21,
                "confirmation_candles": 2,
            },
        ),
        StrategyConfig(
            id="mean_reversion_rsi",
            name="RSI Mean Reversion",
            strategy_type=StrategyType.MEAN_REVERSION,
            description="Trade reversals at RSI extremes",
            regime_suitability={
                MarketRegime.TRENDING_UP: 0.3,
                MarketRegime.TRENDING_DOWN: 0.3,
                MarketRegime.RANGING: 0.9,
                MarketRegime.HIGH_VOLATILITY: 0.4,
                MarketRegime.LOW_VOLATILITY: 0.8,
                MarketRegime.BREAKOUT: 0.2,
            },
            parameters={
                "rsi_period": 14,
                "oversold_level": 30,
                "overbought_level": 70,
            },
        ),
        StrategyConfig(
            id="breakout_bollinger",
            name="Bollinger Breakout",
            strategy_type=StrategyType.BREAKOUT,
            description="Trade breakouts from Bollinger Bands",
            regime_suitability={
                MarketRegime.TRENDING_UP: 0.6,
                MarketRegime.TRENDING_DOWN: 0.6,
                MarketRegime.RANGING: 0.4,
                MarketRegime.HIGH_VOLATILITY: 0.7,
                MarketRegime.LOW_VOLATILITY: 0.3,
                MarketRegime.BREAKOUT: 0.95,
            },
            parameters={
                "bb_period": 20,
                "bb_std": 2.0,
                "volume_confirmation": True,
            },
        ),
        StrategyConfig(
            id="momentum_macd",
            name="MACD Momentum",
            strategy_type=StrategyType.MOMENTUM,
            description="Trade momentum using MACD signals",
            regime_suitability={
                MarketRegime.TRENDING_UP: 0.8,
                MarketRegime.TRENDING_DOWN: 0.8,
                MarketRegime.RANGING: 0.3,
                MarketRegime.HIGH_VOLATILITY: 0.6,
                MarketRegime.LOW_VOLATILITY: 0.5,
                MarketRegime.BREAKOUT: 0.7,
            },
            parameters={
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
            },
        ),
        StrategyConfig(
            id="grid_default",
            name="Grid Trading Bot",
            strategy_type=StrategyType.GRID,
            description="Place buy/sell orders at grid levels to profit from ranging markets",
            regime_suitability={
                MarketRegime.TRENDING_UP: 0.3,
                MarketRegime.TRENDING_DOWN: 0.2,
                MarketRegime.RANGING: 0.95,
                MarketRegime.HIGH_VOLATILITY: 0.4,
                MarketRegime.LOW_VOLATILITY: 0.85,
                MarketRegime.BREAKOUT: 0.1,
            },
            parameters={
                "grid_count": 10,
                "grid_type": "arithmetic",
                "auto_stop_on_breakout": True,
            },
        ),
    ]

    def __init__(self, semantic_memory: SemanticMemory | None = None):
        """Initialize the strategy manager.

        Args:
            semantic_memory: Semantic memory for storing strategy adaptations.
        """
        self.semantic = semantic_memory or get_semantic_memory()
        self._strategies: dict[str, StrategyConfig] = {}
        self._stats = StrategyManagerStats()
        self._current_strategy: StrategyConfig | None = None
        self._current_regime: MarketRegime = MarketRegime.UNKNOWN

        # Register default strategies
        for strategy in self.DEFAULT_STRATEGIES:
            self._strategies[strategy.id] = strategy

    def register_strategy(self, strategy: StrategyConfig) -> None:
        """Register a new strategy.

        Args:
            strategy: Strategy configuration to register
        """
        self._strategies[strategy.id] = strategy
        logger.info("strategy_registered", strategy_id=strategy.id)

    def get_strategy(self, strategy_id: str) -> StrategyConfig | None:
        """Get a strategy by ID.

        Args:
            strategy_id: Strategy ID

        Returns:
            StrategyConfig or None
        """
        return self._strategies.get(strategy_id)

    def list_strategies(self) -> list[dict[str, Any]]:
        """List all registered strategies.

        Returns:
            List of strategy dictionaries
        """
        return [s.to_dict() for s in self._strategies.values()]

    def detect_market_regime(
        self,
        prices: list[float],
        _volumes: list[float] | None = None,
    ) -> MarketRegime:
        """Detect the current market regime from price data.

        Args:
            prices: List of recent prices (close prices)
            volumes: Optional list of volumes

        Returns:
            Detected MarketRegime
        """
        if len(prices) < 20:
            return MarketRegime.UNKNOWN

        # Calculate basic metrics
        prices_array = prices[-50:] if len(prices) >= 50 else prices

        # Simple moving averages
        sma_short = sum(prices_array[-10:]) / 10
        sma_long = sum(prices_array[-30:]) / min(30, len(prices_array))

        # Price change
        price_change = (prices_array[-1] - prices_array[0]) / prices_array[0]

        # Volatility (simplified)
        price_range = max(prices_array) - min(prices_array)
        volatility = price_range / prices_array[0]

        # Determine regime
        if abs(price_change) > 0.05:  # 5%+ move
            if price_change > 0:
                return MarketRegime.TRENDING_UP
            else:
                return MarketRegime.TRENDING_DOWN

        if volatility > 0.1:  # 10%+ range
            return MarketRegime.HIGH_VOLATILITY

        if volatility < 0.03:  # Less than 3% range
            return MarketRegime.LOW_VOLATILITY

        # Check for ranging
        if abs(sma_short - sma_long) / sma_long < 0.01:  # SMAs converging
            return MarketRegime.RANGING

        # Check for breakout (recent volatility spike)
        recent_vol = (max(prices_array[-5:]) - min(prices_array[-5:])) / prices_array[-5]
        older_vol = (max(prices_array[-20:-5]) - min(prices_array[-20:-5])) / prices_array[-20]
        if older_vol > 0 and recent_vol / older_vol > 2:
            return MarketRegime.BREAKOUT

        return MarketRegime.UNKNOWN

    async def select_strategy(
        self,
        symbol: str,  # noqa: ARG002
        prices: list[float],
        volumes: list[float] | None = None,
        force_regime: MarketRegime | None = None,
    ) -> StrategySelection:
        """Select the best strategy for current conditions.

        Args:
            symbol: Trading symbol
            prices: Recent price data
            volumes: Optional volume data
            force_regime: Force a specific regime (for testing)

        Returns:
            StrategySelection with the chosen strategy
        """
        # Detect market regime
        regime = force_regime or self.detect_market_regime(prices, volumes)
        self._current_regime = regime

        # Score each strategy
        scores: list[tuple[StrategyConfig, float]] = []

        for strategy in self._strategies.values():
            if not strategy.is_active:
                continue

            # Base score from regime suitability
            base_score = strategy.regime_suitability.get(regime, 0.5)

            # Adjust for performance
            performance_adjustment = 0.0
            if strategy.total_trades >= 10:
                # Boost for good win rate
                if strategy.win_rate() > 0.6:
                    performance_adjustment += 0.1
                elif strategy.win_rate() < 0.4:
                    performance_adjustment -= 0.1

                # Boost for positive avg PnL
                if strategy.avg_pnl() > 0:
                    performance_adjustment += 0.05

            final_score = min(1.0, max(0.0, base_score + performance_adjustment))
            scores.append((strategy, final_score))

        # Sort by score
        scores.sort(key=lambda x: x[1], reverse=True)

        if not scores:
            # Fallback to first available strategy
            strategy = list(self._strategies.values())[0]
            confidence = 0.5
        else:
            strategy = scores[0][0]
            confidence = scores[0][1]

        # Build reasoning
        reasoning = (
            f"Selected {strategy.name} for {regime.value} market conditions. "
            f"Strategy has {strategy.win_rate():.0%} win rate over {strategy.total_trades} trades."
        )

        # Get alternative strategies
        alternatives = [s[0].id for s in scores[1:4]] if len(scores) > 1 else []

        # Update state
        self._current_strategy = strategy
        strategy.last_used = datetime.now(UTC)

        # Update stats
        self._stats.total_selections += 1
        self._stats.selections_by_strategy[strategy.id] = (
            self._stats.selections_by_strategy.get(strategy.id, 0) + 1
        )
        self._stats.selections_by_regime[regime.value] = (
            self._stats.selections_by_regime.get(regime.value, 0) + 1
        )
        self._stats.last_selection_time = datetime.now(UTC)

        logger.info(
            "strategy_selected",
            strategy_id=strategy.id,
            regime=regime.value,
            confidence=confidence,
        )

        return StrategySelection(
            strategy=strategy,
            confidence=confidence,
            reasoning=reasoning,
            detected_regime=regime,
            alternative_strategies=alternatives,
        )

    async def record_trade_result(
        self,
        strategy_id: str,
        pnl_percentage: float,
        won: bool,
    ) -> None:
        """Record a trade result for a strategy.

        Args:
            strategy_id: ID of the strategy used
            pnl_percentage: P&L percentage of the trade
            won: Whether the trade was profitable
        """
        strategy = self._strategies.get(strategy_id)
        if strategy is None:
            logger.warning("strategy_not_found_for_result", strategy_id=strategy_id)
            return

        strategy.total_trades += 1
        strategy.total_pnl += pnl_percentage
        if won:
            strategy.winning_trades += 1

        logger.debug(
            "strategy_result_recorded",
            strategy_id=strategy_id,
            pnl=pnl_percentage,
            won=won,
        )

    def adapt_strategy_parameters(
        self,
        strategy_id: str,
        parameter_updates: dict[str, Any],
    ) -> bool:
        """Adapt strategy parameters based on learning.

        Args:
            strategy_id: ID of the strategy
            parameter_updates: New parameter values

        Returns:
            True if updated, False if strategy not found
        """
        strategy = self._strategies.get(strategy_id)
        if strategy is None:
            return False

        strategy.parameters.update(parameter_updates)

        logger.info(
            "strategy_parameters_adapted",
            strategy_id=strategy_id,
            updates=parameter_updates,
        )

        return True

    def get_current_strategy(self) -> StrategyConfig | None:
        """Get the currently selected strategy.

        Returns:
            Current StrategyConfig or None
        """
        return self._current_strategy

    def get_current_regime(self) -> MarketRegime:
        """Get the current detected market regime.

        Returns:
            Current MarketRegime
        """
        return self._current_regime

    def get_stats(self) -> dict[str, Any]:
        """Get strategy manager statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "total_strategies": len(self._strategies),
            "active_strategies": sum(1 for s in self._strategies.values() if s.is_active),
            "total_selections": self._stats.total_selections,
            "selections_by_strategy": self._stats.selections_by_strategy,
            "selections_by_regime": self._stats.selections_by_regime,
            "current_strategy": self._current_strategy.id if self._current_strategy else None,
            "current_regime": self._current_regime.value,
            "last_selection_time": (
                self._stats.last_selection_time.isoformat()
                if self._stats.last_selection_time
                else None
            ),
        }


# Global instance
_strategy_manager: StrategyManager | None = None


def get_strategy_manager() -> StrategyManager:
    """Get the global strategy manager instance."""
    global _strategy_manager
    if _strategy_manager is None:
        _strategy_manager = StrategyManager()
    return _strategy_manager
