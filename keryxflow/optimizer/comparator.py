"""Result comparison and analysis for optimization runs."""

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from keryxflow.optimizer.engine import OptimizationResult


@dataclass
class ParameterSensitivity:
    """Sensitivity analysis for a single parameter.

    Attributes:
        name: Parameter name
        values: List of tested values
        avg_metrics: Dict mapping value -> average metric value
        best_value: Value that achieved best average metric
        variance: Variance in metric across values
    """

    name: str
    values: list[Any]
    avg_metrics: dict[Any, float]
    best_value: Any
    variance: float


class ResultComparator:
    """Compare and analyze optimization results.

    Provides methods for:
    - Ranking results by any metric
    - Extracting top N performers
    - Parameter sensitivity analysis
    - Metric correlation analysis
    """

    def __init__(self, results: list[OptimizationResult]):
        """Initialize with optimization results.

        Args:
            results: List of optimization results to analyze
        """
        self.results = results

    def rank_by_metric(
        self,
        metric: str,
        ascending: bool = False,
    ) -> list[OptimizationResult]:
        """Rank results by a specific metric.

        Args:
            metric: Metric name to rank by
            ascending: If True, sort ascending (lower is better)

        Returns:
            Sorted list of results
        """
        # Metrics where lower is better
        lower_is_better = {"max_drawdown", "max_drawdown_duration", "avg_loss"}
        should_reverse = metric not in lower_is_better

        if ascending:
            should_reverse = not should_reverse

        return sorted(
            self.results,
            key=lambda r: r.get_metric(metric),
            reverse=should_reverse,
        )

    def top_n(
        self,
        n: int = 10,
        metric: str = "sharpe_ratio",
    ) -> list[OptimizationResult]:
        """Get top N results by a metric.

        Args:
            n: Number of results to return
            metric: Metric to rank by

        Returns:
            Top N results
        """
        ranked = self.rank_by_metric(metric)
        return ranked[:n]

    def bottom_n(
        self,
        n: int = 10,
        metric: str = "sharpe_ratio",
    ) -> list[OptimizationResult]:
        """Get bottom N results by a metric.

        Args:
            n: Number of results to return
            metric: Metric to rank by

        Returns:
            Bottom N results
        """
        ranked = self.rank_by_metric(metric)
        return ranked[-n:]

    def filter_by(
        self,
        min_trades: int | None = None,
        min_win_rate: float | None = None,
        max_drawdown: float | None = None,
        min_sharpe: float | None = None,
    ) -> list[OptimizationResult]:
        """Filter results by criteria.

        Args:
            min_trades: Minimum number of trades
            min_win_rate: Minimum win rate (as decimal)
            max_drawdown: Maximum drawdown (as decimal)
            min_sharpe: Minimum Sharpe ratio

        Returns:
            Filtered list of results
        """
        filtered = self.results

        if min_trades is not None:
            filtered = [r for r in filtered if r.metrics.total_trades >= min_trades]

        if min_win_rate is not None:
            filtered = [r for r in filtered if r.metrics.win_rate >= min_win_rate]

        if max_drawdown is not None:
            filtered = [r for r in filtered if r.metrics.max_drawdown <= max_drawdown]

        if min_sharpe is not None:
            filtered = [r for r in filtered if r.metrics.sharpe_ratio >= min_sharpe]

        return filtered

    def parameter_sensitivity(
        self,
        parameter: str,
        metric: str = "sharpe_ratio",
    ) -> ParameterSensitivity:
        """Analyze how a parameter affects a metric.

        Args:
            parameter: Parameter name to analyze
            metric: Metric to measure impact on

        Returns:
            ParameterSensitivity with analysis results
        """
        # Group results by parameter value
        value_metrics: dict[Any, list[float]] = defaultdict(list)

        for result in self.results:
            flat_params = result.flat_parameters()
            if parameter in flat_params:
                value = flat_params[parameter]
                metric_value = result.get_metric(metric)
                value_metrics[value].append(metric_value)

        # Calculate averages
        avg_metrics: dict[Any, float] = {}
        for value, metrics_list in value_metrics.items():
            avg_metrics[value] = sum(metrics_list) / len(metrics_list)

        # Find best value
        values = list(avg_metrics.keys())

        # Handle metrics where lower is better
        lower_is_better = {"max_drawdown", "max_drawdown_duration", "avg_loss"}
        if metric in lower_is_better:
            best_value = min(avg_metrics.keys(), key=lambda v: avg_metrics[v])
        else:
            best_value = max(avg_metrics.keys(), key=lambda v: avg_metrics[v])

        # Calculate variance
        all_avgs = list(avg_metrics.values())
        if len(all_avgs) > 1:
            mean = sum(all_avgs) / len(all_avgs)
            variance = sum((x - mean) ** 2 for x in all_avgs) / len(all_avgs)
        else:
            variance = 0.0

        return ParameterSensitivity(
            name=parameter,
            values=values,
            avg_metrics=avg_metrics,
            best_value=best_value,
            variance=variance,
        )

    def all_sensitivities(
        self,
        metric: str = "sharpe_ratio",
    ) -> dict[str, ParameterSensitivity]:
        """Get sensitivity analysis for all parameters.

        Args:
            metric: Metric to measure impact on

        Returns:
            Dict mapping parameter name to sensitivity analysis
        """
        if not self.results:
            return {}

        # Get all parameter names
        first_params = self.results[0].flat_parameters()
        param_names = list(first_params.keys())

        sensitivities = {}
        for param in param_names:
            sensitivities[param] = self.parameter_sensitivity(param, metric)

        return sensitivities

    def metrics_summary(self) -> dict[str, dict[str, float]]:
        """Get summary statistics for all metrics.

        Returns:
            Dict with min/max/avg for each metric
        """
        if not self.results:
            return {}

        metrics_to_summarize = [
            "sharpe_ratio",
            "total_return",
            "win_rate",
            "profit_factor",
            "max_drawdown",
            "total_trades",
            "expectancy",
        ]

        summary = {}
        for metric_name in metrics_to_summarize:
            values = [r.get_metric(metric_name) for r in self.results]

            if not values:
                continue

            summary[metric_name] = {
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
            }

        return summary

    def best_parameters(
        self,
        metric: str = "sharpe_ratio",
    ) -> dict[str, Any]:
        """Get the best parameter set.

        Args:
            metric: Metric to optimize for

        Returns:
            Flattened dict of best parameters
        """
        top = self.top_n(1, metric)
        if not top:
            return {}
        return top[0].flat_parameters()

    def consistency_score(
        self,
        parameter: str,
        metric: str = "sharpe_ratio",
    ) -> float:
        """Calculate how consistently a parameter value performs.

        Higher score means the parameter has more impact on the metric.

        Args:
            parameter: Parameter to analyze
            metric: Metric to measure

        Returns:
            Consistency score (0-1, higher = more consistent/impactful)
        """
        sensitivity = self.parameter_sensitivity(parameter, metric)

        if not sensitivity.avg_metrics or sensitivity.variance == 0:
            return 0.0

        # Normalize variance relative to mean
        mean = sum(sensitivity.avg_metrics.values()) / len(sensitivity.avg_metrics)
        if mean == 0:
            return 0.0

        # Higher variance = more impact = higher score
        # Cap at 1.0
        score = min(1.0, sensitivity.variance / abs(mean))
        return score
