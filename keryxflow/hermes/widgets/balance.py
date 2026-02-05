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
        """Refresh balances."""
        try:
            from keryxflow.exchange.paper import get_paper_engine
            table = self.query_one("#balance-table", DataTable)
            
            # Clear table
            table.clear()
            
            # 2. Fetch Data
            balance_data = None
            is_live_mode = self._settings.system.mode == "live"
            
            # (Fetching logic omitted for brevity, keeping existing flow but wrapped safely)
            if is_live_mode and self._exchange_client and self._exchange_client.is_connected:
                try:
                    balance_data = await self._exchange_client.get_balance()
                except Exception:
                    pass
            
            if not balance_data:
                paper = self._paper_engine or get_paper_engine()
                if paper:
                    balance_data = await paper.get_balance()

            if not balance_data and self._exchange_client and not is_live_mode and self._exchange_client.is_connected:
                try:
                    balance_data = await self._exchange_client.get_balance()
                except Exception:
                    pass

            # 3. Process Data
            total_balances = balance_data.get("total", {}) if balance_data else {}
            # Filter > 0
            balances = {k: v for k, v in total_balances.items() if v > 0}
            
            if not balances:
                table.add_row("—", "No Funds", "—")
                return

            # 4. Populate Table
            rows_added = 0
            self._total_usd = 0.0
            
            for currency, amount in balances.items():
                if amount < 0.00000001: continue
                
                # Get USD Value (Simplified for now)
                usd_value = 0.0
                if currency in ("USDT", "USDC", "USD"):
                    usd_value = amount
                else:
                    # Async call to get value
                    try:
                        usd_value = await self._get_usd_value(currency, amount)
                    except Exception as e:
                        logger.error(f"Error getting price for {currency}: {e}")
                        usd_value = 0.0

                self._total_usd += usd_value
                
                # Format
                formatted_amount = f"{amount:,.4f}" if amount >= 1 else f"{amount:.8f}"
                formatted_amount = formatted_amount.rstrip("0").rstrip(".")
                
                table.add_row(currency, formatted_amount, f"${usd_value:,.2f}")
                rows_added += 1

            # Update Total
            try:
                total_line = self.query_one("#total-line", Static)
                total_line.update(f"[bold]Total: [green]${self._total_usd:,.2f}[/][/]")
            except Exception:
                pass

            if rows_added == 0:
                table.add_row("—", "All dust", "—")

        except Exception as e:
            # CATCH ALL ERRORS AND SHOW IN TABLE
            try:
                table = self.query_one("#balance-table", DataTable)
                table.add_row("CRASH", str(e)[:30], "Check logs")
                self.notify(f"Balance Widget Crash: {e}", severity="error", timeout=10)
                logger.error("balance_widget_crash", error=str(e))
            except Exception:
                pass

    async def _get_usd_value(self, currency: str, amount: float) -> float:
        """Get USD value for a currency amount."""
        if currency in ("USDT", "USDC", "BUSD", "USD"):
            return amount

        if self._exchange_client and self._exchange_client.is_connected:
            try:
                # Use the main exchange client to get ticker
                symbol = f"{currency}/USDT"
                
                # Add timeout to prevent hanging, but keep it tight
                import asyncio
                try:
                    ticker = await asyncio.wait_for(
                        self._exchange_client.get_ticker(symbol), 
                        timeout=1.0 # 1s timeout
                    )
                    if ticker and ticker.get("last"):
                        return amount * ticker["last"]
                except asyncio.TimeoutError:
                    # Log but just return 0 to avoid breaking the UI
                    return 0.0
            except Exception:
                # Silently fail for individual price updates
                return 0.0

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
