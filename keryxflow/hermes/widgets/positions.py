"""Positions widget for displaying open positions."""

from typing import TYPE_CHECKING, Any

from textual.app import ComposeResult
from textual.widgets import DataTable, Static

if TYPE_CHECKING:
    from keryxflow.exchange.paper import PaperTradingEngine


class PositionsWidget(Static):
    """Widget displaying open trading positions."""

    DEFAULT_CSS = """
    PositionsWidget {
        height: 100%;
        border: solid $primary;
        padding: 1;
        background: $surface-darken-1;
    }

    PositionsWidget .title {
        text-style: bold;
        color: $primary-lighten-2;
        margin-bottom: 1;
    }

    PositionsWidget DataTable {
        height: 1fr;
    }
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the positions widget."""
        super().__init__(*args, **kwargs)
        self._positions: list[dict[str, Any]] = []
        self._paper_engine: "PaperTradingEngine | None" = None
        self._trailing_stops: dict[str, float | None] = {}

    def set_paper_engine(self, paper_engine: "PaperTradingEngine") -> None:
        """Set the paper trading engine reference."""
        self._paper_engine = paper_engine

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Static("POSITIONS", classes="title")
        yield DataTable(id="positions-table")

    def on_mount(self) -> None:
        """Called when widget is mounted."""
        table = self.query_one("#positions-table", DataTable)
        table.add_columns("Symbol", "Qty", "Entry", "Current", "PnL", "PnL%", "Trail Stop")
        table.cursor_type = "row"

    async def refresh_data(self) -> None:
        """Refresh positions from paper trading engine."""
        table = self.query_one("#positions-table", DataTable)
        table.clear()

        # Get positions from paper engine if available
        if self._paper_engine:
            positions = await self._paper_engine.get_positions()
            self._positions = [
                {
                    "symbol": pos.symbol,
                    "quantity": pos.quantity,
                    "entry_price": pos.entry_price,
                    "current_price": pos.current_price,
                    "side": pos.side.value if hasattr(pos.side, "value") else pos.side,
                    "pnl": pos.unrealized_pnl,
                    "pnl_pct": pos.unrealized_pnl_percentage,
                }
                for pos in positions
            ]

        if self._positions:
            for pos in self._positions:
                pnl = pos.get("pnl", 0)
                pnl_pct = pos.get("pnl_pct", 0)
                pnl_color = "green" if pnl >= 0 else "red"

                symbol = pos.get("symbol", "")
                trail_stop = self._trailing_stops.get(symbol)
                trail_str = f"${trail_stop:,.2f}" if trail_stop is not None else "—"

                table.add_row(
                    symbol,
                    f"{pos.get('quantity', 0):.6f}",
                    f"${pos.get('entry_price', 0):,.2f}",
                    f"${pos.get('current_price', 0):,.2f}",
                    f"[{pnl_color}]${pnl:+,.2f}[/]",
                    f"[{pnl_color}]{pnl_pct:+.2f}%[/]",
                    trail_str,
                )
        else:
            # Show empty state
            table.add_row("—", "—", "—", "—", "—", "—", "—")

    async def update_prices(self, price_data: dict[str, Any]) -> None:
        """Update position prices with new market data."""
        symbol = price_data.get("symbol")
        price = price_data.get("price", 0)

        for pos in self._positions:
            if pos.get("symbol") == symbol:
                pos["current_price"] = price
                entry = pos.get("entry_price", price)
                qty = pos.get("quantity", 0)
                side = pos.get("side", "buy")

                if side == "buy":
                    pos["pnl"] = (price - entry) * qty
                    pos["pnl_pct"] = ((price - entry) / entry * 100) if entry > 0 else 0
                else:
                    pos["pnl"] = (entry - price) * qty
                    pos["pnl_pct"] = ((entry - price) / entry * 100) if entry > 0 else 0

        await self.refresh_data()

    def set_positions(self, positions: list[dict[str, Any]]) -> None:
        """Set the positions list."""
        self._positions = positions

    def add_position(self, position: dict[str, Any]) -> None:
        """Add a new position."""
        self._positions.append(position)

    def remove_position(self, symbol: str) -> None:
        """Remove a position by symbol."""
        self._positions = [p for p in self._positions if p.get("symbol") != symbol]

    def set_trailing_stops(self, stops: dict[str, float | None]) -> None:
        """Set trailing stop prices for display.

        Args:
            stops: Mapping of symbol to trailing stop price (or None if not active)
        """
        self._trailing_stops = stops

    @property
    def total_pnl(self) -> float:
        """Calculate total PnL across all positions."""
        return sum(p.get("pnl", 0) for p in self._positions)

    @property
    def position_count(self) -> int:
        """Get number of open positions."""
        return len(self._positions)
