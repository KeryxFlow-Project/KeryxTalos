"""Onboarding wizard for first-time users."""

from dataclasses import dataclass
from typing import Any, Literal

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


@dataclass
class UserProfile:
    """User profile from onboarding."""

    experience_level: Literal["beginner", "intermediate", "advanced"]
    risk_profile: str
    show_technical: bool


class OnboardingWizard(ModalScreen[UserProfile | None]):
    """First-run onboarding wizard."""

    DEFAULT_CSS = """
    OnboardingWizard {
        align: center middle;
    }

    OnboardingWizard > Container {
        width: 65;
        height: auto;
        max-height: 90%;
        background: $surface;
        border: double $primary;
        padding: 2;
    }

    OnboardingWizard .title {
        text-style: bold;
        color: $primary-lighten-2;
        text-align: center;
        margin-bottom: 1;
    }

    OnboardingWizard .subtitle {
        color: $text-muted;
        text-align: center;
        margin-bottom: 2;
    }

    OnboardingWizard .question {
        text-style: bold;
        color: $text;
        margin-bottom: 1;
    }

    OnboardingWizard .option {
        padding: 1 2;
        margin-bottom: 1;
        background: $surface-darken-1;
        border: solid $primary;
    }

    OnboardingWizard .option:hover {
        background: $primary-darken-2;
        border: solid $accent;
    }

    OnboardingWizard .option:focus {
        background: $primary-darken-1;
        border: double $accent;
    }

    OnboardingWizard .option-key {
        text-style: bold;
        color: $accent;
    }

    OnboardingWizard .option-title {
        text-style: bold;
        color: $text;
    }

    OnboardingWizard .option-desc {
        color: $text-muted;
        margin-left: 4;
    }

    OnboardingWizard .step-indicator {
        text-align: center;
        color: $text-muted;
        margin-top: 2;
    }

    OnboardingWizard .nav-buttons {
        margin-top: 2;
    }

    OnboardingWizard .nav-buttons Button {
        width: 1fr;
        margin: 0 1;
    }

    OnboardingWizard .welcome-text {
        text-align: center;
        margin-bottom: 2;
        padding: 1;
    }

    OnboardingWizard .summary {
        padding: 1;
        background: $surface-darken-1;
        border: solid $success;
        margin-bottom: 1;
    }

    OnboardingWizard .summary-item {
        margin-bottom: 0;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("1", "select_1", "Option 1", show=False),
        Binding("2", "select_2", "Option 2", show=False),
        Binding("3", "select_3", "Option 3", show=False),
    ]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the onboarding wizard."""
        super().__init__(*args, **kwargs)
        self._step = 0
        self._experience: Literal["beginner", "intermediate", "advanced"] | None = None
        self._risk_profile: str | None = None

    def compose(self) -> ComposeResult:
        """Create the wizard content."""
        with Container(id="wizard-container"):
            yield from self._compose_step()

    def _compose_step(self) -> ComposeResult:
        """Compose current step content."""
        if self._step == 0:
            yield from self._compose_welcome()
        elif self._step == 1:
            yield from self._compose_experience()
        elif self._step == 2:
            yield from self._compose_risk()
        elif self._step == 3:
            yield from self._compose_summary()

    def _compose_welcome(self) -> ComposeResult:
        """Compose welcome screen."""
        yield Static("Welcome to KeryxFlow", classes="title")
        yield Static("Your personal trading assistant", classes="subtitle")

        yield Static(
            "KeryxFlow helps you trade smarter by combining\n"
            "technical analysis with AI-powered insights.\n\n"
            "Let's set up your profile so we can\n"
            "customize the experience for you.",
            classes="welcome-text",
        )

        yield Static(
            "[dim]This will only take a minute.[/]",
            classes="subtitle",
        )

        with Horizontal(classes="nav-buttons"):
            yield Button("Cancel", id="cancel-btn", variant="default")
            yield Button("Get Started", id="next-btn", variant="primary")

        yield Static("Step 1 of 3", classes="step-indicator")

    def _compose_experience(self) -> ComposeResult:
        """Compose experience level selection."""
        yield Static("Experience Level", classes="title")
        yield Static("How familiar are you with trading?", classes="question")

        with Vertical():
            yield Button(
                "[1] I'm completely new to trading",
                id="exp-beginner",
                classes="option",
            )
            yield Static(
                "We'll explain everything in simple terms",
                classes="option-desc",
            )

            yield Button(
                "[2] I know the basics (buy low, sell high)",
                id="exp-intermediate",
                classes="option",
            )
            yield Static(
                "We'll balance clarity with technical detail",
                classes="option-desc",
            )

            yield Button(
                "[3] I'm an experienced trader",
                id="exp-advanced",
                classes="option",
            )
            yield Static(
                "We'll show you the raw data and technical info",
                classes="option-desc",
            )

        with Horizontal(classes="nav-buttons"):
            yield Button("Back", id="back-btn", variant="default")
            yield Button("Next", id="next-btn", variant="primary", disabled=True)

        yield Static("Step 2 of 3", classes="step-indicator")

    def _compose_risk(self) -> ComposeResult:
        """Compose risk profile selection."""
        yield Static("Risk Profile", classes="title")
        yield Static("What's your comfort level with risk?", classes="question")

        with Vertical():
            yield Button(
                "[1] Safety first - I want to learn slowly",
                id="risk-conservative",
                classes="option",
            )
            yield Static(
                "Max 0.5% risk per trade, 2% daily limit",
                classes="option-desc",
            )

            yield Button(
                "[2] Balanced - moderate risk is fine",
                id="risk-balanced",
                classes="option",
            )
            yield Static(
                "Max 1% risk per trade, 5% daily limit",
                classes="option-desc",
            )

            yield Button(
                "[3] Growth - I understand the risks",
                id="risk-aggressive",
                classes="option",
            )
            yield Static(
                "Max 2% risk per trade, 10% daily limit",
                classes="option-desc",
            )

        yield Static(
            "[dim]You can change this later in settings[/]",
            classes="subtitle",
        )

        with Horizontal(classes="nav-buttons"):
            yield Button("Back", id="back-btn", variant="default")
            yield Button("Next", id="next-btn", variant="primary", disabled=True)

        yield Static("Step 3 of 3", classes="step-indicator")

    def _compose_summary(self) -> ComposeResult:
        """Compose summary screen."""
        yield Static("All Set!", classes="title")
        yield Static("Here's your profile:", classes="subtitle")

        # Experience level display
        exp_display = {
            "beginner": "Beginner - Simple explanations",
            "intermediate": "Intermediate - Balanced detail",
            "advanced": "Advanced - Full technical data",
        }

        # Risk profile display
        risk_display = {
            "conservative": "Conservative - Safety first",
            "balanced": "Balanced - Moderate risk",
            "aggressive": "Aggressive - Growth focused",
        }

        with Vertical(classes="summary"):
            yield Static(
                f"Experience: [bold]{exp_display.get(self._experience, 'Unknown')}[/]",
                classes="summary-item",
            )
            yield Static(
                f"Risk Profile: [bold]{risk_display.get(self._risk_profile, 'Unknown')}[/]",
                classes="summary-item",
            )

        yield Static(
            "You can always change these in Settings.",
            classes="subtitle",
        )

        with Horizontal(classes="nav-buttons"):
            yield Button("Back", id="back-btn", variant="default")
            yield Button("Start Trading", id="finish-btn", variant="success")

    def _refresh_step(self) -> None:
        """Refresh the current step display."""
        container = self.query_one("#wizard-container", Container)
        container.remove_children()

        for widget in self._compose_step():
            container.mount(widget)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "cancel-btn":
            self.dismiss(None)
            return

        if button_id == "back-btn":
            self._step -= 1
            self._refresh_step()
            return

        if button_id == "next-btn":
            self._step += 1
            self._refresh_step()
            return

        if button_id == "finish-btn":
            profile = UserProfile(
                experience_level=self._experience or "beginner",
                risk_profile=self._risk_profile or "conservative",
                show_technical=self._experience == "advanced",
            )
            self.dismiss(profile)
            return

        # Experience selections
        if button_id == "exp-beginner":
            self._experience = "beginner"
            self._enable_next()
        elif button_id == "exp-intermediate":
            self._experience = "intermediate"
            self._enable_next()
        elif button_id == "exp-advanced":
            self._experience = "advanced"
            self._enable_next()

        # Risk selections
        elif button_id == "risk-conservative":
            self._risk_profile = "conservative"
            self._enable_next()
        elif button_id == "risk-balanced":
            self._risk_profile = "balanced"
            self._enable_next()
        elif button_id == "risk-aggressive":
            self._risk_profile = "aggressive"
            self._enable_next()

    def _enable_next(self) -> None:
        """Enable the next button."""
        try:
            next_btn = self.query_one("#next-btn", Button)
            next_btn.disabled = False
        except Exception:
            pass

    def action_cancel(self) -> None:
        """Cancel the wizard."""
        self.dismiss(None)

    def action_select_1(self) -> None:
        """Select first option."""
        if self._step == 1:
            self._experience = "beginner"
            self._enable_next()
        elif self._step == 2:
            self._risk_profile = "conservative"
            self._enable_next()

    def action_select_2(self) -> None:
        """Select second option."""
        if self._step == 1:
            self._experience = "intermediate"
            self._enable_next()
        elif self._step == 2:
            self._risk_profile = "balanced"
            self._enable_next()

    def action_select_3(self) -> None:
        """Select third option."""
        if self._step == 1:
            self._experience = "advanced"
            self._enable_next()
        elif self._step == 2:
            self._risk_profile = "aggressive"
            self._enable_next()


class QuickSetupWizard(ModalScreen[dict[str, Any] | None]):
    """Quick setup wizard for API keys and basic settings."""

    DEFAULT_CSS = """
    QuickSetupWizard {
        align: center middle;
    }

    QuickSetupWizard > Container {
        width: 60;
        height: auto;
        background: $surface;
        border: double $primary;
        padding: 2;
    }

    QuickSetupWizard .title {
        text-style: bold;
        color: $primary-lighten-2;
        text-align: center;
        margin-bottom: 1;
    }

    QuickSetupWizard .info {
        color: $text;
        margin-bottom: 2;
        padding: 1;
        background: $surface-darken-1;
    }

    QuickSetupWizard .warning {
        color: $warning;
        margin-bottom: 1;
    }

    QuickSetupWizard .nav-buttons {
        margin-top: 2;
    }

    QuickSetupWizard .nav-buttons Button {
        width: 1fr;
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
    ]

    def compose(self) -> ComposeResult:
        """Create the setup content."""
        with Container():
            yield Static("Paper Trading Mode", classes="title")

            yield Static(
                "KeryxFlow is starting in [bold]paper trading[/] mode.\n\n"
                "This means:\n"
                "  - No real money is at risk\n"
                "  - Trades are simulated\n"
                "  - You can learn safely\n\n"
                "To connect to a real exchange later,\n"
                "add your API keys to the .env file.",
                classes="info",
            )

            yield Static(
                "Your virtual balance: $10,000 USDT",
                classes="warning",
            )

            with Horizontal(classes="nav-buttons"):
                yield Button("Continue", id="continue-btn", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "continue-btn":
            self.dismiss({"paper_mode": True})

    def action_cancel(self) -> None:
        """Cancel setup."""
        self.dismiss(None)
