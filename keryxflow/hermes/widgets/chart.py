"""Chart widget for price visualization."""

from typing import Any

from textual.app import ComposeResult
from textual.widgets import Static


class ChartWidget(Static):
    """ASCII chart widget for price display."""

    DEFAULT_CSS = """
    ChartWidget {
        height: 100%;
        border: solid $primary;
        padding: 1;
        background: $surface-darken-1;
    }

    ChartWidget .title {
        text-style: bold;
        color: $primary-lighten-2;
    }

    ChartWidget .chart-area {
        height: 1fr;
    }

    ChartWidget .indicators {
        height: 3;
        margin-top: 1;
    }

    ChartWidget .price-up {
        color: $success;
    }

    ChartWidget .price-down {
        color: $error;
    }
    """

    def __init__(
        self,
        symbol: str = "BTC/USDT",
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize the chart widget."""
        super().__init__(*args, **kwargs)
        self.symbol = symbol
        self._prices: list[float] = []
        self._current_price = 0.0
        self._price_change = 0.0
        self._indicators: dict[str, Any] = {}

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Static(f"{self.symbol}", classes="title", id="chart-title")
        yield Static("", classes="chart-area", id="chart-area")
        yield Static("", classes="indicators", id="indicators")

    def on_mount(self) -> None:
        """Called when widget is mounted."""
        self._update_display()

    async def refresh_data(self) -> None:
        """Refresh chart data from exchange."""
        # This will be connected to the exchange client
        # For now, just update display
        self._update_display()

    def update_price(self, price: float) -> None:
        """Update with new price data."""
        if self._current_price > 0:
            self._price_change = (price - self._current_price) / self._current_price

        self._current_price = price
        self._prices.append(price)

        # Keep last 60 prices for chart
        if len(self._prices) > 60:
            self._prices = self._prices[-60:]

        self._update_display()

    def update_indicators(self, indicators: dict[str, Any]) -> None:
        """Update technical indicators."""
        self._indicators = indicators
        self._update_display()

    def _update_display(self) -> None:
        """Update the display."""
        # Update title with price
        title = self.query_one("#chart-title", Static)
        if self._current_price > 0:
            change_str = f"{self._price_change:+.2%}" if self._price_change != 0 else ""
            change_class = "price-up" if self._price_change >= 0 else "price-down"
            title.update(
                f"{self.symbol}  ${self._current_price:,.2f} [{change_class}]{change_str}[/]"
            )
        else:
            title.update(f"{self.symbol}")

        # Update chart area
        chart_area = self.query_one("#chart-area", Static)
        if self._prices:
            chart = self._render_ascii_chart()
            chart_area.update(chart)
        else:
            chart_area.update("Waiting for price data...")

        # Update indicators
        indicators = self.query_one("#indicators", Static)
        if self._indicators:
            ind_str = self._render_indicators()
            indicators.update(ind_str)

    def _render_ascii_chart(self) -> str:
        """Render ASCII price chart."""
        if not self._prices:
            return ""

        # Chart dimensions
        width = 40
        height = 8

        prices = self._prices[-width:]
        if len(prices) < 2:
            return "Collecting data..."

        min_price = min(prices)
        max_price = max(prices)
        price_range = max_price - min_price

        if price_range == 0:
            price_range = 1  # Avoid division by zero

        # Create chart grid
        chart_lines = []

        for row in range(height):
            line = ""
            threshold = max_price - (row / (height - 1)) * price_range

            for price in prices:
                if price >= threshold:
                    line += "█"
                elif price >= threshold - (price_range / height / 2):
                    line += "▄"
                else:
                    line += " "

            # Add price label on first and last row
            if row == 0:
                line = f"${max_price:>10,.0f} ┤{line}"
            elif row == height - 1:
                line = f"${min_price:>10,.0f} ┼{line}"
            else:
                line = f"{'':>11} │{line}"

            chart_lines.append(line)

        return "\n".join(chart_lines)

    def _render_indicators(self) -> str:
        """Render technical indicators."""
        parts = []

        if "rsi" in self._indicators:
            rsi = self._indicators["rsi"]
            rsi_val = rsi.get("value", 50) if isinstance(rsi, dict) else rsi
            bar = self._progress_bar(rsi_val, 100, width=10)
            parts.append(f"RSI: {rsi_val:.0f} {bar}")

        if "macd" in self._indicators:
            macd = self._indicators["macd"]
            if isinstance(macd, dict):
                hist = macd.get("histogram", 0)
                arrow = "▲" if hist > 0 else "▼" if hist < 0 else "─"
                color = "green" if hist > 0 else "red" if hist < 0 else "white"
                parts.append(f"MACD: [{color}]{arrow}[/]")

        if "trend" in self._indicators:
            trend = self._indicators["trend"]
            emoji = "📈" if trend == "bullish" else "📉" if trend == "bearish" else "➡️"
            parts.append(f"Trend: {emoji}")

        return "  ".join(parts) if parts else "Indicators loading..."

    def _progress_bar(self, value: float, max_val: float, width: int = 10) -> str:
        """Render a simple progress bar."""
        filled = int((value / max_val) * width)
        empty = width - filled
        return f"[green]{'█' * filled}[/][dim]{'░' * empty}[/]"
