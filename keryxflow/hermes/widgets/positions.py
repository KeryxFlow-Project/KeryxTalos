"""Positions widget for displaying open positions."""

from typing import Any

from textual.app import ComposeResult
from textual.widgets import DataTable, Static


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

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Static("POSITIONS", classes="title")
        yield DataTable(id="positions-table")

    def on_mount(self) -> None:
        """Called when widget is mounted."""
        table = self.query_one("#positions-table", DataTable)
        table.add_columns("Symbol", "Qty", "Entry", "Current", "PnL", "PnL%")
        table.cursor_type = "row"

    async def refresh_data(self) -> None:
        """Refresh positions from paper trading engine."""
        # This will be connected to the paper trading engine
        # For now, show placeholder data
        table = self.query_one("#positions-table", DataTable)
        table.clear()

        if self._positions:
            for pos in self._positions:
                pnl = pos.get("pnl", 0)
                pnl_pct = pos.get("pnl_pct", 0)
                pnl_color = "green" if pnl >= 0 else "red"

                table.add_row(
                    pos.get("symbol", ""),
                    f"{pos.get('quantity', 0):.4f}",
                    f"${pos.get('entry_price', 0):,.2f}",
                    f"${pos.get('current_price', 0):,.2f}",
                    f"[{pnl_color}]${pnl:+,.2f}[/]",
                    f"[{pnl_color}]{pnl_pct:+.2f}%[/]",
                )
        else:
            # Show empty state
            table.add_row("No positions", "", "", "", "", "")

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

    @property
    def total_pnl(self) -> float:
        """Calculate total PnL across all positions."""
        return sum(p.get("pnl", 0) for p in self._positions)

    @property
    def position_count(self) -> int:
        """Get number of open positions."""
        return len(self._positions)
