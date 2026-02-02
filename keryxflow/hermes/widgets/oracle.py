"""Oracle widget for displaying market context and signals."""

from typing import Any

from textual.app import ComposeResult
from textual.widgets import Static


class OracleWidget(Static):
    """Widget displaying Oracle analysis and signals."""

    DEFAULT_CSS = """
    OracleWidget {
        height: 100%;
        border: solid $primary;
        padding: 1;
        background: $surface-darken-1;
    }

    OracleWidget .title {
        text-style: bold;
        color: $primary-lighten-2;
        margin-bottom: 1;
    }

    OracleWidget .context {
        margin-bottom: 1;
    }

    OracleWidget .context.bullish {
        color: $success;
    }

    OracleWidget .context.bearish {
        color: $error;
    }

    OracleWidget .context.neutral {
        color: $text;
    }

    OracleWidget .signal {
        margin-top: 1;
        padding: 1;
        border: solid $accent;
    }

    OracleWidget .confidence {
        margin-top: 1;
    }
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the Oracle widget."""
        super().__init__(*args, **kwargs)
        self._context: dict[str, Any] = {}
        self._signal: dict[str, Any] = {}
        self._news_summary: str = ""

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Static("ORACLE", classes="title")
        yield Static("Analyzing market...", classes="context", id="context")
        yield Static("", classes="signal", id="signal")
        yield Static("", classes="confidence", id="confidence")

    def update_context(self, context: dict[str, Any]) -> None:
        """Update market context."""
        self._context = context
        self._update_display()

    def update_signal(self, signal: dict[str, Any]) -> None:
        """Update latest signal."""
        self._signal = signal
        self._update_display()

    def update_news(self, summary: str) -> None:
        """Update news summary."""
        self._news_summary = summary
        self._update_display()

    def _update_display(self) -> None:
        """Update the display."""
        # Update context
        context_widget = self.query_one("#context", Static)
        if self._context:
            bias = self._context.get("bias", "neutral")
            explanation = self._context.get("simple_explanation", "")

            # Set color class based on bias
            context_widget.remove_class("bullish", "bearish", "neutral")
            if "bullish" in bias.lower():
                context_widget.add_class("bullish")
                emoji = "📈"
            elif "bearish" in bias.lower():
                context_widget.add_class("bearish")
                emoji = "📉"
            else:
                context_widget.add_class("neutral")
                emoji = "➡️"

            context_text = f"{emoji} Context: {bias.replace('_', ' ').title()}\n"
            if explanation:
                context_text += f'"{explanation}"'

            context_widget.update(context_text)
        else:
            context_widget.update("Analyzing market...")

        # Update signal
        signal_widget = self.query_one("#signal", Static)
        if self._signal:
            signal_type = self._signal.get("signal_type", "none").upper()
            symbol = self._signal.get("symbol", "")
            entry = self._signal.get("entry_price")
            confidence = self._signal.get("confidence", 0)

            if signal_type in ("LONG", "SHORT"):
                emoji = "🟢" if signal_type == "LONG" else "🔴"
                signal_text = f"{emoji} {signal_type} {symbol}"
                if entry:
                    signal_text += f" @ ${entry:,.2f}"
                signal_widget.update(signal_text)
            else:
                signal_widget.update("⏳ No active signal")
        else:
            signal_widget.update("")

        # Update confidence
        confidence_widget = self.query_one("#confidence", Static)
        if self._signal:
            confidence = self._signal.get("confidence", 0)
            strength = self._signal.get("strength", "none")

            bar = self._confidence_bar(confidence)
            confidence_widget.update(f"Confidence: {bar} {confidence:.0%} ({strength})")
        elif self._context:
            confidence = self._context.get("confidence", 0)
            bar = self._confidence_bar(confidence)
            confidence_widget.update(f"Confidence: {bar} {confidence:.0%}")
        else:
            confidence_widget.update("")

    def _confidence_bar(self, confidence: float, width: int = 10) -> str:
        """Render a confidence bar."""
        filled = int(confidence * width)
        empty = width - filled

        if confidence >= 0.7:
            color = "green"
        elif confidence >= 0.4:
            color = "yellow"
        else:
            color = "red"

        return f"[{color}]{'█' * filled}[/][dim]{'░' * empty}[/]"

    def get_context_summary(self) -> str:
        """Get a summary of the current context."""
        if not self._context:
            return "No context available"

        bias = self._context.get("bias", "unknown")
        confidence = self._context.get("confidence", 0)
        return f"{bias} ({confidence:.0%})"

    def get_signal_summary(self) -> str:
        """Get a summary of the current signal."""
        if not self._signal:
            return "No signal"

        signal_type = self._signal.get("signal_type", "none")
        symbol = self._signal.get("symbol", "")
        return f"{signal_type.upper()} {symbol}"
