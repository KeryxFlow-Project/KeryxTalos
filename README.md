# KeryxFlow

### *Your keys, your trades, your code.*

A hybrid AI & quantitative trading engine for cryptocurrency markets.

```
┌─ KERYXFLOW v0.1.0 ──────────────────────────────────────── BTC: $67,234.50 ─┐
│                                                                              │
│  ┌─ BTC/USDT ─────────────────────────┐  ┌─ POSITIONS ────────────────────┐ │
│  │     ▁▂▃▅▆▇█▇▆▅▄▃▂▁▂▃▄▅▆▇█▇▆       │  │  BTC   0.052  +$234.50  +3.2%  │ │
│  │  $67,500 ┤        ╭──╮             │  │  ETH   1.205  -$45.20   -1.1%  │ │
│  │          │       ╭╯  ╰╮   ╭╮      │  │  SOL   15.00  +$89.00   +2.8%  │ │
│  │  $67,000 ┤   ╭──╯     ╰──╯ ╰╮     │  ├────────────────────────────────┤ │
│  │          │ ╭─╯               ╰─    │  │  TOTAL        +$278.30  +2.1%  │ │
│  │  $66,500 ┼─╯                       │  └────────────────────────────────┘ │
│  │          └─────────────────────────│                                     │
│  │  RSI: 58 ████████░░  MACD: ▲ bull  │  ┌─ AEGIS ────────────────────────┐ │
│  └────────────────────────────────────┘  │  Status:     ● ARMED           │ │
│                                          │  Daily PnL:  +$278.30 (+2.1%)  │ │
│  ┌─ ORACLE ───────────────────────────┐  │  Drawdown:   -0.8% of 5% max   │ │
│  │  ▶ Context: BULLISH (0.72)         │  │  Risk/Trade: 1.0%              │ │
│  │  ▶ News: ETF inflows continue...   │  │  Open:       2 of 3 max        │ │
│  │  ▶ Signal: BTC LONG @ $67,200      │  └────────────────────────────────┘ │
│  │    Confidence: 0.78 | RR: 2.4      │                                     │
│  └────────────────────────────────────┘  ┌─ STATS ────────────────────────┐ │
│                                          │  Win Rate:   62% (31/50)       │ │
│  ┌─ LOGS ─────────────────────────────────│  Avg Win:    +$156.40          │
│  │  14:32:01 [ORACLE] Signal: BTC LONG    │  Avg Loss:   -$89.20           │
│  │  14:32:02 [AEGIS]  Approved: 0.05 BTC  │  Expectancy: +$42.30/trade     │
│  │  14:32:03 [EXEC]   Filled @ $67,234    │  Sharpe:     1.84              │
│  │  14:32:15 [ORACLE] News: ETF inflows   └────────────────────────────────┘ │
│  └───────────────────────────────────────────────────────────────────────────│
│  [P]anic  [Space]Pause  [L]ogs  [Q]uit                      Stack sats. ₿   │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Why KeryxFlow Exists

The fiat monetary system is broken by design. Infinite money printing, controlled inflation, and centralized monetary policy extract wealth from those at the bottom of the pyramid and transfer it upward. Your savings lose purchasing power while you sleep.

**Bitcoin fixes this.** But holding isn't enough for everyone. Some of us want to actively grow our stack.

KeryxFlow is a tool for sovereign individuals who want to:

- **Accumulate Bitcoin** using algorithmic trading as the vehicle
- **Trade on their own terms** with code they can audit and modify
- **Leverage AI** to read market context humans might miss
- **Manage risk mathematically** because emotions destroy traders

This is not a get-rich-quick scheme. This is infrastructure for disciplined, systematic wealth building.

**Open source because trust requires transparency.**

---

## Philosophy

```
Math protects capital     →  AEGIS   →  No trade without risk approval
AI finds opportunity      →  ORACLE  →  LLM validates market context
Terminal shows truth      →  HERMES  →  Real-time visibility, zero bullshit
```

The goal is simple: **Stack sats.**

Everything else—altcoins, futures, leverage, stablecoins—is just a means to acquire more Bitcoin.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      HERMES (Interface)                      │
│         Terminal UI • Real-time Charts • System Status       │
├─────────────────────────────────────────────────────────────┤
│                      ORACLE (Intelligence)                   │
│    Technical Analysis • News Feeds • Claude LLM Brain        │
├─────────────────────────────────────────────────────────────┤
│                      AEGIS (Risk & Math)                     │
│    Position Sizing • Risk Manager • Circuit Breaker          │
├─────────────────────────────────────────────────────────────┤
│                      EXCHANGE (Connectivity)                 │
│         Binance API • Spot • Futures • Paper Trading         │
└─────────────────────────────────────────────────────────────┘
```

### Hermes — The Interface

Terminal UI built with [Textual](https://textual.textualize.io/). Inspired by `btop` and `htop`.

- ASCII charts with real-time price action
- Color-coded logs and system events
- Position tracking with live PnL
- Panic button for emergency exits
- Keyboard-driven workflow

### Oracle — The Intelligence

Hybrid signal generation: quantitative math + cognitive AI.

- **Technical Engine**: RSI, MACD, Bollinger Bands, OBV, ATR via pandas-ta
- **News Aggregator**: RSS feeds + news APIs for market context
- **LLM Brain**: Claude analyzes sentiment and validates trading signals

The AI doesn't make decisions alone. It validates or vetoes signals generated by math.

### Aegis — The Guardian

Mathematical risk management. **Every order requires Aegis approval.**

- **Position Sizing**: Kelly criterion + fixed fractional
- **Volatility Adaptation**: ATR-based dynamic stops
- **Circuit Breaker**: Automatic shutdown on drawdown limits
- **Exposure Control**: Max positions, correlation checks

Aegis exists because the market doesn't care about your feelings.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.11+ |
| Package Manager | Poetry |
| Exchange | ccxt (Binance Spot, Futures, Margin) |
| Database | SQLModel + aiosqlite |
| Analysis | numpy, pandas, pandas-ta |
| AI | LangChain + Anthropic Claude |
| Interface | Textual |
| Logging | structlog |

---

## Requirements

- Python 3.11+
- Binance account with API access
- Anthropic API key (Claude)
- Terminal with Unicode support

---

## Installation

```bash
# Clone
git clone https://github.com/yourusername/keryxflow.git
cd keryxflow

# Install dependencies
poetry install

# Configure
cp .env.example .env
# Edit .env with your API keys

# Run
poetry run keryxflow
```

---

## Configuration

### Environment Variables (`.env`)

```bash
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret
ANTHROPIC_API_KEY=your_claude_key
```

### Trading Rules (`settings.toml`)

```toml
[risk]
risk_per_trade = 0.01       # 1% per trade
max_daily_drawdown = 0.05   # 5% daily loss = kill switch
max_open_positions = 3

[oracle]
llm_enabled = true
llm_model = "claude-sonnet-4-20250514"

[system]
mode = "paper"              # Start with paper trading
symbols = ["BTC/USDT", "ETH/USDT"]
```

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `q` | Quit |
| `p` | Panic — close all positions immediately |
| `Space` | Pause/Resume trading |
| `l` | Toggle logs panel |
| `s` | Cycle through symbols |
| `?` | Help |

---

## Project Structure

```
keryxflow/
├── keryxflow/
│   ├── main.py              # Entrypoint
│   ├── config.py            # Configuration management
│   │
│   ├── core/                # Infrastructure
│   │   ├── database.py
│   │   ├── events.py
│   │   ├── models.py
│   │   └── logging.py
│   │
│   ├── hermes/              # Terminal UI
│   │   ├── app.py
│   │   ├── widgets/
│   │   └── theme.tcss
│   │
│   ├── oracle/              # Intelligence
│   │   ├── technical.py
│   │   ├── feeds.py
│   │   ├── brain.py
│   │   └── signals.py
│   │
│   ├── aegis/               # Risk Management
│   │   ├── quant.py
│   │   ├── risk.py
│   │   └── circuit.py
│   │
│   └── exchange/            # Binance Integration
│       ├── client.py
│       ├── paper.py
│       └── orders.py
│
├── tests/
├── settings.toml
└── pyproject.toml
```

---

## How It Works

```
Price Feed → Technical Analysis → Signal Generated
                                        ↓
                          News Fetch → LLM Analysis
                                        ↓
                          Signal Validated or Vetoed
                                        ↓
                          Aegis Risk Approval
                                        ↓
                          Order Execution
                                        ↓
                          Position Tracking → TUI Update
```

1. Exchange streams real-time market data
2. Oracle calculates technical indicators
3. When conditions align, a signal is generated
4. LLM analyzes recent news to validate context
5. Aegis checks risk parameters and approves/rejects
6. Order executes (paper or live)
7. Hermes displays everything in real-time

---

## Development

```bash
# Tests
poetry run pytest

# Coverage
poetry run pytest --cov=keryxflow

# Lint
poetry run ruff check .

# Format
poetry run ruff format .
```

---

## Roadmap

- [x] Project structure and documentation
- [ ] Core infrastructure (config, events, database)
- [ ] Exchange client with paper trading
- [ ] Aegis risk engine
- [ ] Oracle technical analysis
- [ ] News feeds integration
- [ ] Claude LLM brain
- [ ] Hermes TUI dashboard
- [ ] Backtesting engine
- [ ] Live trading mode
- [ ] Multi-exchange support

---

## Contributing

KeryxFlow is open source because **trust requires transparency**.

If you believe in financial sovereignty and want to contribute:

1. Fork the repository
2. Create a feature branch
3. Write clean, tested code
4. Submit a pull request

Read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## Disclaimer

This software is experimental. Cryptocurrency trading involves significant financial risk.

- Past performance does not guarantee future results
- Never trade with money you cannot afford to lose
- Paper trade extensively before going live
- The developers are not responsible for financial losses

**Use at your own risk.**

---

## License

MIT License — See [LICENSE](LICENSE)

---

<p align="center">
  <strong>Stack sats. ₿</strong>
</p>
