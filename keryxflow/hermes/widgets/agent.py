"""Agent widget for displaying Cognitive Agent status."""

from typing import TYPE_CHECKING, Any

from textual.app import ComposeResult
from textual.widgets import Static

if TYPE_CHECKING:
    from keryxflow.agent.session import TradingSession


class AgentWidget(Static):
    """Widget displaying Cognitive Agent and session status."""

    DEFAULT_CSS = """
    AgentWidget {
        height: 100%;
        border: solid $primary;
        padding: 1;
        background: $surface-darken-1;
    }

    AgentWidget .title {
        text-style: bold;
        color: $primary-lighten-2;
        margin-bottom: 1;
    }

    AgentWidget .status-row {
        margin-bottom: 0;
    }

    AgentWidget .running {
        color: $success;
    }

    AgentWidget .paused {
        color: $warning;
    }

    AgentWidget .stopped {
        color: $error;
    }

    AgentWidget .idle {
        color: $text-muted;
    }
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the Agent widget."""
        super().__init__(*args, **kwargs)
        self._session: "TradingSession | None" = None
        self._status: dict[str, Any] = {}
        self._agent_enabled = False
        self._custom_label: str | None = None

    def set_session(self, session: "TradingSession") -> None:
        """Set the trading session reference."""
        self._session = session
        self._agent_enabled = True

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Static("AGENT", classes="title")
        yield Static("", id="state-line")
        yield Static("", id="cycles-line")
        yield Static("", id="trades-line")
        yield Static("", id="tools-line")
        yield Static("", id="tokens-line")

    def on_mount(self) -> None:
        """Called when widget is mounted."""
        self._update_display()

    async def refresh_data(self) -> None:
        """Refresh data from session."""
        if self._session:
            self._status = self._session.get_status()
        self._update_display()

    def set_status(self, status: dict[str, Any]) -> None:
        """Set the agent/session status."""
        self._status = status
        if self.is_mounted:
            self._update_display()

    def set_enabled(self, enabled: bool) -> None:
        """Set whether agent mode is enabled."""
        self._agent_enabled = enabled
        if self.is_mounted:
            self._update_display()

    def set_label(self, label: str) -> None:
        """Set a custom label for the state line (e.g. 'Technical Mode')."""
        self._custom_label = label
        if self.is_mounted:
            self._update_display()

    def _update_display(self) -> None:
        """Update the display."""
        # State line
        state_line = self.query_one("#state-line", Static)
        state = self._status.get("state", "idle")

        if not self._agent_enabled:
            label = self._custom_label or "DISABLED"
            state_line.update(f"[dim]Mode:       ○ {label}[/]")
        elif state == "running":
            state_line.update("[bold green]Mode:       ● RUNNING[/]")
        elif state == "paused":
            state_line.update("[bold yellow]Mode:       ◐ PAUSED[/]")
        elif state == "stopped":
            state_line.update("[bold red]Mode:       ○ STOPPED[/]")
        elif state == "error":
            state_line.update("[bold red]Mode:       ✖ ERROR[/]")
        else:
            state_line.update("[dim]Mode:       ○ IDLE[/]")

        # Cycles line
        cycles_line = self.query_one("#cycles-line", Static)
        stats = self._status.get("stats", {})
        cycles = stats.get("cycles_completed", 0)
        success = stats.get("cycles_successful", 0)
        success_pct = (success / cycles * 100) if cycles > 0 else 0

        bar = self._progress_bar(success_pct)
        cycles_line.update(f"Cycles:     {cycles} ({bar} {success_pct:.0f}%)")

        # Trades line
        trades_line = self.query_one("#trades-line", Static)
        trades = stats.get("trades_executed", 0)
        win_rate = stats.get("win_rate", 0)
        pnl = stats.get("total_pnl", 0)
        pnl_color = "green" if pnl >= 0 else "red"
        trades_line.update(
            f"Trades:     {trades} ({win_rate:.0f}% WR) [{pnl_color}]${pnl:+,.2f}[/]"
        )

        # Tools line
        tools_line = self.query_one("#tools-line", Static)
        tool_calls = stats.get("tool_calls", 0)
        cpm = stats.get("cycles_per_minute", 0)
        tools_line.update(f"Tools:      {tool_calls} calls ({cpm:.1f} cycles/min)")

        # Tokens line
        tokens_line = self.query_one("#tokens-line", Static)
        tokens = stats.get("tokens_used", 0)
        cost = stats.get("total_cost", 0.0)
        tokens_str = f"{tokens / 1000:.1f}K" if tokens > 1000 else str(tokens)
        tokens_line.update(f"Tokens:     {tokens_str} (${cost:.2f})")

    def _progress_bar(self, percentage: float, width: int = 6) -> str:
        """Render a progress bar."""
        filled = int((percentage / 100) * width)
        empty = width - filled

        if percentage >= 80:
            color = "green"
        elif percentage >= 50:
            color = "yellow"
        else:
            color = "red"

        return f"[{color}]{'█' * filled}[/][dim]{'░' * empty}[/]"

    @property
    def is_running(self) -> bool:
        """Check if agent is running."""
        return self._status.get("state") == "running"

    @property
    def is_enabled(self) -> bool:
        """Check if agent mode is enabled."""
        return self._agent_enabled

    @property
    def cycles_completed(self) -> int:
        """Get number of completed cycles."""
        stats = self._status.get("stats", {})
        return stats.get("cycles_completed", 0)
