"""Walk-forward analysis for out-of-sample validation."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

from keryxflow.backtester.engine import BacktestEngine
from keryxflow.backtester.report import BacktestResult
from keryxflow.core.logging import get_logger
from keryxflow.core.models import RiskProfile
from keryxflow.optimizer.engine import OptimizationConfig, OptimizationEngine
from keryxflow.optimizer.grid import ParameterGrid

logger = get_logger(__name__)


@dataclass
class WalkForwardWindow:
    """Result for a single walk-forward window.

    Attributes:
        window_index: Index of this window (0-based)
        is_start: Start datetime of the in-sample period
        is_end: End datetime of the in-sample period
        oos_start: Start datetime of the out-of-sample period
        oos_end: End datetime of the out-of-sample period
        best_params: Best parameters found during IS optimization
        is_result: BacktestResult for the in-sample period
        oos_result: BacktestResult for the out-of-sample period
        degradation_ratio: OOS return / IS return (< 1.0 means overfitting)
    """

    window_index: int
    is_start: datetime
    is_end: datetime
    oos_start: datetime
    oos_end: datetime
    best_params: dict[str, dict[str, Any]]
    is_result: BacktestResult
    oos_result: BacktestResult
    degradation_ratio: float


@dataclass
class WalkForwardResult:
    """Aggregate result of walk-forward analysis.

    Attributes:
        windows: List of per-window results
        num_windows: Number of windows analyzed
        oos_pct: Fraction of data used for out-of-sample
        aggregate_oos_return: Combined OOS total return
        aggregate_oos_trades: Total OOS trades across all windows
        aggregate_oos_win_rate: Combined OOS win rate
        avg_degradation_ratio: Average IS-to-OOS degradation
        oos_equity_curve: Concatenated OOS equity curve
    """

    windows: list[WalkForwardWindow] = field(default_factory=list)
    num_windows: int = 0
    oos_pct: float = 0.3
    aggregate_oos_return: float = 0.0
    aggregate_oos_trades: int = 0
    aggregate_oos_win_rate: float = 0.0
    avg_degradation_ratio: float = 0.0
    oos_equity_curve: list[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for reporting."""
        return {
            "num_windows": self.num_windows,
            "oos_pct": self.oos_pct,
            "aggregate": {
                "oos_return": self.aggregate_oos_return,
                "oos_return_pct": f"{self.aggregate_oos_return * 100:.2f}%",
                "oos_trades": self.aggregate_oos_trades,
                "oos_win_rate": self.aggregate_oos_win_rate,
                "avg_degradation": self.avg_degradation_ratio,
            },
            "windows": [
                {
                    "index": w.window_index,
                    "is_period": f"{w.is_start} - {w.is_end}",
                    "oos_period": f"{w.oos_start} - {w.oos_end}",
                    "is_return": w.is_result.total_return,
                    "oos_return": w.oos_result.total_return,
                    "degradation": w.degradation_ratio,
                    "oos_trades": w.oos_result.total_trades,
                }
                for w in self.windows
            ],
        }


@dataclass
class WalkForwardConfig:
    """Configuration for walk-forward analysis.

    Attributes:
        num_windows: Number of rolling windows
        oos_pct: Fraction of each window used for OOS (0.0-1.0)
        optimization_metric: Metric to optimize during IS phase
        initial_balance: Starting balance per window
        risk_profile: Risk profile for backtests
        slippage: Slippage percentage
        commission: Commission percentage
    """

    num_windows: int = 5
    oos_pct: float = 0.3
    optimization_metric: str = "sharpe_ratio"
    initial_balance: float = 10000.0
    risk_profile: RiskProfile = RiskProfile.BALANCED
    slippage: float = 0.001
    commission: float = 0.001


class WalkForwardEngine:
    """Walk-forward analysis engine.

    Splits data into rolling non-overlapping windows. For each window:
    1. Optimizes parameters on the in-sample (IS) portion
    2. Validates the best parameters on the out-of-sample (OOS) portion
    3. Computes degradation ratio (OOS/IS performance)

    Example:
        wf = WalkForwardEngine(config=WalkForwardConfig(num_windows=5))
        result = await wf.run(
            data={"BTC/USDT": df},
            grid=ParameterGrid.quick_grid(),
        )
        print(f"Avg degradation: {result.avg_degradation_ratio:.2f}")
    """

    def __init__(self, config: WalkForwardConfig | None = None):
        """Initialize walk-forward engine.

        Args:
            config: Walk-forward configuration (uses defaults if None)
        """
        self.config = config or WalkForwardConfig()

    async def run(
        self,
        data: dict[str, pd.DataFrame],
        grid: ParameterGrid,
        progress_callback: Any | None = None,
    ) -> WalkForwardResult:
        """Run walk-forward analysis.

        Args:
            data: Dict of {symbol: OHLCV DataFrame} with 'datetime' column
            grid: Parameter grid for IS optimization
            progress_callback: Optional callback(window_idx, num_windows)

        Returns:
            WalkForwardResult with per-window and aggregate metrics
        """
        # Get all timestamps from the data
        all_timestamps: list[datetime] = []
        for df in data.values():
            all_timestamps.extend(df["datetime"].tolist())
        all_timestamps = sorted(set(all_timestamps))

        if len(all_timestamps) < self.config.num_windows * 2:
            raise ValueError(
                f"Insufficient data for {self.config.num_windows} windows. "
                f"Need at least {self.config.num_windows * 2} timestamps, "
                f"got {len(all_timestamps)}."
            )

        # Split into windows
        windows = self._split_windows(all_timestamps)

        logger.info(
            "walk_forward_starting",
            num_windows=len(windows),
            oos_pct=self.config.oos_pct,
            total_timestamps=len(all_timestamps),
        )

        opt_config = OptimizationConfig(
            initial_balance=self.config.initial_balance,
            risk_profile=self.config.risk_profile,
            slippage=self.config.slippage,
            commission=self.config.commission,
        )

        window_results: list[WalkForwardWindow] = []

        for idx, (is_start, is_end, oos_start, oos_end) in enumerate(windows):
            if progress_callback:
                progress_callback(idx, len(windows))

            logger.info(
                "walk_forward_window",
                window=idx + 1,
                is_period=f"{is_start} - {is_end}",
                oos_period=f"{oos_start} - {oos_end}",
            )

            # Slice data for IS period
            is_data = self._slice_data(data, is_start, is_end)
            oos_data = self._slice_data(data, oos_start, oos_end)

            if not is_data or not oos_data:
                logger.warning("walk_forward_window_skipped", window=idx + 1, reason="no_data")
                continue

            # Phase 1: Optimize on IS data
            optimizer = OptimizationEngine(config=opt_config)
            try:
                opt_results = await optimizer.optimize(
                    data=is_data,
                    grid=grid,
                    metric=self.config.optimization_metric,
                    start=is_start,
                    end=is_end,
                )
            except Exception as e:
                logger.warning("walk_forward_optimization_failed", window=idx + 1, error=str(e))
                continue

            if not opt_results:
                logger.warning("walk_forward_no_results", window=idx + 1)
                continue

            best = opt_results[0]
            best_params = best.parameters
            is_result = best.metrics

            # Phase 2: Validate best params on OOS data
            optimizer._apply_parameters(best_params)
            try:
                engine = BacktestEngine(
                    initial_balance=self.config.initial_balance,
                    risk_profile=self.config.risk_profile,
                    slippage=self.config.slippage,
                    commission=self.config.commission,
                )
                oos_result = await engine.run(oos_data, start=oos_start, end=oos_end)
            except Exception as e:
                logger.warning("walk_forward_oos_failed", window=idx + 1, error=str(e))
                optimizer._restore_original_settings()
                continue
            finally:
                optimizer._restore_original_settings()

            # Calculate degradation ratio
            if is_result.total_return != 0:
                degradation = oos_result.total_return / is_result.total_return
            else:
                degradation = 0.0

            window_result = WalkForwardWindow(
                window_index=idx,
                is_start=is_start,
                is_end=is_end,
                oos_start=oos_start,
                oos_end=oos_end,
                best_params=best_params,
                is_result=is_result,
                oos_result=oos_result,
                degradation_ratio=degradation,
            )
            window_results.append(window_result)

        # Compute aggregates
        return self._compute_aggregates(window_results)

    def _split_windows(
        self, timestamps: list[datetime]
    ) -> list[tuple[datetime, datetime, datetime, datetime]]:
        """Split timestamps into non-overlapping IS/OOS windows.

        Returns:
            List of (is_start, is_end, oos_start, oos_end) tuples
        """
        n = len(timestamps)
        window_size = n // self.config.num_windows
        windows = []

        for i in range(self.config.num_windows):
            start_idx = i * window_size
            end_idx = (i + 1) * window_size if i < self.config.num_windows - 1 else n

            window_timestamps = timestamps[start_idx:end_idx]
            if len(window_timestamps) < 2:
                continue

            # Split window into IS and OOS
            split_idx = int(len(window_timestamps) * (1 - self.config.oos_pct))
            split_idx = max(1, min(split_idx, len(window_timestamps) - 1))

            is_start = window_timestamps[0]
            is_end = window_timestamps[split_idx - 1]
            oos_start = window_timestamps[split_idx]
            oos_end = window_timestamps[-1]

            windows.append((is_start, is_end, oos_start, oos_end))

        return windows

    def _slice_data(
        self,
        data: dict[str, pd.DataFrame],
        start: datetime,
        end: datetime,
    ) -> dict[str, pd.DataFrame]:
        """Slice data to a time range."""
        sliced = {}
        for symbol, df in data.items():
            mask = (df["datetime"] >= start) & (df["datetime"] <= end)
            subset = df[mask].copy()
            if len(subset) > 0:
                sliced[symbol] = subset
        return sliced

    def _compute_aggregates(self, windows: list[WalkForwardWindow]) -> WalkForwardResult:
        """Compute aggregate metrics from window results."""
        if not windows:
            return WalkForwardResult(num_windows=0, oos_pct=self.config.oos_pct)

        # Aggregate OOS metrics
        total_oos_trades = sum(w.oos_result.total_trades for w in windows)
        total_oos_wins = sum(w.oos_result.winning_trades for w in windows)
        oos_win_rate = total_oos_wins / total_oos_trades if total_oos_trades > 0 else 0.0

        # Chain OOS returns: (1+r1) * (1+r2) * ... - 1
        chained_return = 1.0
        for w in windows:
            chained_return *= 1 + w.oos_result.total_return
        aggregate_oos_return = chained_return - 1

        # Average degradation
        degradations = [w.degradation_ratio for w in windows]
        avg_degradation = sum(degradations) / len(degradations)

        # Concatenate OOS equity curves (normalized)
        oos_equity = [self.config.initial_balance]
        current_balance = self.config.initial_balance
        for w in windows:
            if w.oos_result.equity_curve and len(w.oos_result.equity_curve) > 1:
                curve = w.oos_result.equity_curve
                scale = current_balance / curve[0] if curve[0] != 0 else 1.0
                for eq in curve[1:]:
                    oos_equity.append(eq * scale)
                current_balance = oos_equity[-1]

        return WalkForwardResult(
            windows=windows,
            num_windows=len(windows),
            oos_pct=self.config.oos_pct,
            aggregate_oos_return=aggregate_oos_return,
            aggregate_oos_trades=total_oos_trades,
            aggregate_oos_win_rate=oos_win_rate,
            avg_degradation_ratio=avg_degradation,
            oos_equity_curve=oos_equity,
        )
