"""Optimization engine for running parameter grid searches."""

import time
from dataclasses import dataclass
from typing import Any

import pandas as pd

from keryxflow.backtester.engine import BacktestEngine
from keryxflow.backtester.report import BacktestResult
from keryxflow.config import get_settings
from keryxflow.core.logging import get_logger
from keryxflow.core.models import RiskProfile
from keryxflow.optimizer.grid import ParameterGrid

logger = get_logger(__name__)


@dataclass
class OptimizationResult:
    """Result of a single backtest run with specific parameters.

    Attributes:
        parameters: Dict with 'oracle' and 'risk' parameter values
        metrics: BacktestResult with performance metrics
        run_time: Time taken to run the backtest in seconds
        run_index: Index of this run in the optimization sequence
    """

    parameters: dict[str, dict[str, Any]]
    metrics: BacktestResult
    run_time: float
    run_index: int = 0

    def get_metric(self, name: str) -> float:
        """Get a specific metric value.

        Args:
            name: Metric name (e.g., 'sharpe_ratio', 'total_return', 'win_rate')

        Returns:
            Metric value or 0.0 if not found
        """
        return getattr(self.metrics, name, 0.0)

    def flat_parameters(self) -> dict[str, Any]:
        """Get flattened parameters dict."""
        result = {}
        for category in self.parameters.values():
            result.update(category)
        return result


@dataclass
class OptimizationConfig:
    """Configuration for optimization runs.

    Attributes:
        initial_balance: Starting balance for backtests
        risk_profile: Base risk profile to use
        slippage: Slippage percentage (0.001 = 0.1%)
        commission: Commission percentage (0.001 = 0.1%)
    """

    initial_balance: float = 10000.0
    risk_profile: RiskProfile = RiskProfile.BALANCED
    slippage: float = 0.001
    commission: float = 0.001


class OptimizationEngine:
    """Engine for running parameter optimization via grid search.

    Example:
        engine = OptimizationEngine()
        results = await engine.optimize(
            data={"BTC/USDT": ohlcv_df},
            grid=ParameterGrid.quick_grid(),
            metric="sharpe_ratio",
        )

        best = results[0]
        print(f"Best Sharpe: {best.metrics.sharpe_ratio}")
    """

    def __init__(self, config: OptimizationConfig | None = None):
        """Initialize the optimization engine.

        Args:
            config: Optimization configuration (uses defaults if None)
        """
        self.config = config or OptimizationConfig()
        self._original_settings: dict[str, Any] | None = None

    async def optimize(
        self,
        data: dict[str, pd.DataFrame],
        grid: ParameterGrid,
        metric: str = "sharpe_ratio",
        start: Any | None = None,
        end: Any | None = None,
        progress_callback: Any | None = None,
    ) -> list[OptimizationResult]:
        """Run optimization across all parameter combinations.

        Args:
            data: Dict of {symbol: OHLCV DataFrame}
            grid: Parameter grid to test
            metric: Metric to optimize for (used for sorting results)
            start: Start datetime for backtest (optional)
            end: End datetime for backtest (optional)
            progress_callback: Optional callback(current, total, params) for progress updates

        Returns:
            List of OptimizationResult sorted by metric (best first)
        """
        results: list[OptimizationResult] = []
        total_combinations = len(grid)

        logger.info(
            "optimization_starting",
            combinations=total_combinations,
            metric=metric,
            symbols=list(data.keys()),
        )

        # Store original settings
        self._save_original_settings()

        try:
            for idx, params in enumerate(grid.combinations()):
                run_start = time.time()

                # Report progress
                if progress_callback:
                    progress_callback(idx + 1, total_combinations, params)
                else:
                    flat = {**params.get("oracle", {}), **params.get("risk", {})}
                    logger.debug(
                        "optimization_run",
                        run=idx + 1,
                        total=total_combinations,
                        params=flat,
                    )

                # Apply parameters to settings
                self._apply_parameters(params)

                # Run backtest
                try:
                    result = await self._run_backtest(data, start, end)
                    run_time = time.time() - run_start

                    opt_result = OptimizationResult(
                        parameters=params,
                        metrics=result,
                        run_time=run_time,
                        run_index=idx,
                    )
                    results.append(opt_result)

                    logger.debug(
                        "optimization_run_complete",
                        run=idx + 1,
                        sharpe=result.sharpe_ratio,
                        return_pct=result.total_return * 100,
                        trades=result.total_trades,
                    )

                except Exception as e:
                    logger.warning(
                        "optimization_run_failed",
                        run=idx + 1,
                        error=str(e),
                    )
                    continue

        finally:
            # Restore original settings
            self._restore_original_settings()

        # Sort by metric (descending - higher is better)
        results = self._sort_results(results, metric)

        logger.info(
            "optimization_complete",
            total_runs=len(results),
            best_metric=results[0].get_metric(metric) if results else 0,
        )

        return results

    async def _run_backtest(
        self,
        data: dict[str, pd.DataFrame],
        start: Any | None,
        end: Any | None,
    ) -> BacktestResult:
        """Run a single backtest with current settings."""
        engine = BacktestEngine(
            initial_balance=self.config.initial_balance,
            risk_profile=self.config.risk_profile,
            slippage=self.config.slippage,
            commission=self.config.commission,
        )

        return await engine.run(data, start=start, end=end)

    def _save_original_settings(self) -> None:
        """Save original settings for restoration."""
        settings = get_settings()
        self._original_settings = {
            "oracle": {
                "rsi_period": settings.oracle.rsi_period,
                "rsi_overbought": settings.oracle.rsi_overbought,
                "rsi_oversold": settings.oracle.rsi_oversold,
                "macd_fast": settings.oracle.macd_fast,
                "macd_slow": settings.oracle.macd_slow,
                "macd_signal": settings.oracle.macd_signal,
                "bbands_period": settings.oracle.bbands_period,
                "bbands_std": settings.oracle.bbands_std,
            },
            "risk": {
                "risk_per_trade": settings.risk.risk_per_trade,
                "min_risk_reward": settings.risk.min_risk_reward,
                "atr_multiplier": settings.risk.atr_multiplier,
                "max_daily_drawdown": settings.risk.max_daily_drawdown,
                "max_open_positions": settings.risk.max_open_positions,
            },
        }

    def _restore_original_settings(self) -> None:
        """Restore original settings."""
        if self._original_settings is None:
            return

        settings = get_settings()

        for key, value in self._original_settings["oracle"].items():
            if hasattr(settings.oracle, key):
                object.__setattr__(settings.oracle, key, value)

        for key, value in self._original_settings["risk"].items():
            if hasattr(settings.risk, key):
                object.__setattr__(settings.risk, key, value)

    def _apply_parameters(self, params: dict[str, dict[str, Any]]) -> None:
        """Apply parameter values to global settings."""
        settings = get_settings()

        # Apply oracle parameters
        for key, value in params.get("oracle", {}).items():
            if hasattr(settings.oracle, key):
                object.__setattr__(settings.oracle, key, value)

        # Apply risk parameters
        for key, value in params.get("risk", {}).items():
            if hasattr(settings.risk, key):
                object.__setattr__(settings.risk, key, value)

    def _sort_results(
        self,
        results: list[OptimizationResult],
        metric: str,
        ascending: bool = False,
    ) -> list[OptimizationResult]:
        """Sort results by a metric.

        Args:
            results: List of optimization results
            metric: Metric name to sort by
            ascending: Sort ascending (lower is better) if True

        Returns:
            Sorted list of results
        """
        # Metrics where lower is better
        lower_is_better = {"max_drawdown", "max_drawdown_duration"}
        should_reverse = metric not in lower_is_better

        if ascending:
            should_reverse = not should_reverse

        return sorted(
            results,
            key=lambda r: r.get_metric(metric),
            reverse=should_reverse,
        )


# Convenience function
async def run_optimization(
    data: dict[str, pd.DataFrame],
    grid: ParameterGrid,
    metric: str = "sharpe_ratio",
    initial_balance: float = 10000.0,
) -> list[OptimizationResult]:
    """Run parameter optimization with default settings.

    Args:
        data: Dict of {symbol: OHLCV DataFrame}
        grid: Parameter grid to test
        metric: Metric to optimize for
        initial_balance: Starting balance

    Returns:
        List of OptimizationResult sorted by metric
    """
    config = OptimizationConfig(initial_balance=initial_balance)
    engine = OptimizationEngine(config)
    return await engine.optimize(data, grid, metric)
