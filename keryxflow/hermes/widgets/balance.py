"""Balance widget for displaying wallet balances from exchange."""

from typing import TYPE_CHECKING, Any

from textual.app import ComposeResult
from textual.widgets import DataTable, Static

from keryxflow.config import get_settings

if TYPE_CHECKING:
    from keryxflow.exchange.client import ExchangeClient


class BalanceWidget(Static):
    """Widget displaying wallet balances from exchange."""

    DEFAULT_CSS = """
    BalanceWidget {
        height: 100%;
        border: solid $primary;
        padding: 1;
        background: $surface-darken-1;
    }

    BalanceWidget .title {
        text-style: bold;
        color: $primary-lighten-2;
        margin-bottom: 1;
    }

    BalanceWidget DataTable {
        height: 1fr;
    }

    BalanceWidget .total-row {
        text-style: bold;
        margin-top: 1;
    }
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the balance widget."""
        super().__init__(*args, **kwargs)
        self._balances: dict[str, float] = {}
        self._exchange_client: "ExchangeClient | None" = None
        self._total_usd: float = 0.0

    def set_exchange_client(self, client: "ExchangeClient") -> None:
        """Set the exchange client reference."""
        self._exchange_client = client

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Static("BALANCE", classes="title")
        yield DataTable(id="balance-table")
        yield Static("", id="total-line", classes="total-row")

    def on_mount(self) -> None:
        """Called when widget is mounted."""
        table = self.query_one("#balance-table", DataTable)
        table.add_columns("Asset", "Amount", "≈ USD")
        table.cursor_type = "row"

    async def refresh_data(self) -> None:
        """Refresh balances from exchange."""
        import asyncio

        table = self.query_one("#balance-table", DataTable)
        table.clear()

        if self._exchange_client:
            try:
                # Fetch balance from exchange (use thread for sync ccxt)
                settings = get_settings()

                def fetch_balance_sync():
                    import ccxt

                    config: dict[str, Any] = {"enableRateLimit": True}
                    if settings.has_binance_credentials:
                        config["apiKey"] = settings.binance_api_key.get_secret_value()
                        config["secret"] = settings.binance_api_secret.get_secret_value()

                    client = ccxt.binance(config)
                    return client.fetch_balance()

                balance = await asyncio.to_thread(fetch_balance_sync)

                # Filter non-zero balances
                self._balances = {
                    currency: amount
                    for currency, amount in balance.get("total", {}).items()
                    if amount > 0
                }

                # Calculate USD values (approximate)
                self._total_usd = 0.0
                rows = []

                for currency, amount in sorted(self._balances.items()):
                    usd_value = await self._get_usd_value(currency, amount)
                    self._total_usd += usd_value
                    rows.append((currency, amount, usd_value))

                # Add rows to table
                for currency, amount, usd_value in rows:
                    if amount >= 0.00000001:  # Filter dust
                        table.add_row(
                            currency,
                            f"{amount:.8f}".rstrip("0").rstrip("."),
                            f"${usd_value:,.2f}",
                        )

                # Update total
                total_line = self.query_one("#total-line", Static)
                total_line.update(f"[bold]Total: [green]${self._total_usd:,.2f}[/][/]")

            except Exception as e:
                table.add_row("Error", str(e)[:30], "—")
        else:
            table.add_row("—", "No exchange", "—")

    async def _get_usd_value(self, currency: str, amount: float) -> float:
        """Get USD value for a currency amount."""
        import asyncio

        if currency in ("USDT", "USDC", "BUSD", "USD"):
            return amount

        if self._exchange_client:
            try:
                # Try to get price from exchange (use thread for sync ccxt)
                symbol = f"{currency}/USDT"

                def fetch_ticker_sync():
                    import ccxt

                    client = ccxt.binance({"enableRateLimit": True})
                    return client.fetch_ticker(symbol)

                ticker = await asyncio.to_thread(fetch_ticker_sync)
                if ticker and ticker.get("last"):
                    return amount * ticker["last"]
            except Exception:
                pass

        return 0.0

    def set_balances(self, balances: dict[str, float]) -> None:
        """Set balances manually."""
        self._balances = {k: v for k, v in balances.items() if v > 0}

    @property
    def total_usd(self) -> float:
        """Get total balance in USD."""
        return self._total_usd

    @property
    def has_usdt(self) -> bool:
        """Check if user has USDT."""
        return self._balances.get("USDT", 0) > 0

    @property
    def usdt_balance(self) -> float:
        """Get USDT balance."""
        return self._balances.get("USDT", 0)
