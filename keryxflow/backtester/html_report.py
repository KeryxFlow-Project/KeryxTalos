"""HTML report generation with embedded charts for backtesting."""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import TYPE_CHECKING

from keryxflow.core.logging import get_logger

if TYPE_CHECKING:
    from keryxflow.backtester.monte_carlo import MonteCarloResult
    from keryxflow.backtester.report import BacktestResult
    from keryxflow.backtester.walk_forward import WalkForwardResult

logger = get_logger(__name__)


def _fig_to_base64(fig) -> str:
    """Convert matplotlib figure to base64-encoded PNG string."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=100)
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("utf-8")
    buf.close()
    return encoded


class HtmlReportGenerator:
    """Generates self-contained HTML reports with embedded matplotlib charts.

    Example:
        gen = HtmlReportGenerator()
        gen.generate(
            backtest_result=result,
            output_path="report.html",
            monte_carlo_result=mc_result,
            walk_forward_result=wf_result,
        )
    """

    def generate(
        self,
        backtest_result: BacktestResult,
        output_path: str | Path,
        monte_carlo_result: MonteCarloResult | None = None,
        walk_forward_result: WalkForwardResult | None = None,
    ) -> Path:
        """Generate an HTML report.

        Args:
            backtest_result: Main backtest result
            output_path: Path for the output HTML file
            monte_carlo_result: Optional Monte Carlo simulation result
            walk_forward_result: Optional walk-forward analysis result

        Returns:
            Path to the generated HTML file
        """
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        charts: dict[str, str] = {}

        # Equity curve chart
        if backtest_result.equity_curve:
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.plot(backtest_result.equity_curve, color="#2196F3", linewidth=1.5)
            ax.set_title("Equity Curve")
            ax.set_xlabel("Period")
            ax.set_ylabel("Equity ($)")
            ax.grid(True, alpha=0.3)
            ax.axhline(y=backtest_result.initial_balance, color="gray", linestyle="--", alpha=0.5)
            charts["equity"] = _fig_to_base64(fig)
            plt.close(fig)

        # Drawdown chart
        if backtest_result.equity_curve and len(backtest_result.equity_curve) > 1:
            import numpy as np

            equity = np.array(backtest_result.equity_curve)
            peak = np.maximum.accumulate(equity)
            with np.errstate(divide="ignore", invalid="ignore"):
                dd = (peak - equity) / peak
                dd = np.nan_to_num(dd, nan=0.0)

            fig, ax = plt.subplots(figsize=(10, 3))
            ax.fill_between(range(len(dd)), dd * 100, color="#F44336", alpha=0.4)
            ax.plot(dd * 100, color="#F44336", linewidth=1)
            ax.set_title("Drawdown")
            ax.set_xlabel("Period")
            ax.set_ylabel("Drawdown (%)")
            ax.grid(True, alpha=0.3)
            ax.invert_yaxis()
            charts["drawdown"] = _fig_to_base64(fig)
            plt.close(fig)

        # Trade PnL distribution
        if backtest_result.trades:
            pnls = [t.pnl for t in backtest_result.trades]
            fig, ax = plt.subplots(figsize=(8, 4))
            colors = ["#4CAF50" if p > 0 else "#F44336" for p in pnls]
            ax.bar(range(len(pnls)), pnls, color=colors, width=1.0)
            ax.set_title("Trade PnL Distribution")
            ax.set_xlabel("Trade #")
            ax.set_ylabel("PnL ($)")
            ax.axhline(y=0, color="gray", linewidth=0.8)
            ax.grid(True, alpha=0.3)
            charts["trade_pnl"] = _fig_to_base64(fig)
            plt.close(fig)

        # Walk-forward IS vs OOS chart
        if walk_forward_result and walk_forward_result.windows:
            fig, ax = plt.subplots(figsize=(10, 4))
            window_indices = list(range(len(walk_forward_result.windows)))
            is_returns = [w.is_result.total_return * 100 for w in walk_forward_result.windows]
            oos_returns = [w.oos_result.total_return * 100 for w in walk_forward_result.windows]

            width = 0.35
            x_pos = list(range(len(window_indices)))
            ax.bar(
                [x - width / 2 for x in x_pos],
                is_returns,
                width,
                label="In-Sample",
                color="#2196F3",
                alpha=0.8,
            )
            ax.bar(
                [x + width / 2 for x in x_pos],
                oos_returns,
                width,
                label="Out-of-Sample",
                color="#FF9800",
                alpha=0.8,
            )
            ax.set_title("Walk-Forward: IS vs OOS Returns")
            ax.set_xlabel("Window")
            ax.set_ylabel("Return (%)")
            ax.set_xticks(x_pos)
            ax.set_xticklabels([f"W{i + 1}" for i in window_indices])
            ax.legend()
            ax.grid(True, alpha=0.3)
            ax.axhline(y=0, color="gray", linewidth=0.8)
            charts["wf_comparison"] = _fig_to_base64(fig)
            plt.close(fig)

            # OOS equity curve
            if walk_forward_result.oos_equity_curve:
                fig, ax = plt.subplots(figsize=(10, 4))
                ax.plot(walk_forward_result.oos_equity_curve, color="#FF9800", linewidth=1.5)
                ax.set_title("Walk-Forward: Concatenated OOS Equity")
                ax.set_xlabel("Period")
                ax.set_ylabel("Equity ($)")
                ax.grid(True, alpha=0.3)
                charts["wf_equity"] = _fig_to_base64(fig)
                plt.close(fig)

        # Monte Carlo distribution chart
        if monte_carlo_result and monte_carlo_result.num_trades > 0:
            fig, axes = plt.subplots(1, 2, figsize=(12, 4))

            # Final equity distribution
            ax1 = axes[0]
            pcts = monte_carlo_result.final_equity_percentiles
            # Draw a simple bar chart of percentiles
            labels = ["P5", "P25", "P50", "P75", "P95"]
            values = [
                pcts.get(5, 0),
                pcts.get(25, 0),
                pcts.get(50, 0),
                pcts.get(75, 0),
                pcts.get(95, 0),
            ]
            bar_colors = ["#F44336", "#FF9800", "#4CAF50", "#2196F3", "#9C27B0"]
            ax1.bar(labels, values, color=bar_colors, alpha=0.8)
            ax1.axhline(
                y=monte_carlo_result.original_final_equity,
                color="red",
                linestyle="--",
                label=f"Original: ${monte_carlo_result.original_final_equity:,.0f}",
            )
            ax1.set_title("Final Equity Distribution")
            ax1.set_ylabel("Equity ($)")
            ax1.legend(fontsize=8)
            ax1.grid(True, alpha=0.3)

            # Max drawdown distribution
            ax2 = axes[1]
            dd_pcts = monte_carlo_result.max_drawdown_percentiles
            dd_values = [
                dd_pcts.get(5, 0) * 100,
                dd_pcts.get(25, 0) * 100,
                dd_pcts.get(50, 0) * 100,
                dd_pcts.get(75, 0) * 100,
                dd_pcts.get(95, 0) * 100,
            ]
            ax2.bar(labels, dd_values, color=bar_colors, alpha=0.8)
            ax2.axhline(
                y=monte_carlo_result.original_max_drawdown * 100,
                color="red",
                linestyle="--",
                label=f"Original: {monte_carlo_result.original_max_drawdown * 100:.1f}%",
            )
            ax2.set_title("Max Drawdown Distribution")
            ax2.set_ylabel("Drawdown (%)")
            ax2.legend(fontsize=8)
            ax2.grid(True, alpha=0.3)

            fig.tight_layout()
            charts["mc_distribution"] = _fig_to_base64(fig)
            plt.close(fig)

            # MC equity curves (worst/median/best)
            if monte_carlo_result.worst_equity_curve:
                fig, ax = plt.subplots(figsize=(10, 4))
                ax.plot(
                    monte_carlo_result.worst_equity_curve,
                    color="#F44336",
                    label="Worst",
                    alpha=0.7,
                )
                ax.plot(
                    monte_carlo_result.median_equity_curve,
                    color="#4CAF50",
                    label="Median",
                    linewidth=2,
                )
                ax.plot(
                    monte_carlo_result.best_equity_curve,
                    color="#2196F3",
                    label="Best",
                    alpha=0.7,
                )
                if backtest_result.equity_curve:
                    ax.plot(
                        backtest_result.equity_curve,
                        color="black",
                        label="Original",
                        linestyle="--",
                        alpha=0.5,
                    )
                ax.set_title("Monte Carlo: Equity Scenarios")
                ax.set_xlabel("Trade #")
                ax.set_ylabel("Equity ($)")
                ax.legend()
                ax.grid(True, alpha=0.3)
                charts["mc_curves"] = _fig_to_base64(fig)
                plt.close(fig)

        # Build HTML
        html = self._build_html(backtest_result, charts, monte_carlo_result, walk_forward_result)

        output_path.write_text(html)

        logger.info("html_report_generated", path=str(output_path))
        return output_path

    def _build_html(
        self,
        result: BacktestResult,
        charts: dict[str, str],
        mc_result: MonteCarloResult | None,
        wf_result: WalkForwardResult | None,
    ) -> str:
        """Build the HTML string."""
        pnl = result.final_balance - result.initial_balance
        pnl_sign = "+" if pnl >= 0 else ""

        # Metrics table
        metrics_html = f"""
        <table class="metrics">
            <tr>
                <th colspan="2">Performance</th>
                <th colspan="2">Trades</th>
                <th colspan="2">Risk</th>
            </tr>
            <tr>
                <td>Initial Balance</td><td>${result.initial_balance:,.2f}</td>
                <td>Total Trades</td><td>{result.total_trades}</td>
                <td>Max Drawdown</td><td>{result.max_drawdown * 100:.2f}%</td>
            </tr>
            <tr>
                <td>Final Balance</td><td>${result.final_balance:,.2f}</td>
                <td>Win Rate</td><td>{result.win_rate * 100:.1f}%</td>
                <td>Sharpe Ratio</td><td>{result.sharpe_ratio:.2f}</td>
            </tr>
            <tr>
                <td>Total Return</td><td>{pnl_sign}{result.total_return * 100:.2f}%</td>
                <td>Profit Factor</td><td>{result.profit_factor:.2f}</td>
                <td>Sortino Ratio</td><td>{result.sortino_ratio:.2f}</td>
            </tr>
            <tr>
                <td>Net P&amp;L</td><td>{pnl_sign}${pnl:,.2f}</td>
                <td>Expectancy</td><td>${result.expectancy:,.2f}</td>
                <td>Calmar Ratio</td><td>{result.calmar_ratio:.2f}</td>
            </tr>
        </table>
        """

        # Chart images
        chart_sections = []
        for key, b64 in charts.items():
            chart_sections.append(
                f'<div class="chart"><img src="data:image/png;base64,{b64}" alt="{key}"></div>'
            )
        charts_html = "\n".join(chart_sections)

        # Walk-forward section
        wf_section = ""
        if wf_result and wf_result.windows:
            wf_rows = ""
            for w in wf_result.windows:
                wf_rows += f"""
                <tr>
                    <td>W{w.window_index + 1}</td>
                    <td>{w.is_result.total_return * 100:.2f}%</td>
                    <td>{w.oos_result.total_return * 100:.2f}%</td>
                    <td>{w.degradation_ratio:.2f}</td>
                    <td>{w.oos_result.total_trades}</td>
                    <td>{w.oos_result.win_rate * 100:.1f}%</td>
                </tr>
                """
            wf_section = f"""
            <h2>Walk-Forward Analysis</h2>
            <p>Windows: {wf_result.num_windows} | OOS%: {wf_result.oos_pct * 100:.0f}% |
               Avg Degradation: {wf_result.avg_degradation_ratio:.2f} |
               Aggregate OOS Return: {wf_result.aggregate_oos_return * 100:.2f}%</p>
            <table class="metrics">
                <tr>
                    <th>Window</th><th>IS Return</th><th>OOS Return</th>
                    <th>Degradation</th><th>OOS Trades</th><th>OOS Win Rate</th>
                </tr>
                {wf_rows}
            </table>
            """

        # Monte Carlo section
        mc_section = ""
        if mc_result and mc_result.num_trades > 0:
            mc_section = f"""
            <h2>Monte Carlo Simulation</h2>
            <p>Simulations: {mc_result.num_simulations} | Trades per sim: {mc_result.num_trades}</p>
            <table class="metrics">
                <tr>
                    <th></th><th>P5</th><th>P25</th><th>P50 (Median)</th><th>P75</th><th>P95</th>
                </tr>
                <tr>
                    <td>Final Equity</td>
                    <td>${mc_result.final_equity_percentiles.get(5, 0):,.0f}</td>
                    <td>${mc_result.final_equity_percentiles.get(25, 0):,.0f}</td>
                    <td>${mc_result.final_equity_percentiles.get(50, 0):,.0f}</td>
                    <td>${mc_result.final_equity_percentiles.get(75, 0):,.0f}</td>
                    <td>${mc_result.final_equity_percentiles.get(95, 0):,.0f}</td>
                </tr>
                <tr>
                    <td>Max Drawdown</td>
                    <td>{mc_result.max_drawdown_percentiles.get(5, 0) * 100:.1f}%</td>
                    <td>{mc_result.max_drawdown_percentiles.get(25, 0) * 100:.1f}%</td>
                    <td>{mc_result.max_drawdown_percentiles.get(50, 0) * 100:.1f}%</td>
                    <td>{mc_result.max_drawdown_percentiles.get(75, 0) * 100:.1f}%</td>
                    <td>{mc_result.max_drawdown_percentiles.get(95, 0) * 100:.1f}%</td>
                </tr>
                <tr>
                    <td>Total Return</td>
                    <td>{mc_result.total_return_percentiles.get(5, 0) * 100:.1f}%</td>
                    <td>{mc_result.total_return_percentiles.get(25, 0) * 100:.1f}%</td>
                    <td>{mc_result.total_return_percentiles.get(50, 0) * 100:.1f}%</td>
                    <td>{mc_result.total_return_percentiles.get(75, 0) * 100:.1f}%</td>
                    <td>{mc_result.total_return_percentiles.get(95, 0) * 100:.1f}%</td>
                </tr>
            </table>
            <p>
                95% CI Equity: ${mc_result.ci_95_equity[0]:,.0f} - ${mc_result.ci_95_equity[1]:,.0f} |
                99% CI Equity: ${mc_result.ci_99_equity[0]:,.0f} - ${mc_result.ci_99_equity[1]:,.0f}
            </p>
            """

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KeryxFlow Backtest Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #fafafa;
            color: #333;
        }}
        h1 {{
            color: #1a1a2e;
            border-bottom: 3px solid #2196F3;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #16213e;
            margin-top: 30px;
        }}
        .metrics {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
            background: white;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .metrics th {{
            background: #1a1a2e;
            color: white;
            padding: 10px 15px;
            text-align: left;
        }}
        .metrics td {{
            padding: 8px 15px;
            border-bottom: 1px solid #eee;
        }}
        .metrics tr:hover {{
            background: #f5f5f5;
        }}
        .chart {{
            margin: 20px 0;
            text-align: center;
        }}
        .chart img {{
            max-width: 100%;
            border: 1px solid #ddd;
            border-radius: 4px;
            background: white;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 10px;
            border-top: 1px solid #ddd;
            color: #999;
            font-size: 0.85em;
        }}
    </style>
</head>
<body>
    <h1>KeryxFlow Backtest Report</h1>

    <h2>Summary</h2>
    {metrics_html}

    <h2>Charts</h2>
    {charts_html}

    {wf_section}

    {mc_section}

    <div class="footer">
        Generated by KeryxFlow Backtester
    </div>
</body>
</html>"""

        return html
