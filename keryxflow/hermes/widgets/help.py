"""Help modal widget for displaying glossary terms."""

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from keryxflow import __version__
from keryxflow.core.glossary import (
    GlossaryEntry,
    get_term,
    get_terms_by_category,
    search_glossary,
)

BANNER_SMALL = """\
[bold #F7931A]██╗  ██╗███████╗██████╗ ██╗   ██╗██╗  ██╗
██║ ██╔╝██╔════╝██╔══██╗╚██╗ ██╔╝╚██╗██╔╝
█████╔╝ █████╗  ██████╔╝ ╚████╔╝  ╚███╔╝
██╔═██╗ ██╔══╝  ██╔══██╗  ╚██╔╝   ██╔██╗
██║  ██╗███████╗██║  ██║   ██║   ██╔╝ ██╗
╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝[/bold #F7931A]
[#F7931A]FLOW[/#F7931A]"""


class HelpModal(ModalScreen[None]):
    """Modal screen for displaying help and glossary."""

    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
    }

    HelpModal > Container {
        width: 60;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: double $primary;
        padding: 1 2;
    }

    HelpModal .title {
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }

    HelpModal .subtitle {
        color: $text-muted;
        text-align: center;
        margin-bottom: 1;
    }

    HelpModal Input {
        margin-bottom: 1;
    }

    HelpModal .term-name {
        text-style: bold;
        color: $accent;
        margin-top: 1;
    }

    HelpModal .simple {
        color: $text;
        margin-left: 2;
    }

    HelpModal .technical {
        color: $text-muted;
        margin-left: 2;
        text-style: italic;
    }

    HelpModal .why-matters {
        color: $success;
        margin-left: 2;
        margin-bottom: 1;
    }

    HelpModal .category-header {
        text-style: bold;
        color: $warning;
        margin-top: 1;
        border-bottom: solid $primary;
    }

    HelpModal VerticalScroll {
        height: auto;
        max-height: 20;
        margin-bottom: 1;
    }

    HelpModal Button {
        width: 100%;
    }

    HelpModal .keybindings {
        margin-top: 1;
        padding: 1;
        background: $surface-darken-1;
        border: solid $primary;
    }

    HelpModal .keybinding-row {
        margin-bottom: 0;
    }

    HelpModal .key {
        text-style: bold;
        color: $accent;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close", priority=True),
        Binding("q", "close", "Close", show=False),
    ]

    def __init__(
        self,
        term: str | None = None,
        show_detailed: bool = True,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the help modal.

        Args:
            term: Specific term to show, or None for general help
            show_detailed: Whether to show technical details
        """
        super().__init__(*args, **kwargs)
        self._term = term
        self._show_detailed = show_detailed
        self._search_results: list[GlossaryEntry] = []

    def compose(self) -> ComposeResult:
        """Create the modal content."""
        with Container():
            if self._term:
                # Show specific term
                yield from self._compose_term_view()
            else:
                # Show general help
                yield from self._compose_help_view()

    def _compose_term_view(self) -> ComposeResult:
        """Compose view for a specific term."""
        entry = get_term(self._term) if self._term else None

        yield Static("GLOSSARY", classes="title")

        if entry:
            yield Static(f"[bold]{entry.name}[/]", classes="term-name")
            yield Static(f"[dim]({entry.category})[/]", classes="subtitle")
            yield Static(f"📖 {entry.simple}", classes="simple")

            if self._show_detailed:
                yield Static(f"🔬 {entry.technical}", classes="technical")

            yield Static(f"💡 {entry.why_matters}", classes="why-matters")
        else:
            yield Static(f"Term '{self._term}' not found.", classes="simple")
            yield Static("Try searching below:", classes="subtitle")

        yield Input(placeholder="Search terms...", id="search-input")
        yield VerticalScroll(id="search-results")
        yield Button("Close [Esc]", id="close-btn", variant="primary")

    def _compose_help_view(self) -> ComposeResult:
        """Compose general help view."""
        yield Static(BANNER_SMALL, classes="title")
        yield Static(f"v{__version__} — Your keys, your trades, your code.", classes="subtitle")

        # Keybindings section
        yield Static("Keyboard Shortcuts", classes="category-header")
        with Vertical(classes="keybindings"):
            yield Static("[bold cyan]Q[/]     Quit", classes="keybinding-row")
            yield Static("[bold cyan]P[/]     Panic (emergency stop)", classes="keybinding-row")
            yield Static("[bold cyan]Space[/] Pause/Resume trading", classes="keybinding-row")
            yield Static(
                "[bold cyan]A[/]     Toggle AI Agent (start/pause)", classes="keybinding-row"
            )
            yield Static("[bold cyan]?[/]     Show this help", classes="keybinding-row")
            yield Static("[bold cyan]L[/]     Toggle logs panel", classes="keybinding-row")
            yield Static("[bold cyan]S[/]     Switch symbol", classes="keybinding-row")

        yield Static("Search Glossary", classes="category-header")
        yield Input(placeholder="Type to search terms...", id="search-input")
        yield VerticalScroll(id="search-results")

        yield Button("Close [Esc]", id="close-btn", variant="primary")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        query = event.value.strip()
        results_container = self.query_one("#search-results", VerticalScroll)

        # Clear previous results
        results_container.remove_children()

        if len(query) < 2:
            return

        # Search glossary
        results = search_glossary(query)
        self._search_results = results

        if not results:
            results_container.mount(Static("[dim]No terms found[/]", classes="simple"))
            return

        # Show results (limit to 5)
        for entry in results[:5]:
            results_container.mount(Static(f"[bold]{entry.name}[/]", classes="term-name"))
            results_container.mount(Static(f"  {entry.simple}", classes="simple"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "close-btn":
            self.dismiss()

    def action_close(self) -> None:
        """Close the modal."""
        self.dismiss()


class QuickHelpWidget(Static):
    """Small widget showing contextual help hint."""

    DEFAULT_CSS = """
    QuickHelpWidget {
        height: auto;
        padding: 0 1;
        background: $surface-darken-2;
        color: $text-muted;
    }
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the quick help widget."""
        super().__init__(*args, **kwargs)
        self._current_term: str | None = None

    def compose(self) -> ComposeResult:
        """Create the widget content."""
        yield Label("Press [bold cyan]?[/] for help", id="help-hint")

    def show_term_hint(self, term: str) -> None:
        """Show a hint for a specific term."""
        entry = get_term(term)
        if entry:
            self._current_term = term
            hint = self.query_one("#help-hint", Label)
            hint.update(f"[dim]{entry.name}:[/] {entry.simple[:40]}... [?]")

    def clear_hint(self) -> None:
        """Clear the current hint."""
        self._current_term = None
        hint = self.query_one("#help-hint", Label)
        hint.update("Press [bold cyan]?[/] for help")


class GlossaryBrowser(ModalScreen[None]):
    """Full glossary browser modal."""

    DEFAULT_CSS = """
    GlossaryBrowser {
        align: center middle;
    }

    GlossaryBrowser > Container {
        width: 80;
        height: 80%;
        background: $surface;
        border: double $primary;
        padding: 1 2;
    }

    GlossaryBrowser .title {
        text-style: bold;
        color: $primary-lighten-2;
        text-align: center;
        margin-bottom: 1;
    }

    GlossaryBrowser .category-tabs {
        height: 3;
        margin-bottom: 1;
    }

    GlossaryBrowser .category-btn {
        margin-right: 1;
    }

    GlossaryBrowser .category-btn.active {
        background: $primary;
    }

    GlossaryBrowser VerticalScroll {
        height: 1fr;
        margin-bottom: 1;
    }

    GlossaryBrowser .term-entry {
        padding: 1;
        margin-bottom: 1;
        background: $surface-darken-1;
        border: solid $primary;
    }

    GlossaryBrowser .term-name {
        text-style: bold;
        color: $accent;
    }

    GlossaryBrowser .simple {
        color: $text;
        margin-left: 2;
    }

    GlossaryBrowser .technical {
        color: $text-muted;
        margin-left: 2;
    }

    GlossaryBrowser Button {
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close", priority=True),
        Binding("1", "category_basics", "Basics", show=False),
        Binding("2", "category_indicators", "Indicators", show=False),
        Binding("3", "category_risk", "Risk", show=False),
        Binding("4", "category_orders", "Orders", show=False),
        Binding("5", "category_analysis", "Analysis", show=False),
    ]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the glossary browser."""
        super().__init__(*args, **kwargs)
        self._current_category = "basics"

    def compose(self) -> ComposeResult:
        """Create the browser content."""
        with Container():
            yield Static("GLOSSARY BROWSER", classes="title")
            yield Static(
                "[1] Basics  [2] Indicators  [3] Risk  [4] Orders  [5] Analysis",
                classes="category-tabs",
            )
            yield VerticalScroll(id="terms-list")
            yield Button("Close [Esc]", id="close-btn", variant="primary")

    def on_mount(self) -> None:
        """Load initial category."""
        self._load_category(self._current_category)

    def _load_category(self, category: str) -> None:
        """Load terms for a category."""
        self._current_category = category
        terms_list = self.query_one("#terms-list", VerticalScroll)
        terms_list.remove_children()

        entries = get_terms_by_category(category)

        for entry in entries:
            with Vertical(classes="term-entry"):
                terms_list.mount(Static(f"[bold]{entry.name}[/]", classes="term-name"))
                terms_list.mount(Static(f"📖 {entry.simple}", classes="simple"))
                terms_list.mount(Static(f"🔬 {entry.technical}", classes="technical"))

    def action_close(self) -> None:
        """Close the browser."""
        self.dismiss()

    def action_category_basics(self) -> None:
        """Switch to basics category."""
        self._load_category("basics")

    def action_category_indicators(self) -> None:
        """Switch to indicators category."""
        self._load_category("indicators")

    def action_category_risk(self) -> None:
        """Switch to risk category."""
        self._load_category("risk")

    def action_category_orders(self) -> None:
        """Switch to orders category."""
        self._load_category("orders")

    def action_category_analysis(self) -> None:
        """Switch to analysis category."""
        self._load_category("analysis")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "close-btn":
            self.dismiss()
