"""Monte Carlo simulation for backtest result validation."""

from dataclasses import dataclass, field

import numpy as np

from keryxflow.backtester.report import BacktestResult
from keryxflow.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MonteCarloResult:
    """Result of Monte Carlo simulation.

    Attributes:
        num_simulations: Number of simulations run
        num_trades: Number of trades resampled per simulation
        initial_balance: Starting balance used

        final_equity_percentiles: Percentile distribution of final equity
            Keys: 5, 25, 50, 75, 95
        max_drawdown_percentiles: Percentile distribution of max drawdown
            Keys: 5, 25, 50, 75, 95
        total_return_percentiles: Percentile distribution of total return
            Keys: 5, 25, 50, 75, 95

        ci_95_equity: (lower, upper) 95% confidence interval for final equity
        ci_99_equity: (lower, upper) 99% confidence interval for final equity
        ci_95_max_drawdown: (lower, upper) 95% CI for max drawdown
        ci_99_max_drawdown: (lower, upper) 99% CI for max drawdown

        worst_equity_curve: Equity curve from worst simulation (by final equity)
        median_equity_curve: Equity curve from median simulation
        best_equity_curve: Equity curve from best simulation

        original_final_equity: Final equity from the original backtest
        original_max_drawdown: Max drawdown from the original backtest
    """

    num_simulations: int
    num_trades: int
    initial_balance: float

    final_equity_percentiles: dict[int, float] = field(default_factory=dict)
    max_drawdown_percentiles: dict[int, float] = field(default_factory=dict)
    total_return_percentiles: dict[int, float] = field(default_factory=dict)

    ci_95_equity: tuple[float, float] = (0.0, 0.0)
    ci_99_equity: tuple[float, float] = (0.0, 0.0)
    ci_95_max_drawdown: tuple[float, float] = (0.0, 0.0)
    ci_99_max_drawdown: tuple[float, float] = (0.0, 0.0)

    worst_equity_curve: list[float] = field(default_factory=list)
    median_equity_curve: list[float] = field(default_factory=list)
    best_equity_curve: list[float] = field(default_factory=list)

    original_final_equity: float = 0.0
    original_max_drawdown: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for reporting."""
        return {
            "simulations": self.num_simulations,
            "trades_per_sim": self.num_trades,
            "final_equity": {
                "p5": self.final_equity_percentiles.get(5, 0),
                "p25": self.final_equity_percentiles.get(25, 0),
                "p50": self.final_equity_percentiles.get(50, 0),
                "p75": self.final_equity_percentiles.get(75, 0),
                "p95": self.final_equity_percentiles.get(95, 0),
                "ci_95": self.ci_95_equity,
                "ci_99": self.ci_99_equity,
            },
            "max_drawdown": {
                "p5": self.max_drawdown_percentiles.get(5, 0),
                "p25": self.max_drawdown_percentiles.get(25, 0),
                "p50": self.max_drawdown_percentiles.get(50, 0),
                "p75": self.max_drawdown_percentiles.get(75, 0),
                "p95": self.max_drawdown_percentiles.get(95, 0),
                "ci_95": self.ci_95_max_drawdown,
                "ci_99": self.ci_99_max_drawdown,
            },
            "original": {
                "final_equity": self.original_final_equity,
                "max_drawdown": self.original_max_drawdown,
            },
        }


class MonteCarloEngine:
    """Monte Carlo simulation engine using bootstrap resampling.

    Resamples trades with replacement to estimate the distribution of
    possible outcomes from a backtest's trade set.

    Example:
        mc = MonteCarloEngine(num_simulations=1000, seed=42)
        result = mc.run(backtest_result)
        print(f"95% CI equity: {result.ci_95_equity}")
    """

    def __init__(self, num_simulations: int = 1000, seed: int | None = None):
        """Initialize Monte Carlo engine.

        Args:
            num_simulations: Number of bootstrap simulations to run
            seed: Random seed for reproducibility (None for random)
        """
        self.num_simulations = num_simulations
        self.seed = seed

    def run(self, backtest_result: BacktestResult) -> MonteCarloResult:
        """Run Monte Carlo simulation on backtest trades.

        Takes the PnL from each trade, resamples with replacement N times,
        and rebuilds equity curves to compute confidence intervals.

        Uses two passes: first collects scalars, second collects
        worst/median/best curves to avoid storing all curves in memory.

        Args:
            backtest_result: Result from a backtest run

        Returns:
            MonteCarloResult with distributions and confidence intervals
        """
        trades = backtest_result.trades
        initial_balance = backtest_result.initial_balance

        if len(trades) == 0:
            return MonteCarloResult(
                num_simulations=self.num_simulations,
                num_trades=0,
                initial_balance=initial_balance,
                original_final_equity=backtest_result.final_balance,
                original_max_drawdown=backtest_result.max_drawdown,
            )

        pnls = np.array([t.pnl for t in trades])
        num_trades = len(pnls)

        logger.info(
            "monte_carlo_starting",
            simulations=self.num_simulations,
            trades=num_trades,
        )

        # Pass 1: collect final equities and max drawdowns
        rng = np.random.default_rng(self.seed)
        final_equities = np.empty(self.num_simulations)
        max_drawdowns = np.empty(self.num_simulations)

        for i in range(self.num_simulations):
            resampled_pnls = rng.choice(pnls, size=num_trades, replace=True)
            cumulative = np.cumsum(resampled_pnls)
            equity = initial_balance + cumulative
            final_equities[i] = equity[-1]

            # Max drawdown from equity with initial balance prepended
            full_equity = np.empty(num_trades + 1)
            full_equity[0] = initial_balance
            full_equity[1:] = equity
            peak = np.maximum.accumulate(full_equity)
            with np.errstate(divide="ignore", invalid="ignore"):
                dd = (peak - full_equity) / peak
                dd = np.clip(dd, 0.0, 1.0)
                dd = np.nan_to_num(dd, nan=0.0, posinf=1.0, neginf=0.0)
            max_drawdowns[i] = float(np.max(dd))

        # Find target indices for worst/median/best
        worst_idx = int(np.argmin(final_equities))
        best_idx = int(np.argmax(final_equities))
        median_val = float(np.median(final_equities))
        median_idx = int(np.argmin(np.abs(final_equities - median_val)))

        # Pass 2: replay with same seed to extract curves for worst/median/best
        target_indices = {worst_idx, median_idx, best_idx}
        rng2 = np.random.default_rng(self.seed)
        stored_curves: dict[int, list[float]] = {}

        for i in range(self.num_simulations):
            resampled_pnls = rng2.choice(pnls, size=num_trades, replace=True)
            if i in target_indices:
                cumulative = np.cumsum(resampled_pnls)
                full_equity = np.empty(num_trades + 1)
                full_equity[0] = initial_balance
                full_equity[1:] = initial_balance + cumulative
                stored_curves[i] = full_equity.tolist()

        # Compute percentiles
        pct_keys = [5, 25, 50, 75, 95]
        equity_pcts = np.percentile(final_equities, pct_keys)
        dd_pcts = np.percentile(max_drawdowns, pct_keys)
        total_returns = (final_equities - initial_balance) / initial_balance
        return_pcts = np.percentile(total_returns, pct_keys)

        result = MonteCarloResult(
            num_simulations=self.num_simulations,
            num_trades=num_trades,
            initial_balance=initial_balance,
            final_equity_percentiles=dict(
                zip(pct_keys, [float(v) for v in equity_pcts], strict=True)
            ),
            max_drawdown_percentiles=dict(zip(pct_keys, [float(v) for v in dd_pcts], strict=True)),
            total_return_percentiles=dict(
                zip(pct_keys, [float(v) for v in return_pcts], strict=True)
            ),
            ci_95_equity=(
                float(np.percentile(final_equities, 2.5)),
                float(np.percentile(final_equities, 97.5)),
            ),
            ci_99_equity=(
                float(np.percentile(final_equities, 0.5)),
                float(np.percentile(final_equities, 99.5)),
            ),
            ci_95_max_drawdown=(
                float(np.percentile(max_drawdowns, 2.5)),
                float(np.percentile(max_drawdowns, 97.5)),
            ),
            ci_99_max_drawdown=(
                float(np.percentile(max_drawdowns, 0.5)),
                float(np.percentile(max_drawdowns, 99.5)),
            ),
            worst_equity_curve=stored_curves.get(worst_idx, []),
            median_equity_curve=stored_curves.get(median_idx, []),
            best_equity_curve=stored_curves.get(best_idx, []),
            original_final_equity=backtest_result.final_balance,
            original_max_drawdown=backtest_result.max_drawdown,
        )

        logger.info(
            "monte_carlo_complete",
            median_equity=result.final_equity_percentiles.get(50, 0),
            ci_95=result.ci_95_equity,
        )

        return result
