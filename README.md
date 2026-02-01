# KeryxFlow

A hybrid AI & quantitative trading engine for cryptocurrency markets.

KeryxFlow (from Greek *Keryx*, "The Herald" + *Flow*) is an open-source algorithmic trading system that combines quantitative mathematics with LLM-powered market context analysis.

## Philosophy

- **Math protects capital** (Aegis) - No trade executes without risk approval
- **AI finds opportunity** (Oracle) - LLM analyzes news and sentiment to validate signals
- **Terminal shows truth** (Hermes) - Real-time TUI with zero-latency visualization

## Architecture

The system operates on three layers:

```
┌─────────────────────────────────────────────────────────────┐
│                      HERMES (Interface)                      │
│              TUI Dashboard + Real-time Charts                │
├─────────────────────────────────────────────────────────────┤
│                      ORACLE (Intelligence)                   │
│         Technical Analysis + News Feeds + LLM Brain          │
├─────────────────────────────────────────────────────────────┤
│                      AEGIS (Risk & Math)                     │
│       Position Sizing + Risk Manager + Circuit Breaker       │
├─────────────────────────────────────────────────────────────┤
│                      EXCHANGE (Connectivity)                 │
│              CCXT Async Client + Paper Trading               │
└─────────────────────────────────────────────────────────────┘
```

### Hermes (Interface Layer)

Terminal User Interface built with [Textual](https://textual.textualize.io/).

- ASCII/Braille charts for price visualization
- Real-time logs with color-coded events
- Position and PnL tracking
- Panic button for emergency shutdown

### Oracle (Intelligence Layer)

Hybrid signal generation combining quantitative and cognitive analysis.

- **Technical Engine**: RSI, MACD, Bollinger Bands, OBV, ATR via pandas-ta
- **News Aggregator**: RSS feeds and news APIs for market context
- **LLM Brain**: Claude analyzes news sentiment and validates/vetoes technical signals

### Aegis (Risk Layer)

Mathematical guardian that must approve every order.

- **Position Sizing**: Dynamic lot calculation based on stop-loss distance and balance
- **Volatility Filter**: ATR-based automatic stop adjustment
- **Circuit Breaker**: Kill switch triggered by daily drawdown limit

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| Package Manager | Poetry |
| Exchange | ccxt (Binance Spot/Futures) |
| Database | SQLModel + aiosqlite |
| Analysis | numpy, pandas, pandas-ta |
| AI | LangChain + Anthropic Claude |
| Interface | Textual |
| Logging | structlog |

## Installation

### Prerequisites

- Python 3.11 or higher
- Poetry
- Binance API keys (for live/paper trading)
- Anthropic API key (for LLM features)

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/keryxflow.git
cd keryxflow

# Install dependencies
poetry install

# Copy environment template
cp .env.example .env

# Edit .env with your API keys
```

### Configuration

Edit `settings.toml` to configure trading parameters:

```toml
[risk]
model = "fixed_fractional"
risk_per_trade = 0.01          # 1% risk per trade
max_daily_drawdown = 0.05      # 5% daily loss limit (kill switch)
stop_loss_type = "atr"

[system]
exchange = "binance"
mode = "paper"                  # "paper" or "live"
symbols = ["BTC/USDT", "ETH/USDT"]

[oracle]
llm_enabled = true
news_sources = ["cryptopanic", "rss"]
analysis_interval = 300         # seconds

[database]
url = "sqlite+aiosqlite:///data/keryxflow.db"
```

## Usage

```bash
# Start the trading terminal
poetry run keryxflow

# Start in paper trading mode (default)
poetry run keryxflow --mode paper

# Start with specific symbols
poetry run keryxflow --symbols BTC/USDT,ETH/USDT
```

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `q` | Quit |
| `p` | Panic - Close all positions |
| `Space` | Pause/Resume trading |
| `l` | Toggle logs panel |
| `?` | Help |

## Project Structure

```
keryxflow/
├── pyproject.toml
├── .env.example
├── settings.toml
├── README.md
│
├── keryxflow/
│   ├── __init__.py
│   ├── main.py              # Entrypoint
│   ├── config.py            # Pydantic Settings
│   │
│   ├── core/
│   │   ├── database.py      # SQLModel + async engine
│   │   ├── events.py        # Event bus (pub/sub)
│   │   ├── models.py        # Trade, Signal, Position
│   │   └── logging.py       # Structured logging
│   │
│   ├── hermes/              # TUI
│   │   ├── app.py
│   │   ├── widgets/
│   │   └── theme.tcss
│   │
│   ├── oracle/              # Intelligence
│   │   ├── technical.py     # pandas-ta indicators
│   │   ├── feeds.py         # News aggregator
│   │   ├── brain.py         # LLM integration
│   │   └── signals.py       # Signal generator
│   │
│   ├── aegis/               # Risk
│   │   ├── quant.py         # Math engine
│   │   ├── risk.py          # Risk manager
│   │   └── circuit.py       # Circuit breaker
│   │
│   └── exchange/            # Connectivity
│       ├── client.py        # CCXT wrapper
│       ├── paper.py         # Paper trading
│       └── orders.py        # Order management
│
├── tests/
└── data/
```

## How It Works

1. **Price Feed**: Exchange client streams real-time market data
2. **Technical Analysis**: Oracle calculates indicators on incoming data
3. **Signal Generation**: When conditions align, a trading signal is created
4. **Context Validation**: LLM analyzes recent news to validate or veto the signal
5. **Risk Approval**: Aegis checks position size, drawdown, and risk parameters
6. **Execution**: If approved, order is placed (paper or live)
7. **Monitoring**: Hermes displays all activity in real-time

```
Price → Technical Analysis → Signal
                               ↓
                 News → LLM → Validation
                               ↓
                 Aegis → Approval → Execution → TUI
```

## Development

```bash
# Run tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=keryxflow

# Lint
poetry run ruff check .

# Format
poetry run ruff format .
```

## Roadmap

- [x] Project setup and documentation
- [ ] Core infrastructure (config, database, events)
- [ ] Exchange connectivity and paper trading
- [ ] Risk engine (Aegis)
- [ ] Technical analysis (Oracle)
- [ ] News feeds and LLM integration
- [ ] TUI dashboard (Hermes)
- [ ] Backtesting engine
- [ ] Live trading mode

## Disclaimer

This software is experimental. Cryptocurrency trading involves significant financial risk. Using this software does not guarantee profits. Use at your own risk.

**Never trade with money you cannot afford to lose.**

## License

MIT License - See [LICENSE](LICENSE) for details.
