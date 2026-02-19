"""Backtesting report and metrics."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from keryxflow.backtester.engine import BacktestTrade


@dataclass
class BacktestResult:
    """Result of a backtest run."""

    # Performance
    initial_balance: float
    final_balance: float
    total_return: float  # as decimal (0.15 = 15%)

    # Trade statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float  # as decimal

    # Trade metrics
    avg_win: float
    avg_loss: float
    expectancy: float
    profit_factor: float

    # Risk metrics
    max_drawdown: float  # as decimal
    max_drawdown_duration: int  # in periods
    sharpe_ratio: float
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0

    # Raw data
    trades: list["BacktestTrade"] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "performance": {
                "initial_balance": self.initial_balance,
                "final_balance": self.final_balance,
                "total_return": self.total_return,
                "total_return_pct": f"{self.total_return * 100:.2f}%",
            },
            "trades": {
                "total": self.total_trades,
                "winning": self.winning_trades,
                "losing": self.losing_trades,
                "win_rate": self.win_rate,
                "win_rate_pct": f"{self.win_rate * 100:.1f}%",
            },
            "metrics": {
                "avg_win": self.avg_win,
                "avg_loss": self.avg_loss,
                "expectancy": self.expectancy,
                "profit_factor": self.profit_factor,
            },
            "risk": {
                "max_drawdown": self.max_drawdown,
                "max_drawdown_pct": f"{self.max_drawdown * 100:.2f}%",
                "max_drawdown_duration": self.max_drawdown_duration,
                "sharpe_ratio": self.sharpe_ratio,
                "sortino_ratio": self.sortino_ratio,
                "calmar_ratio": self.calmar_ratio,
            },
        }


class BacktestReporter:
    """Generates reports from backtest results."""

    @staticmethod
    def print_summary(result: BacktestResult) -> str:
        """
        Generate a formatted summary report.

        Returns:
            Formatted string for terminal output
        """
        pnl = result.final_balance - result.initial_balance
        pnl_sign = "+" if pnl >= 0 else ""

        lines = [
            "",
            "=" * 50,
            "             BACKTEST REPORT",
            "=" * 50,
            "",
            "PERFORMANCE",
            "-" * 50,
            f"  Initial Balance:    ${result.initial_balance:,.2f}",
            f"  Final Balance:      ${result.final_balance:,.2f}",
            f"  Total Return:       {pnl_sign}{result.total_return * 100:.2f}%",
            f"  Net P&L:            {pnl_sign}${pnl:,.2f}",
            "",
            "TRADES",
            "-" * 50,
            f"  Total Trades:       {result.total_trades}",
            f"  Winning Trades:     {result.winning_trades}",
            f"  Losing Trades:      {result.losing_trades}",
            f"  Win Rate:           {result.win_rate * 100:.1f}%",
            "",
            "METRICS",
            "-" * 50,
            f"  Avg Win:            ${result.avg_win:,.2f}",
            f"  Avg Loss:           ${result.avg_loss:,.2f}",
            f"  Expectancy:         ${result.expectancy:,.2f}/trade",
            f"  Profit Factor:      {result.profit_factor:.2f}",
            "",
            "RISK",
            "-" * 50,
            f"  Max Drawdown:       {result.max_drawdown * 100:.2f}%",
            f"  DD Duration:        {result.max_drawdown_duration} periods",
            f"  Sharpe Ratio:       {result.sharpe_ratio:.2f}",
            f"  Sortino Ratio:      {result.sortino_ratio:.2f}",
            f"  Calmar Ratio:       {result.calmar_ratio:.2f}",
            "",
            "=" * 50,
        ]

        return "\n".join(lines)

    @staticmethod
    def save_trades_csv(result: BacktestResult, path: str | Path) -> None:
        """
        Save trades to CSV file.

        Args:
            result: Backtest result
            path: Output file path
        """
        import csv

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", newline="") as f:
            writer = csv.writer(f)

            # Header
            writer.writerow(
                [
                    "symbol",
                    "side",
                    "quantity",
                    "entry_price",
                    "entry_time",
                    "exit_price",
                    "exit_time",
                    "stop_loss",
                    "take_profit",
                    "pnl",
                    "pnl_pct",
                    "exit_reason",
                ]
            )

            # Trades
            for trade in result.trades:
                writer.writerow(
                    [
                        trade.symbol,
                        trade.side,
                        trade.quantity,
                        trade.entry_price,
                        trade.entry_time.isoformat() if trade.entry_time else "",
                        trade.exit_price,
                        trade.exit_time.isoformat() if trade.exit_time else "",
                        trade.stop_loss,
                        trade.take_profit,
                        trade.pnl,
                        trade.pnl_percentage,
                        trade.exit_reason,
                    ]
                )

    @staticmethod
    def save_equity_csv(result: BacktestResult, path: str | Path) -> None:
        """
        Save equity curve to CSV file.

        Args:
            result: Backtest result
            path: Output file path
        """
        import csv

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["period", "equity"])

            for i, equity in enumerate(result.equity_curve):
                writer.writerow([i, equity])

    @staticmethod
    def plot_equity_ascii(result: BacktestResult, width: int = 60, height: int = 15) -> str:
        """
        Generate ASCII art equity curve.

        Args:
            result: Backtest result
            width: Chart width in characters
            height: Chart height in lines

        Returns:
            ASCII chart string
        """
        if not result.equity_curve:
            return "No equity data"

        curve = result.equity_curve

        # Downsample if needed
        if len(curve) > width:
            step = len(curve) / width
            curve = [curve[int(i * step)] for i in range(width)]

        min_val = min(curve)
        max_val = max(curve)
        val_range = max_val - min_val

        if val_range == 0:
            val_range = 1

        # Build chart
        lines = []

        # Header
        lines.append(f"  ${max_val:,.0f} ┤")

        # Chart body
        for row in range(height - 2):
            threshold = max_val - (row + 1) * (val_range / (height - 1))
            line = "        │"

            for val in curve:
                if val >= threshold:
                    line += "█"
                else:
                    line += " "

            lines.append(line)

        # Footer
        lines.append(f"  ${min_val:,.0f} ┼" + "─" * len(curve))
        lines.append("        " + "└" + "─" * (len(curve) - 1) + "▶")

        return "\n".join(lines)

    @staticmethod
    def format_trade_list(result: BacktestResult, limit: int = 10) -> str:
        """
        Format recent trades as a table.

        Args:
            result: Backtest result
            limit: Maximum trades to show

        Returns:
            Formatted string
        """
        if not result.trades:
            return "No trades"

        trades = result.trades[-limit:]

        lines = [
            "",
            "RECENT TRADES",
            "-" * 70,
            f"{'Symbol':<12} {'Side':<6} {'Entry':>10} {'Exit':>10} {'PnL':>12} {'Reason':<12}",
            "-" * 70,
        ]

        for trade in trades:
            pnl_str = f"${trade.pnl:+,.2f}"

            lines.append(
                f"{trade.symbol:<12} "
                f"{trade.side.upper():<6} "
                f"${trade.entry_price:>9,.2f} "
                f"${trade.exit_price or 0:>9,.2f} "
                f"{pnl_str:>12} "
                f"{trade.exit_reason or '':<12}"
            )

        lines.append("-" * 70)

        return "\n".join(lines)
