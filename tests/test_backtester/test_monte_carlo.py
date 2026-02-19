"""Tests for Monte Carlo simulation engine."""

import pytest

from keryxflow.backtester.engine import BacktestTrade
from keryxflow.backtester.monte_carlo import MonteCarloEngine
from keryxflow.backtester.report import BacktestResult


def _make_result(trades: list[BacktestTrade], initial_balance: float = 10000.0) -> BacktestResult:
    """Helper to create a BacktestResult with given trades."""
    pnls = [t.pnl for t in trades]
    equity = [initial_balance]
    for p in pnls:
        equity.append(equity[-1] + p)

    final = equity[-1]
    winners = [t for t in trades if t.pnl > 0]
    losers = [t for t in trades if t.pnl <= 0]

    return BacktestResult(
        initial_balance=initial_balance,
        final_balance=final,
        total_return=(final - initial_balance) / initial_balance,
        total_trades=len(trades),
        winning_trades=len(winners),
        losing_trades=len(losers),
        win_rate=len(winners) / len(trades) if trades else 0,
        avg_win=sum(t.pnl for t in winners) / len(winners) if winners else 0,
        avg_loss=sum(abs(t.pnl) for t in losers) / len(losers) if losers else 0,
        expectancy=0,
        profit_factor=0,
        max_drawdown=0,
        max_drawdown_duration=0,
        sharpe_ratio=0,
        trades=trades,
        equity_curve=equity,
    )


def _make_trades(pnls: list[float]) -> list[BacktestTrade]:
    """Helper to create trades from PnL values."""
    from datetime import datetime

    return [
        BacktestTrade(
            symbol="BTC/USDT",
            side="buy",
            quantity=1.0,
            entry_price=50000.0,
            entry_time=datetime(2024, 1, 1),
            exit_price=50000.0 + pnl,
            exit_time=datetime(2024, 1, 2),
            pnl=pnl,
            pnl_percentage=pnl / 500,
            exit_reason="signal",
        )
        for pnl in pnls
    ]


class TestMonteCarloEngine:
    """Tests for MonteCarloEngine."""

    def test_basic_simulation(self):
        """Test basic Monte Carlo simulation runs and produces results."""
        trades = _make_trades([100, -50, 200, -30, 150, -80, 50, 120])
        result = _make_result(trades)

        mc = MonteCarloEngine(num_simulations=100, seed=42)
        mc_result = mc.run(result)

        assert mc_result.num_simulations == 100
        assert mc_result.num_trades == 8
        assert mc_result.initial_balance == 10000.0

    def test_percentile_ordering(self):
        """Test that percentiles are in correct order."""
        trades = _make_trades([100, -50, 200, -30, 150, -80, 50, 120, -10, 80])
        result = _make_result(trades)

        mc = MonteCarloEngine(num_simulations=500, seed=42)
        mc_result = mc.run(result)

        pcts = mc_result.final_equity_percentiles
        assert pcts[5] <= pcts[25] <= pcts[50] <= pcts[75] <= pcts[95]

    def test_confidence_interval_ordering(self):
        """Test that 99% CI is wider than 95% CI."""
        trades = _make_trades([100, -50, 200, -30, 150, -80, 50, 120])
        result = _make_result(trades)

        mc = MonteCarloEngine(num_simulations=500, seed=42)
        mc_result = mc.run(result)

        assert mc_result.ci_99_equity[0] <= mc_result.ci_95_equity[0]
        assert mc_result.ci_99_equity[1] >= mc_result.ci_95_equity[1]

    def test_seed_reproducibility(self):
        """Test that same seed produces same results."""
        trades = _make_trades([100, -50, 200, -30])
        result = _make_result(trades)

        mc1 = MonteCarloEngine(num_simulations=100, seed=123)
        result1 = mc1.run(result)

        mc2 = MonteCarloEngine(num_simulations=100, seed=123)
        result2 = mc2.run(result)

        assert result1.final_equity_percentiles == result2.final_equity_percentiles
        assert result1.ci_95_equity == result2.ci_95_equity

    def test_empty_trades(self):
        """Test Monte Carlo with no trades."""
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

        mc = MonteCarloEngine(num_simulations=10, seed=42)
        mc_result = mc.run(result)

        assert mc_result.num_trades == 0
        assert mc_result.final_equity_percentiles == {}

    def test_single_trade(self):
        """Test Monte Carlo with single trade."""
        trades = _make_trades([100])
        result = _make_result(trades)

        mc = MonteCarloEngine(num_simulations=100, seed=42)
        mc_result = mc.run(result)

        # All simulations should resample the same single trade
        assert mc_result.num_trades == 1
        assert mc_result.final_equity_percentiles[50] == pytest.approx(10100.0, rel=0.01)

    def test_all_winning_trades(self):
        """Test Monte Carlo with all winners."""
        trades = _make_trades([100, 200, 150, 80])
        result = _make_result(trades)

        mc = MonteCarloEngine(num_simulations=100, seed=42)
        mc_result = mc.run(result)

        # All simulations should have positive final equity
        assert mc_result.final_equity_percentiles[5] > 10000.0

    def test_all_losing_trades(self):
        """Test Monte Carlo with all losers."""
        trades = _make_trades([-100, -200, -150, -80])
        result = _make_result(trades)

        mc = MonteCarloEngine(num_simulations=100, seed=42)
        mc_result = mc.run(result)

        # All simulations should have negative final equity relative to start
        assert mc_result.final_equity_percentiles[95] < 10000.0

    def test_equity_curves_stored(self):
        """Test that worst/median/best equity curves are stored."""
        trades = _make_trades([100, -50, 200, -30, 150, -80, 50, 120])
        result = _make_result(trades)

        mc = MonteCarloEngine(num_simulations=100, seed=42)
        mc_result = mc.run(result)

        assert len(mc_result.worst_equity_curve) == 9  # 8 trades + initial
        assert len(mc_result.median_equity_curve) == 9
        assert len(mc_result.best_equity_curve) == 9

        # Worst should end lower than best
        assert mc_result.worst_equity_curve[-1] <= mc_result.best_equity_curve[-1]

    def test_max_drawdown_percentiles(self):
        """Test max drawdown percentiles are valid."""
        trades = _make_trades([100, -200, 150, -50, 200, -100])
        result = _make_result(trades)

        mc = MonteCarloEngine(num_simulations=200, seed=42)
        mc_result = mc.run(result)

        dd_pcts = mc_result.max_drawdown_percentiles
        for p in [5, 25, 50, 75, 95]:
            assert 0 <= dd_pcts[p] <= 1.0

        assert dd_pcts[5] <= dd_pcts[95]

    def test_original_values_preserved(self):
        """Test that original backtest values are preserved."""
        trades = _make_trades([100, -50])
        result = _make_result(trades)

        mc = MonteCarloEngine(num_simulations=10, seed=42)
        mc_result = mc.run(result)

        assert mc_result.original_final_equity == result.final_balance
        assert mc_result.original_max_drawdown == result.max_drawdown

    def test_to_dict(self):
        """Test to_dict produces expected structure."""
        trades = _make_trades([100, -50, 200])
        result = _make_result(trades)

        mc = MonteCarloEngine(num_simulations=50, seed=42)
        mc_result = mc.run(result)

        d = mc_result.to_dict()
        assert "simulations" in d
        assert "final_equity" in d
        assert "max_drawdown" in d
        assert "original" in d
        assert "p50" in d["final_equity"]
