"""Tests for HTML report generation."""

from datetime import datetime

from keryxflow.backtester.engine import BacktestTrade
from keryxflow.backtester.html_report import HtmlReportGenerator
from keryxflow.backtester.monte_carlo import MonteCarloEngine
from keryxflow.backtester.report import BacktestResult


def _make_backtest_result() -> BacktestResult:
    """Create a sample BacktestResult for testing."""
    trades = [
        BacktestTrade(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.1,
            entry_price=50000.0,
            entry_time=datetime(2024, 1, 1),
            exit_price=51000.0,
            exit_time=datetime(2024, 1, 2),
            pnl=100.0,
            pnl_percentage=2.0,
            exit_reason="take_profit",
        ),
        BacktestTrade(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.1,
            entry_price=51000.0,
            entry_time=datetime(2024, 1, 3),
            exit_price=50500.0,
            exit_time=datetime(2024, 1, 4),
            pnl=-50.0,
            pnl_percentage=-1.0,
            exit_reason="stop_loss",
        ),
        BacktestTrade(
            symbol="BTC/USDT",
            side="buy",
            quantity=0.1,
            entry_price=50500.0,
            entry_time=datetime(2024, 1, 5),
            exit_price=52000.0,
            exit_time=datetime(2024, 1, 6),
            pnl=150.0,
            pnl_percentage=3.0,
            exit_reason="signal",
        ),
    ]

    return BacktestResult(
        initial_balance=10000.0,
        final_balance=10200.0,
        total_return=0.02,
        total_trades=3,
        winning_trades=2,
        losing_trades=1,
        win_rate=0.667,
        avg_win=125.0,
        avg_loss=50.0,
        expectancy=66.67,
        profit_factor=5.0,
        max_drawdown=0.005,
        max_drawdown_duration=2,
        sharpe_ratio=1.5,
        sortino_ratio=2.0,
        calmar_ratio=1.8,
        trades=trades,
        equity_curve=[10000, 10100, 10050, 10200],
    )


class TestHtmlReportGenerator:
    """Tests for HtmlReportGenerator."""

    def test_generate_basic_report(self, tmp_path):
        """Test basic HTML report generation."""
        result = _make_backtest_result()
        output_path = tmp_path / "report.html"

        gen = HtmlReportGenerator()
        path = gen.generate(result, output_path)

        assert path.exists()
        content = path.read_text()
        assert "<!DOCTYPE html>" in content
        assert "KeryxFlow Backtest Report" in content

    def test_report_contains_metrics(self, tmp_path):
        """Test that report contains key metrics."""
        result = _make_backtest_result()
        output_path = tmp_path / "report.html"

        gen = HtmlReportGenerator()
        gen.generate(result, output_path)

        content = output_path.read_text()
        assert "$10,000.00" in content  # initial balance
        assert "$10,200.00" in content  # final balance
        assert "Sharpe Ratio" in content
        assert "Sortino Ratio" in content
        assert "Calmar Ratio" in content
        assert "Profit Factor" in content

    def test_report_contains_charts(self, tmp_path):
        """Test that report contains embedded chart images."""
        result = _make_backtest_result()
        output_path = tmp_path / "report.html"

        gen = HtmlReportGenerator()
        gen.generate(result, output_path)

        content = output_path.read_text()
        assert "data:image/png;base64," in content

    def test_report_with_monte_carlo(self, tmp_path):
        """Test report with Monte Carlo results."""
        result = _make_backtest_result()
        mc = MonteCarloEngine(num_simulations=50, seed=42)
        mc_result = mc.run(result)

        output_path = tmp_path / "report_mc.html"
        gen = HtmlReportGenerator()
        gen.generate(result, output_path, monte_carlo_result=mc_result)

        content = output_path.read_text()
        assert "Monte Carlo Simulation" in content
        assert "Simulations:" in content

    def test_report_creates_parent_dirs(self, tmp_path):
        """Test that report creates parent directories."""
        result = _make_backtest_result()
        output_path = tmp_path / "subdir" / "nested" / "report.html"

        gen = HtmlReportGenerator()
        gen.generate(result, output_path)

        assert output_path.exists()

    def test_report_no_trades(self, tmp_path):
        """Test report with no trades."""
        result = BacktestResult(
            initial_balance=10000.0,
            final_balance=10000.0,
            total_return=0.0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            expectancy=0.0,
            profit_factor=0.0,
            max_drawdown=0.0,
            max_drawdown_duration=0,
            sharpe_ratio=0.0,
            trades=[],
            equity_curve=[10000.0],
        )

        output_path = tmp_path / "empty_report.html"
        gen = HtmlReportGenerator()
        gen.generate(result, output_path)

        assert output_path.exists()
        content = output_path.read_text()
        assert "KeryxFlow Backtest Report" in content
