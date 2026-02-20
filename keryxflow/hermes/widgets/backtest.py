"""Backtest results widget for displaying backtest metrics."""

import json
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.widgets import Static


class BacktestResultsWidget(Static):
    """Widget displaying backtest results from the most recent JSON output."""

    DEFAULT_CSS = """
    BacktestResultsWidget {
        height: 100%;
        border: solid $primary;
        padding: 1;
        background: $surface-darken-1;
    }

    BacktestResultsWidget .title {
        text-style: bold;
        color: $primary-lighten-2;
        margin-bottom: 1;
    }

    BacktestResultsWidget .metric-row {
        margin-bottom: 0;
    }

    BacktestResultsWidget .positive {
        color: $success;
    }

    BacktestResultsWidget .negative {
        color: $error;
    }

    BacktestResultsWidget .no-data {
        color: $text-muted;
        text-style: italic;
    }
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the backtest results widget."""
        super().__init__(*args, **kwargs)
        self._result: dict[str, Any] | None = None

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Static("BACKTEST RESULTS", classes="title")
        yield Static("", id="return-line", classes="metric-row")
        yield Static("", id="drawdown-line", classes="metric-row")
        yield Static("", id="winrate-line", classes="metric-row")
        yield Static("", id="trades-line", classes="metric-row")
        yield Static("", id="sharpe-line", classes="metric-row")
        yield Static("", id="profit-factor-line", classes="metric-row")

    def on_mount(self) -> None:
        """Called when widget is mounted."""
        self._load_latest_results()
        self._update_display()

    def set_result(self, result: dict[str, Any]) -> None:
        """Set backtest result data directly."""
        self._result = result
        self._update_display()

    def refresh_results(self) -> None:
        """Refresh results by re-scanning for the latest JSON file."""
        self._load_latest_results()
        self._update_display()

    def _load_latest_results(self) -> None:
        """Load the most recent results.json file from common output paths."""
        search_paths = [
            Path.cwd() / "results.json",
            Path.cwd() / "backtest_output" / "results.json",
            Path.cwd() / "output" / "results.json",
        ]

        # Also search for results.json in immediate subdirectories
        try:
            for subdir in Path.cwd().iterdir():
                if subdir.is_dir() and not subdir.name.startswith("."):
                    candidate = subdir / "results.json"
                    if candidate not in search_paths:
                        search_paths.append(candidate)
        except PermissionError:
            pass

        # Find the most recent file by modification time
        latest_file: Path | None = None
        latest_mtime: float = 0

        for path in search_paths:
            if path.exists() and path.is_file():
                mtime = path.stat().st_mtime
                if mtime > latest_mtime:
                    latest_mtime = mtime
                    latest_file = path

        if latest_file:
            try:
                with open(latest_file) as f:
                    self._result = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._result = None
        else:
            self._result = None

    def _update_display(self) -> None:
        """Update the display with current result data."""
        if self._result is None:
            self._show_no_data()
            return

        try:
            performance = self._result.get("performance", {})
            trades = self._result.get("trades", {})
            metrics = self._result.get("metrics", {})
            risk = self._result.get("risk", {})

            # Total Return
            return_line = self.query_one("#return-line", Static)
            total_return = performance.get("total_return", 0)
            return_pct = performance.get("total_return_pct", f"{total_return * 100:.2f}%")
            return_color = "green" if total_return >= 0 else "red"
            return_line.update(f"Return:        [{return_color}]{return_pct}[/]")

            # Max Drawdown
            drawdown_line = self.query_one("#drawdown-line", Static)
            max_drawdown = risk.get("max_drawdown", 0)
            drawdown_pct = risk.get("max_drawdown_pct", f"{max_drawdown * 100:.2f}%")
            drawdown_line.update(f"Max Drawdown:  [red]{drawdown_pct}[/]")

            # Win Rate
            winrate_line = self.query_one("#winrate-line", Static)
            win_rate = trades.get("win_rate", 0)
            win_rate_pct = trades.get("win_rate_pct", f"{win_rate * 100:.1f}%")
            winrate_color = "green" if win_rate >= 0.5 else "yellow"
            winrate_line.update(f"Win Rate:      [{winrate_color}]{win_rate_pct}[/]")

            # Total Trades
            trades_line = self.query_one("#trades-line", Static)
            total_trades = trades.get("total", 0)
            winning = trades.get("winning", 0)
            losing = trades.get("losing", 0)
            trades_line.update(f"Total Trades:  {total_trades} ({winning}W/{losing}L)")

            # Sharpe Ratio
            sharpe_line = self.query_one("#sharpe-line", Static)
            sharpe = risk.get("sharpe_ratio", 0)
            sharpe_color = "green" if sharpe >= 1 else ("yellow" if sharpe >= 0 else "red")
            sharpe_line.update(f"Sharpe Ratio:  [{sharpe_color}]{sharpe:.2f}[/]")

            # Profit Factor
            pf_line = self.query_one("#profit-factor-line", Static)
            profit_factor = metrics.get("profit_factor", 0)
            pf_color = (
                "green" if profit_factor >= 1.5 else ("yellow" if profit_factor >= 1 else "red")
            )
            pf_line.update(f"Profit Factor: [{pf_color}]{profit_factor:.2f}[/]")

        except Exception:
            self._show_no_data()

    def _show_no_data(self) -> None:
        """Display message when no backtest results are found."""
        return_line = self.query_one("#return-line", Static)
        return_line.update("[dim]No backtest results found.[/]")

        drawdown_line = self.query_one("#drawdown-line", Static)
        drawdown_line.update("[dim]Run: keryxflow-backtest --output ./results[/]")

        # Clear other lines
        for line_id in ["#winrate-line", "#trades-line", "#sharpe-line", "#profit-factor-line"]:
            line = self.query_one(line_id, Static)
            line.update("")
