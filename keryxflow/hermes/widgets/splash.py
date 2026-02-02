"""Splash screen widget."""

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Static

from keryxflow import __version__

BANNER = """\
[bold #F7931A]╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   ██╗  ██╗███████╗██████╗ ██╗   ██╗██╗  ██╗                   ║
║   ██║ ██╔╝██╔════╝██╔══██╗╚██╗ ██╔╝╚██╗██╔╝                   ║
║   █████╔╝ █████╗  ██████╔╝ ╚████╔╝  ╚███╔╝                    ║
║   ██╔═██╗ ██╔══╝  ██╔══██╗  ╚██╔╝   ██╔██╗                    ║
║   ██║  ██╗███████╗██║  ██║   ██║   ██╔╝ ██╗                   ║
║   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝  FLOW            ║
║                                                               ║
║   [white]Your keys, your trades, your code.[/white]                         ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝[/bold #F7931A]"""


class SplashScreen(ModalScreen[None]):
    """Splash screen shown on startup."""

    DEFAULT_CSS = """
    SplashScreen {
        align: center middle;
        background: $background 80%;
    }

    SplashScreen > Container {
        width: 70;
        height: auto;
        padding: 1 2;
        background: $surface;
        border: double $primary;
    }

    SplashScreen .banner {
        width: 100%;
    }

    SplashScreen .version {
        text-align: center;
        color: $text-muted;
        margin-top: 1;
    }

    SplashScreen .hint {
        text-align: center;
        color: $text-muted;
        margin-top: 1;
    }
    """

    AUTO_DISMISS_SECONDS = 2.5

    def compose(self) -> ComposeResult:
        """Create splash content."""
        with Container():
            yield Static(BANNER, classes="banner")
            yield Static(f"v{__version__}", classes="version")
            yield Static("[dim]Press any key to continue...[/dim]", classes="hint")

    def on_mount(self) -> None:
        """Start auto-dismiss timer."""
        self.set_timer(self.AUTO_DISMISS_SECONDS, self._auto_dismiss)

    def _auto_dismiss(self) -> None:
        """Auto dismiss after timeout."""
        if self.is_current:
            self.dismiss()

    def on_key(self) -> None:
        """Dismiss on any key press."""
        self.dismiss()

    def on_click(self) -> None:
        """Dismiss on click."""
        self.dismiss()
