"""Modal for manual order entry."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from keryxflow.core.logging import get_logger

logger = get_logger(__name__)


class OrderModal(ModalScreen[dict | None]):
    """Modal screen for entering manual orders."""

    DEFAULT_CSS = """
    OrderModal {
        align: center middle;
    }

    OrderModal > Vertical {
        width: 60;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    OrderModal .title {
        text-style: bold;
        text-align: center;
        width: 100%;
        margin-bottom: 1;
    }

    OrderModal .title-buy {
        color: $success;
    }

    OrderModal .title-sell {
        color: $error;
    }

    OrderModal .info-row {
        height: 3;
        margin-bottom: 1;
    }

    OrderModal .info-label {
        width: 15;
        text-style: bold;
    }

    OrderModal .info-value {
        width: 1fr;
        color: $primary-lighten-2;
    }

    OrderModal Input {
        width: 100%;
        margin-bottom: 1;
    }

    OrderModal .buttons {
        margin-top: 1;
        height: 3;
        align: center middle;
    }

    OrderModal Button {
        margin: 0 1;
    }

    OrderModal #confirm-buy {
        background: $success;
    }

    OrderModal #confirm-sell {
        background: $error;
    }

    OrderModal .estimate {
        text-align: center;
        margin-top: 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "confirm", "Confirm"),
    ]

    def __init__(
        self,
        symbol: str,
        side: str,  # "buy" or "sell"
        current_price: float,
        available_balance: float,
        current_position: float = 0.0,
    ) -> None:
        """Initialize the order modal."""
        super().__init__()
        self.symbol = symbol
        self.side = side
        self.current_price = current_price
        self.available_balance = available_balance
        self.current_position = current_position
        self._quantity: float = 0.0

    def compose(self) -> ComposeResult:
        """Create the modal layout."""
        title_class = "title-buy" if self.side == "buy" else "title-sell"
        side_text = "COMPRAR" if self.side == "buy" else "VENDER"

        with Vertical():
            yield Static(
                f"[bold]{side_text} {self.symbol}[/]",
                classes=f"title {title_class}",
            )

            # Price info
            with Horizontal(classes="info-row"):
                yield Static("Preço atual:", classes="info-label")
                yield Static(f"${self.current_price:,.2f}", classes="info-value")

            # Balance/Position info
            with Horizontal(classes="info-row"):
                if self.side == "buy":
                    yield Static("Saldo USDT:", classes="info-label")
                    yield Static(f"${self.available_balance:,.2f}", classes="info-value")
                else:
                    yield Static("Posição:", classes="info-label")
                    base = self.symbol.split("/")[0]
                    yield Static(f"{self.current_position:.8f} {base}", classes="info-value")

            # Quantity input
            yield Label("Quantidade:")
            yield Input(
                placeholder="Ex: 0.001",
                id="quantity-input",
                type="number",
            )

            # Estimate
            yield Static("", id="estimate", classes="estimate")

            # Buttons
            with Horizontal(classes="buttons"):
                yield Button("Cancelar", variant="default", id="cancel")
                if self.side == "buy":
                    yield Button("Comprar", variant="success", id="confirm-buy")
                else:
                    yield Button("Vender", variant="error", id="confirm-sell")

    def on_mount(self) -> None:
        """Focus the input when mounted."""
        self.query_one("#quantity-input", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Update estimate when quantity changes."""
        try:
            qty = float(event.value) if event.value else 0.0
            self._quantity = qty
            total = qty * self.current_price

            estimate = self.query_one("#estimate", Static)
            if self.side == "buy":
                estimate.update(f"Total: ${total:,.2f} USDT")
            else:
                estimate.update(f"Valor: ${total:,.2f} USDT")
        except ValueError:
            self._quantity = 0.0

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel":
            self.dismiss(None)
        elif event.button.id in ("confirm-buy", "confirm-sell"):
            self._confirm_order()

    def action_cancel(self) -> None:
        """Cancel the order."""
        self.dismiss(None)

    def action_confirm(self) -> None:
        """Confirm the order."""
        self._confirm_order()

    def _confirm_order(self) -> None:
        """Validate and confirm the order."""
        try:
            qty_input = self.query_one("#quantity-input", Input)
            qty = float(qty_input.value) if qty_input.value else 0.0

            if qty <= 0:
                self.notify("Quantidade inválida", severity="error")
                return

            # Validate balance/position
            if self.side == "buy":
                total_cost = qty * self.current_price
                if total_cost > self.available_balance:
                    self.notify("Saldo insuficiente", severity="error")
                    return
            else:
                if qty > self.current_position:
                    self.notify("Posição insuficiente", severity="error")
                    return

            # Return order data
            self.dismiss({
                "symbol": self.symbol,
                "side": self.side,
                "quantity": qty,
                "price": self.current_price,
            })

        except ValueError:
            self.notify("Quantidade inválida", severity="error")
