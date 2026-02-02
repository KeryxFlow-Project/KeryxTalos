"""Stats widget for displaying trading statistics."""

from typing import Any

from textual.app import ComposeResult
from textual.widgets import Static


class StatsWidget(Static):
    """Widget displaying trading statistics."""

    DEFAULT_CSS = """
    StatsWidget {
        height: 100%;
        border: solid $primary;
        padding: 1;
        background: $surface-darken-1;
    }

    StatsWidget .title {
        text-style: bold;
        color: $primary-lighten-2;
        margin-bottom: 1;
    }

    StatsWidget .stat-row {
        margin-bottom: 0;
    }

    StatsWidget .positive {
        color: $success;
    }

    StatsWidget .negative {
        color: $error;
    }
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the stats widget."""
        super().__init__(*args, **kwargs)
        self._stats: dict[str, Any] = {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "expectancy": 0.0,
            "sharpe": 0.0,
            "total_pnl": 0.0,
        }

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Static("STATS", classes="title")
        yield Static("", id="trades-line")
        yield Static("", id="winrate-line")
        yield Static("", id="avg-line")
        yield Static("", id="expectancy-line")

    def on_mount(self) -> None:
        """Called when widget is mounted."""
        self._update_display()

    async def refresh_data(self) -> None:
        """Refresh statistics from database."""
        # This will be connected to the database
        self._update_display()

    def set_stats(self, stats: dict[str, Any]) -> None:
        """Set trading statistics."""
        self._stats.update(stats)
        self._update_display()

    def record_trade(self, pnl: float) -> None:
        """Record a new trade result."""
        self._stats["total_trades"] += 1

        if pnl >= 0:
            self._stats["wins"] += 1
            # Update average win
            total_wins = self._stats["avg_win"] * (self._stats["wins"] - 1) + pnl
            self._stats["avg_win"] = total_wins / self._stats["wins"]
        else:
            self._stats["losses"] += 1
            # Update average loss
            total_losses = self._stats["avg_loss"] * (self._stats["losses"] - 1) + abs(pnl)
            self._stats["avg_loss"] = total_losses / self._stats["losses"]

        # Update win rate
        total = self._stats["total_trades"]
        self._stats["win_rate"] = (self._stats["wins"] / total * 100) if total > 0 else 0

        # Update total PnL
        self._stats["total_pnl"] += pnl

        # Update expectancy
        self._calculate_expectancy()

        self._update_display()

    def _calculate_expectancy(self) -> None:
        """Calculate trading expectancy."""
        win_rate = self._stats["win_rate"] / 100
        avg_win = self._stats["avg_win"]
        avg_loss = self._stats["avg_loss"]

        if avg_loss > 0:
            self._stats["expectancy"] = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        else:
            self._stats["expectancy"] = win_rate * avg_win

    def _update_display(self) -> None:
        """Update the display."""
        # Trades line
        trades_line = self.query_one("#trades-line", Static)
        total = self._stats["total_trades"]
        wins = self._stats["wins"]
        trades_line.update(f"Trades:     {total} ({wins} wins)")

        # Win rate line
        winrate_line = self.query_one("#winrate-line", Static)
        win_rate = self._stats["win_rate"]
        bar = self._winrate_bar(win_rate)
        winrate_line.update(f"Win Rate:   {bar} {win_rate:.1f}%")

        # Average line
        avg_line = self.query_one("#avg-line", Static)
        avg_win = self._stats["avg_win"]
        avg_loss = self._stats["avg_loss"]
        avg_line.update(
            f"Avg Win:    [green]${avg_win:+,.2f}[/]\n" f"Avg Loss:   [red]${-avg_loss:,.2f}[/]"
        )

        # Expectancy line
        expectancy_line = self.query_one("#expectancy-line", Static)
        exp = self._stats["expectancy"]
        exp_color = "green" if exp >= 0 else "red"
        expectancy_line.update(f"Expectancy: [{exp_color}]${exp:+,.2f}/trade[/]")

    def _winrate_bar(self, percentage: float, width: int = 10) -> str:
        """Render a win rate bar."""
        filled = int((percentage / 100) * width)
        empty = width - filled

        if percentage >= 60:
            color = "green"
        elif percentage >= 45:
            color = "yellow"
        else:
            color = "red"

        return f"[{color}]{'█' * filled}[/][dim]{'░' * empty}[/]"

    @property
    def win_rate(self) -> float:
        """Get current win rate."""
        return self._stats["win_rate"]

    @property
    def expectancy(self) -> float:
        """Get current expectancy."""
        return self._stats["expectancy"]

    @property
    def total_pnl(self) -> float:
        """Get total PnL."""
        return self._stats["total_pnl"]
