"""Logs widget for displaying activity log."""

from datetime import UTC, datetime
from typing import Any

from textual.app import ComposeResult
from textual.widgets import RichLog, Static


class LogsWidget(Static):
    """Widget displaying activity log."""

    DEFAULT_CSS = """
    LogsWidget {
        height: 100%;
        border: solid $primary;
        padding: 1;
        background: $surface-darken-2;
    }

    LogsWidget .title {
        text-style: bold;
        color: $primary-lighten-2;
        margin-bottom: 1;
    }

    LogsWidget RichLog {
        height: 1fr;
        scrollbar-size: 1 1;
    }
    """

    MAX_ENTRIES = 100

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the logs widget."""
        super().__init__(*args, **kwargs)
        self._entries: list[tuple[datetime, str, str]] = []

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Static("ACTIVITY", classes="title")
        yield RichLog(id="log-output", highlight=True, markup=True)

    def add_entry(
        self,
        message: str,
        level: str = "info",
        timestamp: datetime | None = None,
    ) -> None:
        """Add a log entry."""
        if timestamp is None:
            timestamp = datetime.now(UTC)

        self._entries.append((timestamp, level, message))

        # Trim old entries
        if len(self._entries) > self.MAX_ENTRIES:
            self._entries = self._entries[-self.MAX_ENTRIES :]

        # Format and write to log
        log_output = self.query_one("#log-output", RichLog)
        formatted = self._format_entry(timestamp, level, message)
        log_output.write(formatted)

    def _format_entry(self, timestamp: datetime, level: str, message: str) -> str:
        """Format a log entry for display."""
        time_str = timestamp.strftime("%H:%M:%S")

        # Level icons
        icons = {
            "info": "ℹ",
            "success": "✓",
            "warning": "⚠",
            "error": "✗",
            "trade": "💰",
            "signal": "📊",
        }
        icon = icons.get(level, "•")

        # Level colors
        colors = {
            "info": "white",
            "success": "green",
            "warning": "yellow",
            "error": "red",
            "trade": "cyan",
            "signal": "magenta",
        }
        color = colors.get(level, "white")

        return f"[dim]{time_str}[/] [{color}]{icon}[/] {message}"

    def clear(self) -> None:
        """Clear all log entries."""
        self._entries.clear()
        log_output = self.query_one("#log-output", RichLog)
        log_output.clear()

    def get_entries(self, count: int | None = None) -> list[tuple[datetime, str, str]]:
        """Get log entries."""
        if count is None:
            return self._entries.copy()
        return self._entries[-count:]

    @property
    def entry_count(self) -> int:
        """Get number of log entries."""
        return len(self._entries)
