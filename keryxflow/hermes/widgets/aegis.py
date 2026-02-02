"""Aegis widget for displaying risk management status."""

from typing import Any

from textual.app import ComposeResult
from textual.widgets import Static


class AegisWidget(Static):
    """Widget displaying Aegis risk management status."""

    DEFAULT_CSS = """
    AegisWidget {
        height: 100%;
        border: solid $primary;
        padding: 1;
        background: $surface-darken-1;
    }

    AegisWidget .title {
        text-style: bold;
        color: $primary-lighten-2;
        margin-bottom: 1;
    }

    AegisWidget .status-row {
        margin-bottom: 0;
    }

    AegisWidget .armed {
        color: $success;
    }

    AegisWidget .tripped {
        color: $error;
        text-style: bold;
    }

    AegisWidget .warning {
        color: $warning;
    }
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the Aegis widget."""
        super().__init__(*args, **kwargs)
        self._status: dict[str, Any] = {}
        self._is_tripped = False
        self._trip_reason = ""

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Static("AEGIS", classes="title")
        yield Static("", id="status-line")
        yield Static("", id="pnl-line")
        yield Static("", id="risk-line")
        yield Static("", id="positions-line")

    def on_mount(self) -> None:
        """Called when widget is mounted."""
        self._update_display()

    async def refresh_data(self) -> None:
        """Refresh data from risk manager."""
        # This will be connected to the risk manager
        self._update_display()

    def set_status(self, status: dict[str, Any]) -> None:
        """Set the risk manager status."""
        self._status = status
        self._is_tripped = status.get("circuit_breaker_active", False)
        self._update_display()

    def set_tripped(self, reason: str) -> None:
        """Set circuit breaker as tripped."""
        self._is_tripped = True
        self._trip_reason = reason
        self._update_display()

    def set_armed(self) -> None:
        """Set circuit breaker as armed (active)."""
        self._is_tripped = False
        self._trip_reason = ""
        self._update_display()

    def _update_display(self) -> None:
        """Update the display."""
        # Status line
        status_line = self.query_one("#status-line", Static)
        if self._is_tripped:
            status_line.update("[bold red]Status:     ● TRIPPED[/]")
            if self._trip_reason:
                status_line.update(
                    f"[bold red]Status:     ● TRIPPED[/]\n[dim]{self._trip_reason}[/]"
                )
        else:
            status_line.update("[bold green]Status:     ● ARMED[/]")

        # PnL line
        pnl_line = self.query_one("#pnl-line", Static)
        daily_pnl = self._status.get("daily_pnl", 0)
        pnl_color = "green" if daily_pnl >= 0 else "red"
        pnl_line.update(f"Daily PnL:  [{pnl_color}]${daily_pnl:+,.2f}[/]")

        # Risk line
        risk_line = self.query_one("#risk-line", Static)
        daily_dd = self._status.get("daily_drawdown", 0)
        max_dd = self._status.get("max_daily_drawdown", 0.05)
        dd_pct = (daily_dd / max_dd * 100) if max_dd > 0 else 0

        bar = self._risk_bar(dd_pct)
        risk_line.update(f"Risk used:  {bar} {dd_pct:.1f}% of {max_dd:.0%} max")

        # Positions line
        positions_line = self.query_one("#positions-line", Static)
        open_pos = self._status.get("open_positions", 0)
        max_pos = self._status.get("max_positions", 3)
        positions_line.update(f"Positions:  {open_pos}/{max_pos}")

    def _risk_bar(self, percentage: float, width: int = 10) -> str:
        """Render a risk usage bar."""
        filled = int((percentage / 100) * width)
        empty = width - filled

        if percentage >= 80:
            color = "red"
        elif percentage >= 50:
            color = "yellow"
        else:
            color = "green"

        return f"[{color}]{'█' * filled}[/][dim]{'░' * empty}[/]"

    @property
    def is_tripped(self) -> bool:
        """Check if circuit breaker is tripped."""
        return self._is_tripped

    @property
    def can_trade(self) -> bool:
        """Check if trading is allowed."""
        if self._is_tripped:
            return False

        open_pos = self._status.get("open_positions", 0)
        max_pos = self._status.get("max_positions", 3)
        return open_pos < max_pos
