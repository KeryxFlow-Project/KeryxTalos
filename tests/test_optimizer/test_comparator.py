"""Tests for the result comparator module."""


import pytest

from keryxflow.backtester.report import BacktestResult
from keryxflow.optimizer.comparator import ResultComparator
from keryxflow.optimizer.engine import OptimizationResult


def make_result(
    sharpe: float = 1.0,
    total_return: float = 0.1,
    win_rate: float = 0.5,
    max_drawdown: float = 0.1,
    total_trades: int = 10,
    rsi_period: int = 14,
    risk_per_trade: float = 0.01,
) -> OptimizationResult:
    """Helper to create OptimizationResult for testing."""
    metrics = BacktestResult(
        initial_balance=10000.0,
        final_balance=10000.0 * (1 + total_return),
        total_return=total_return,
        total_trades=total_trades,
        winning_trades=int(total_trades * win_rate),
        losing_trades=int(total_trades * (1 - win_rate)),
        win_rate=win_rate,
        avg_win=100.0,
        avg_loss=50.0,
        expectancy=50.0,
        profit_factor=2.0,
        max_drawdown=max_drawdown,
        max_drawdown_duration=10,
        sharpe_ratio=sharpe,
        trades=[],
        equity_curve=[10000.0],
    )

    return OptimizationResult(
        parameters={
            "oracle": {"rsi_period": rsi_period},
            "risk": {"risk_per_trade": risk_per_trade},
        },
        metrics=metrics,
        run_time=1.0,
        run_index=0,
    )


class TestResultComparator:
    """Tests for ResultComparator class."""

    def test_rank_by_metric_sharpe(self):
        """Test ranking by Sharpe ratio."""
        results = [
            make_result(sharpe=1.0),
            make_result(sharpe=2.0),
            make_result(sharpe=1.5),
        ]

        comparator = ResultComparator(results)
        ranked = comparator.rank_by_metric("sharpe_ratio")

        assert ranked[0].metrics.sharpe_ratio == 2.0
        assert ranked[1].metrics.sharpe_ratio == 1.5
        assert ranked[2].metrics.sharpe_ratio == 1.0

    def test_rank_by_metric_drawdown(self):
        """Test ranking by max drawdown (lower is better)."""
        results = [
            make_result(max_drawdown=0.1),
            make_result(max_drawdown=0.05),
            make_result(max_drawdown=0.15),
        ]

        comparator = ResultComparator(results)
        ranked = comparator.rank_by_metric("max_drawdown")

        # Lower drawdown should be first
        assert ranked[0].metrics.max_drawdown == 0.05
        assert ranked[1].metrics.max_drawdown == 0.1
        assert ranked[2].metrics.max_drawdown == 0.15

    def test_top_n(self):
        """Test getting top N results."""
        results = [
            make_result(sharpe=1.0),
            make_result(sharpe=3.0),
            make_result(sharpe=2.0),
            make_result(sharpe=1.5),
            make_result(sharpe=2.5),
        ]

        comparator = ResultComparator(results)
        top = comparator.top_n(3, "sharpe_ratio")

        assert len(top) == 3
        assert top[0].metrics.sharpe_ratio == 3.0
        assert top[1].metrics.sharpe_ratio == 2.5
        assert top[2].metrics.sharpe_ratio == 2.0

    def test_bottom_n(self):
        """Test getting bottom N results."""
        results = [
            make_result(sharpe=1.0),
            make_result(sharpe=3.0),
            make_result(sharpe=2.0),
        ]

        comparator = ResultComparator(results)
        bottom = comparator.bottom_n(2, "sharpe_ratio")

        assert len(bottom) == 2
        assert bottom[0].metrics.sharpe_ratio == 2.0
        assert bottom[1].metrics.sharpe_ratio == 1.0

    def test_filter_by_min_trades(self):
        """Test filtering by minimum trades."""
        results = [
            make_result(total_trades=5),
            make_result(total_trades=15),
            make_result(total_trades=25),
        ]

        comparator = ResultComparator(results)
        filtered = comparator.filter_by(min_trades=10)

        assert len(filtered) == 2
        assert all(r.metrics.total_trades >= 10 for r in filtered)

    def test_filter_by_multiple_criteria(self):
        """Test filtering by multiple criteria."""
        results = [
            make_result(sharpe=1.0, win_rate=0.4, max_drawdown=0.15),
            make_result(sharpe=2.0, win_rate=0.6, max_drawdown=0.05),
            make_result(sharpe=1.5, win_rate=0.55, max_drawdown=0.08),
        ]

        comparator = ResultComparator(results)
        filtered = comparator.filter_by(
            min_win_rate=0.5,
            max_drawdown=0.1,
        )

        assert len(filtered) == 2
        assert all(r.metrics.win_rate >= 0.5 for r in filtered)
        assert all(r.metrics.max_drawdown <= 0.1 for r in filtered)

    def test_parameter_sensitivity(self):
        """Test parameter sensitivity analysis."""
        results = [
            make_result(sharpe=1.0, rsi_period=7),
            make_result(sharpe=1.2, rsi_period=7),
            make_result(sharpe=2.0, rsi_period=14),
            make_result(sharpe=2.2, rsi_period=14),
            make_result(sharpe=1.5, rsi_period=21),
            make_result(sharpe=1.7, rsi_period=21),
        ]

        comparator = ResultComparator(results)
        sensitivity = comparator.parameter_sensitivity("rsi_period", "sharpe_ratio")

        assert sensitivity.name == "rsi_period"
        assert set(sensitivity.values) == {7, 14, 21}
        assert sensitivity.best_value == 14  # Highest average
        assert sensitivity.avg_metrics[7] == pytest.approx(1.1, rel=0.01)
        assert sensitivity.avg_metrics[14] == pytest.approx(2.1, rel=0.01)
        assert sensitivity.avg_metrics[21] == pytest.approx(1.6, rel=0.01)

    def test_all_sensitivities(self):
        """Test getting sensitivities for all parameters."""
        results = [
            make_result(rsi_period=7, risk_per_trade=0.01),
            make_result(rsi_period=14, risk_per_trade=0.02),
        ]

        comparator = ResultComparator(results)
        sensitivities = comparator.all_sensitivities("sharpe_ratio")

        assert "rsi_period" in sensitivities
        assert "risk_per_trade" in sensitivities

    def test_metrics_summary(self):
        """Test metrics summary statistics."""
        results = [
            make_result(sharpe=1.0, total_return=0.1),
            make_result(sharpe=2.0, total_return=0.2),
            make_result(sharpe=1.5, total_return=0.15),
        ]

        comparator = ResultComparator(results)
        summary = comparator.metrics_summary()

        assert "sharpe_ratio" in summary
        assert summary["sharpe_ratio"]["min"] == 1.0
        assert summary["sharpe_ratio"]["max"] == 2.0
        assert summary["sharpe_ratio"]["avg"] == pytest.approx(1.5, rel=0.01)

    def test_best_parameters(self):
        """Test extracting best parameters."""
        results = [
            make_result(sharpe=1.0, rsi_period=7, risk_per_trade=0.01),
            make_result(sharpe=2.0, rsi_period=14, risk_per_trade=0.02),
            make_result(sharpe=1.5, rsi_period=21, risk_per_trade=0.01),
        ]

        comparator = ResultComparator(results)
        best = comparator.best_parameters("sharpe_ratio")

        assert best["rsi_period"] == 14
        assert best["risk_per_trade"] == 0.02

    def test_empty_results(self):
        """Test handling empty results."""
        comparator = ResultComparator([])

        assert comparator.rank_by_metric("sharpe_ratio") == []
        assert comparator.top_n(5) == []
        assert comparator.all_sensitivities() == {}
        assert comparator.metrics_summary() == {}
        assert comparator.best_parameters() == {}
