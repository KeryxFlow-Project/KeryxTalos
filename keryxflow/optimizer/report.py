"""Report generation for optimization results."""

import csv
from pathlib import Path
from typing import Any

from keryxflow.optimizer.comparator import ResultComparator
from keryxflow.optimizer.engine import OptimizationResult


class OptimizationReport:
    """Generate reports from optimization results.

    Provides methods for:
    - Terminal summary output
    - CSV export of all results
    - Best parameters extraction
    """

    def __init__(self, results: list[OptimizationResult]):
        """Initialize with optimization results.

        Args:
            results: List of optimization results
        """
        self.results = results
        self.comparator = ResultComparator(results)

    def print_summary(
        self,
        metric: str = "sharpe_ratio",
        top_n: int = 5,
    ) -> str:
        """Generate a formatted summary report.

        Args:
            metric: Primary metric to rank by
            top_n: Number of top results to show

        Returns:
            Formatted string for terminal output
        """
        if not self.results:
            return "No optimization results to display."

        total_time = sum(r.run_time for r in self.results)

        lines = [
            "",
            "=" * 50,
            "         OPTIMIZATION REPORT",
            "=" * 50,
            "",
            "GRID SUMMARY",
            "-" * 50,
            f"  Parameters:     {self._count_parameters()}",
            f"  Combinations:   {len(self.results)}",
            f"  Total Runtime:  {self._format_time(total_time)}",
            "",
        ]

        # Top results
        top_results = self.comparator.top_n(top_n, metric)
        lines.append(f"TOP {len(top_results)} RESULTS (by {metric.replace('_', ' ').title()})")
        lines.append("-" * 50)

        for i, result in enumerate(top_results, 1):
            m = result.metrics
            params_str = self._format_params_short(result.flat_parameters())

            lines.append(
                f"  #{i}  Sharpe: {m.sharpe_ratio:.2f}  Return: {m.total_return * 100:+.1f}%  Win: {m.win_rate * 100:.0f}%"
            )
            lines.append(f"      {params_str}")
            lines.append("")

        # Parameter sensitivity
        lines.append("PARAMETER SENSITIVITY")
        lines.append("-" * 50)

        sensitivities = self.comparator.all_sensitivities(metric)
        for param_name, sensitivity in sensitivities.items():
            lines.append(f"  {param_name}:")
            for value, avg_metric in sorted(sensitivity.avg_metrics.items()):
                is_best = value == sensitivity.best_value
                marker = "(best)" if is_best else ""
                lines.append(f"    {value:>8} -> Avg {metric}: {avg_metric:.3f} {marker}")
            lines.append("")

        # Best parameters
        lines.append("BEST PARAMETERS")
        lines.append("-" * 50)
        best = self.comparator.best_parameters(metric)
        for name, value in best.items():
            lines.append(f"  {name}: {value}")

        lines.append("")
        lines.append("=" * 50)

        return "\n".join(lines)

    def print_compact(
        self,
        metric: str = "sharpe_ratio",
        top_n: int = 10,
    ) -> str:
        """Generate a compact summary table.

        Args:
            metric: Metric to rank by
            top_n: Number of results to show

        Returns:
            Formatted table string
        """
        if not self.results:
            return "No results."

        top_results = self.comparator.top_n(top_n, metric)

        lines = [
            "",
            f"{'#':<3} {'Sharpe':>8} {'Return':>8} {'Win':>6} {'Trades':>7} {'MaxDD':>7} Parameters",
            "-" * 70,
        ]

        for i, result in enumerate(top_results, 1):
            m = result.metrics
            params = self._format_params_short(result.flat_parameters())

            lines.append(
                f"{i:<3} {m.sharpe_ratio:>8.2f} "
                f"{m.total_return * 100:>+7.1f}% "
                f"{m.win_rate * 100:>5.0f}% "
                f"{m.total_trades:>7} "
                f"{m.max_drawdown * 100:>6.1f}% "
                f"{params}"
            )

        return "\n".join(lines)

    def save_csv(
        self,
        path: str | Path,
        include_all_metrics: bool = True,
    ) -> None:
        """Save all results to a CSV file.

        Args:
            path: Output file path
            include_all_metrics: Include all available metrics
        """
        if not self.results:
            return

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Determine columns
        param_names = list(self.results[0].flat_parameters().keys())
        metric_names = [
            "sharpe_ratio",
            "total_return",
            "win_rate",
            "profit_factor",
            "max_drawdown",
            "max_drawdown_duration",
            "total_trades",
            "winning_trades",
            "losing_trades",
            "avg_win",
            "avg_loss",
            "expectancy",
        ]

        if not include_all_metrics:
            metric_names = metric_names[:5]

        # Write CSV
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)

            # Header
            header = ["run_index"] + param_names + metric_names + ["run_time"]
            writer.writerow(header)

            # Data rows
            for result in self.results:
                params = result.flat_parameters()
                row = [result.run_index]

                for pname in param_names:
                    row.append(params.get(pname, ""))

                for mname in metric_names:
                    row.append(result.get_metric(mname))

                row.append(result.run_time)
                writer.writerow(row)

    def save_best_params(
        self,
        path: str | Path,
        metric: str = "sharpe_ratio",
    ) -> None:
        """Save best parameters to a text file.

        Args:
            path: Output file path
            metric: Metric to determine best by
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        best = self.comparator.best_parameters(metric)
        top = self.comparator.top_n(1, metric)

        with open(path, "w") as f:
            f.write(f"# Best Parameters (by {metric})\n")
            f.write(f"# Generated from {len(self.results)} optimization runs\n\n")

            if top:
                m = top[0].metrics
                f.write("# Performance:\n")
                f.write(f"#   Sharpe Ratio: {m.sharpe_ratio:.3f}\n")
                f.write(f"#   Total Return: {m.total_return * 100:+.2f}%\n")
                f.write(f"#   Win Rate: {m.win_rate * 100:.1f}%\n")
                f.write(f"#   Max Drawdown: {m.max_drawdown * 100:.2f}%\n")
                f.write(f"#   Total Trades: {m.total_trades}\n\n")

            f.write("# Parameters:\n")
            for name, value in sorted(best.items()):
                f.write(f"{name}={value}\n")

    def best_parameters(
        self,
        metric: str = "sharpe_ratio",
    ) -> dict[str, Any]:
        """Get the best parameter set.

        Args:
            metric: Metric to optimize for

        Returns:
            Dict with best parameters
        """
        return self.comparator.best_parameters(metric)

    def _count_parameters(self) -> int:
        """Count unique parameters tested."""
        if not self.results:
            return 0
        return len(self.results[0].flat_parameters())

    def _format_time(self, seconds: float) -> str:
        """Format seconds as human-readable time."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{mins}m {secs}s"
        else:
            hours = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            return f"{hours}h {mins}m"

    def _format_params_short(self, params: dict[str, Any]) -> str:
        """Format parameters in a short form."""
        parts = []
        for name, value in params.items():
            # Shorten parameter names
            short_name = name.replace("_period", "").replace("_per_trade", "").replace("min_", "")
            if isinstance(value, float):
                parts.append(f"{short_name}={value:.3g}")
            else:
                parts.append(f"{short_name}={value}")
        return ", ".join(parts)
