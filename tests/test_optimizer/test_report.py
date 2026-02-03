"""Tests for the optimization report module."""

import tempfile
from pathlib import Path

from keryxflow.backtester.report import BacktestResult
from keryxflow.optimizer.engine import OptimizationResult
from keryxflow.optimizer.report import OptimizationReport


def make_result(
    sharpe: float = 1.0,
    total_return: float = 0.1,
    win_rate: float = 0.5,
    max_drawdown: float = 0.1,
    total_trades: int = 10,
    rsi_period: int = 14,
    risk_per_trade: float = 0.01,
    run_time: float = 1.0,
    run_index: int = 0,
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
        run_time=run_time,
        run_index=run_index,
    )


class TestOptimizationReport:
    """Tests for OptimizationReport class."""

    def test_print_summary(self):
        """Test generating summary report."""
        results = [
            make_result(sharpe=2.0, total_return=0.15, rsi_period=14, run_index=0),
            make_result(sharpe=1.5, total_return=0.10, rsi_period=21, run_index=1),
            make_result(sharpe=1.0, total_return=0.05, rsi_period=7, run_index=2),
        ]

        report = OptimizationReport(results)
        summary = report.print_summary()

        assert "OPTIMIZATION REPORT" in summary
        assert "GRID SUMMARY" in summary
        assert "TOP" in summary
        assert "PARAMETER SENSITIVITY" in summary
        assert "BEST PARAMETERS" in summary
        assert "rsi_period" in summary

    def test_print_summary_empty(self):
        """Test summary with empty results."""
        report = OptimizationReport([])
        summary = report.print_summary()

        assert "No optimization results" in summary

    def test_print_compact(self):
        """Test compact output format."""
        results = [
            make_result(sharpe=2.0, total_return=0.15),
            make_result(sharpe=1.5, total_return=0.10),
        ]

        report = OptimizationReport(results)
        compact = report.print_compact()

        assert "Sharpe" in compact
        assert "Return" in compact
        assert "Win" in compact

    def test_save_csv(self):
        """Test saving results to CSV."""
        results = [
            make_result(sharpe=2.0, rsi_period=14, risk_per_trade=0.01, run_index=0),
            make_result(sharpe=1.5, rsi_period=21, risk_per_trade=0.02, run_index=1),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "results.csv"

            report = OptimizationReport(results)
            report.save_csv(csv_path)

            assert csv_path.exists()

            # Read and verify
            content = csv_path.read_text()
            lines = content.strip().split("\n")

            # Check header
            header = lines[0]
            assert "run_index" in header
            assert "rsi_period" in header
            assert "risk_per_trade" in header
            assert "sharpe_ratio" in header

            # Check data rows
            assert len(lines) == 3  # header + 2 results

    def test_save_best_params(self):
        """Test saving best parameters."""
        results = [
            make_result(sharpe=2.0, rsi_period=14, risk_per_trade=0.01),
            make_result(sharpe=1.5, rsi_period=21, risk_per_trade=0.02),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            params_path = Path(tmpdir) / "best_params.txt"

            report = OptimizationReport(results)
            report.save_best_params(params_path, "sharpe_ratio")

            assert params_path.exists()

            content = params_path.read_text()
            assert "rsi_period=14" in content
            assert "risk_per_trade=0.01" in content

    def test_best_parameters(self):
        """Test extracting best parameters."""
        results = [
            make_result(sharpe=2.0, rsi_period=14, risk_per_trade=0.01),
            make_result(sharpe=1.5, rsi_period=21, risk_per_trade=0.02),
        ]

        report = OptimizationReport(results)
        best = report.best_parameters("sharpe_ratio")

        assert best["rsi_period"] == 14
        assert best["risk_per_trade"] == 0.01

    def test_format_time_seconds(self):
        """Test time formatting for seconds."""
        report = OptimizationReport([])

        assert "30.0s" in report._format_time(30.0)
        assert "1.5s" in report._format_time(1.5)

    def test_format_time_minutes(self):
        """Test time formatting for minutes."""
        report = OptimizationReport([])

        result = report._format_time(90)
        assert "1m" in result
        assert "30s" in result

    def test_format_time_hours(self):
        """Test time formatting for hours."""
        report = OptimizationReport([])

        result = report._format_time(3700)
        assert "1h" in result

    def test_creates_output_directories(self):
        """Test that output directories are created."""
        results = [make_result()]

        with tempfile.TemporaryDirectory() as tmpdir:
            nested_path = Path(tmpdir) / "nested" / "dir" / "results.csv"

            report = OptimizationReport(results)
            report.save_csv(nested_path)

            assert nested_path.exists()
