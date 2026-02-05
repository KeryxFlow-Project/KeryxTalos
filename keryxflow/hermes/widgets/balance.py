"""Balance widget for displaying wallet balances from exchange."""

from typing import TYPE_CHECKING, Any

from textual.app import ComposeResult
from textual.widgets import DataTable, Static

from keryxflow.config import get_settings
from keryxflow.core.logging import get_logger

if TYPE_CHECKING:
    from keryxflow.exchange.client import ExchangeClient

logger = get_logger(__name__)


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
        self._paper_engine: Any = None
        self._total_usd: float = 0.0
        self._settings = get_settings()

    def set_exchange_client(self, client: "ExchangeClient") -> None:
        """Set the exchange client reference."""
        self._exchange_client = client

    def set_paper_engine(self, paper_engine: Any) -> None:
        """Set the paper engine reference for paper trading mode."""
        self._paper_engine = paper_engine

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
        # Show loading message
        table.add_row("...", "Loading", "...")
        # Schedule refresh
        self.set_timer(2.0, self._delayed_refresh)

    def _delayed_refresh(self) -> None:
        """Refresh after a delay to ensure engines are connected."""
        self.run_worker(self.refresh_data())

    async def refresh_data(self) -> None:
        """Refresh balances from paper engine or exchange."""
        from keryxflow.exchange.paper import get_paper_engine

        table = self.query_one("#balance-table", DataTable)
        
        # Ensure columns exist (handle race condition where refresh called before on_mount)
        if not table.columns:
            table.add_columns("Asset", "Amount", "≈ USD")
            table.cursor_type = "row"
            
        table.clear()

        balance_data = None
        is_live_mode = self._settings.system.mode == "live"

        # In live mode, try exchange client first
        if is_live_mode and self._exchange_client:
            try:
                logger.debug("balance_widget_fetching_live")
                if self._exchange_client.is_connected:
                    balance_data = await self._exchange_client.get_balance()
                    logger.debug("balance_widget_live_data", data=str(balance_data)[:100])
                else:
                    logger.warning("balance_widget_exchange_not_connected")
            except Exception as e:
                logger.warning("balance_widget_exchange_error", error=str(e))

        # In paper mode (or as fallback), try paper engine
        if balance_data is None:
            paper = self._paper_engine or get_paper_engine()
            if paper:
                try:
                    logger.debug("balance_widget_fetching_paper")
                    balance_data = await paper.get_balance()
                    logger.debug("balance_widget_paper_data", data=str(balance_data)[:100])
                except Exception as e:
                    logger.warning("balance_widget_paper_error", error=str(e))

        # Final fallback to exchange client if paper also failed
        if balance_data is None and self._exchange_client and not is_live_mode:
            try:
                if self._exchange_client.is_connected:
                    balance_data = await self._exchange_client.get_balance()
            except Exception as e:
                logger.warning("balance_widget_fallback_error", error=str(e))

        # Check if we have any data
        total_balances = balance_data.get("total", {}) if balance_data else {}
        has_data = any(v > 0 for v in total_balances.values())

        if balance_data and has_data:
            try:
                # Filter non-zero balances
                self._balances = {
                    currency: amount
                    for currency, amount in total_balances.items()
                    if amount > 0
                }

                # Calculate USD values (approximate)
                self._total_usd = 0.0
                rows = []

                for currency, amount in sorted(self._balances.items()):
                    usd_value = await self._get_usd_value(currency, amount)
                    self._total_usd += usd_value
                    rows.append((currency, amount, usd_value))

                # Filter rows to update
                display_rows = []
                for currency, amount, usd_value in rows:
                    if amount >= 0.00000001:
                         # Format amount nicely
                        if amount >= 1:
                            amount_str = f"{amount:,.4f}".rstrip("0").rstrip(".")
                        else:
                            amount_str = f"{amount:.8f}".rstrip("0").rstrip(".")
                        display_rows.append((currency, amount_str, f"${usd_value:,.2f}"))

                # Add rows to table
                if not display_rows:
                     table.add_row("—", "Empty balance", "—")
                else:
                    for currency, amount_str, usd_str in display_rows:
                        table.add_row(currency, amount_str, usd_str)

                # Update total
                total_line = self.query_one("#total-line", Static)
                total_line.update(f"[bold]Total: [green]${self._total_usd:,.2f}[/][/]")

            except Exception as e:
                logger.error("balance_widget_process_error", error=str(e))
                table.add_row("Error", str(e)[:30], "—")
        else:
            # Show debug info about what's missing
            mode = self._settings.system.mode
            if not balance_data:
                if not self._exchange_client and not self._paper_engine:
                    table.add_row("—", "No source", "—")
                elif mode == "live" and self._exchange_client:
                    if not self._exchange_client.is_connected:
                        table.add_row("—", "Not connected", "—")
                    else:
                        table.add_row("—", "No balance", "—")
                else:
                    table.add_row("—", "Fetching...", "—")
            else:
                # balance_data exists but is empty
                table.add_row("—", "Empty balance", "—")
                logger.debug("balance_widget_empty", raw=str(balance_data)[:200])

    async def _get_usd_value(self, currency: str, amount: float) -> float:
        """Get USD value for a currency amount."""
        if currency in ("USDT", "USDC", "BUSD", "USD"):
            return amount

        if self._exchange_client:
            try:
                # Use the main exchange client to get ticker
                symbol = f"{currency}/USDT"
                ticker = await self._exchange_client.get_ticker(symbol)
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
