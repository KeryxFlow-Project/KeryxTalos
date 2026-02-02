```
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   ██╗  ██╗███████╗██████╗ ██╗   ██╗██╗  ██╗                   ║
║   ██║ ██╔╝██╔════╝██╔══██╗╚██╗ ██╔╝╚██╗██╔╝                   ║
║   █████╔╝ █████╗  ██████╔╝ ╚████╔╝  ╚███╔╝                    ║
║   ██╔═██╗ ██╔══╝  ██╔══██╗  ╚██╔╝   ██╔██╗                    ║
║   ██║  ██╗███████╗██║  ██║   ██║   ██╔╝ ██╗                   ║
║   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝  FLOW             ║
║                                                               ║
║   Your keys, your trades, your code.                          ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

![Python](https://img.shields.io/badge/Python-3.12+-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-MVP-orange)
![Binance](https://img.shields.io/badge/Exchange-Binance-yellow?logo=binance)
![Claude](https://img.shields.io/badge/AI-Claude-blueviolet)

---

An AI-powered trading assistant that helps you accumulate Bitcoin.

```
┌─ KERYXFLOW v0.8.0 ──────────────────────────────────────── BTC: $67,234.50 ─┐
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

## What is KeryxFlow?

**In simple terms:** KeryxFlow is like having a smart assistant that watches the crypto market 24/7 and trades for you, following strict rules to protect your money.

**What it does:**
- 📊 Watches cryptocurrency prices in real-time
- 🤖 Uses AI (Claude) to understand market news and sentiment
- 📈 Finds trading opportunities using math, not emotions
- 🛡️ Protects your capital with strict risk rules
- 💻 Shows everything in a beautiful terminal interface

**What it doesn't do:**
- ❌ Guarantee profits (no one can)
- ❌ Require you to understand complex trading
- ❌ Take custody of your funds (your keys stay yours)

---

## Who is this for?

### 🌱 Beginners

Never traded before? That's fine.

KeryxFlow has a **Simple Mode** that:
- Asks a few questions about your goals
- Configures everything automatically
- Uses conservative settings to protect you while you learn
- Explains what it's doing in plain language

### 🎯 Experienced Traders

Want full control? **Advanced Mode** gives you:
- Custom technical indicators
- Fine-tuned risk parameters
- Strategy customization
- Raw market data access

---

## Quick Start

### What you'll need

1. **A computer** with Python 3.12+ installed
2. **A Binance account** ([create one here](https://www.binance.com))
3. **An Anthropic API key** for Claude AI ([get one here](https://console.anthropic.com))
4. **15 minutes** to set everything up

### Installation

```bash
# Download KeryxFlow
git clone https://github.com/yourusername/keryxflow.git
cd keryxflow

# Install it
poetry install

# Set up your configuration
cp .env.example .env
```

### First Run

```bash
poetry run keryxflow
```

On first launch, KeryxFlow will guide you through setup:

```
┌─ Welcome to KeryxFlow ─────────────────────────────────────┐
│                                                            │
│  Let's set up your trading assistant.                      │
│                                                            │
│  How much trading experience do you have?                  │
│                                                            │
│  [1] 🌱 I'm completely new to trading                      │
│  [2] 📊 I know the basics (buy low, sell high)             │
│  [3] 🎯 I'm an experienced trader                          │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

Based on your answers, KeryxFlow configures itself appropriately.

---

## How it Works (Simple Explanation)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   PRICES    │────▶│   ORACLE    │────▶│    AEGIS    │────▶│   EXECUTE   │
│ Real-time   │     │ "Should we  │     │ "Is it safe │     │  "Do the    │
│   updates   │     │   trade?"   │     │  to trade?" │     │   trade"    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
  From Binance       Analyzes with       Checks your risk     Places order
  via WebSocket      TA + AI context     limits and rules     (or simulates)
```

The **TradingEngine** orchestrates this entire flow automatically:

1. **Price updates arrive** — Real-time prices from Binance are collected into OHLCV candles
2. **Oracle analyzes** — Every 60 seconds, Oracle generates signals using technical indicators
3. **Aegis validates** — Before any trade, risk limits are checked (position size, drawdown, max positions)
4. **Execute** — Approved orders execute via Paper Engine or Live Exchange

**You're always in control.** Press `P` for panic mode to close everything instantly.

---

## Concepts Explained

New to trading? Here are the terms you'll see:

| Term | What it means | Why it matters |
|------|---------------|----------------|
| **Paper Trading** | Simulated trading with fake money | Practice without risk |
| **Position** | An open trade you currently have | Shows what you own |
| **PnL** | Profit and Loss | Are you winning or losing? |
| **Stop-Loss** | Automatic sell if price drops too much | Limits your losses |
| **Drawdown** | How much you've lost from your peak | Measures bad periods |

Press `?` on any term in the interface to see its explanation.

---

## Why KeryxFlow Exists

The fiat monetary system is broken by design. Inflation erodes your savings while you sleep. Banks can freeze your accounts. Governments print money endlessly.

**Bitcoin fixes this.** But holding isn't enough for everyone. Some of us want to actively grow our stack.

KeryxFlow is a tool for sovereign individuals who want to:

- **Accumulate Bitcoin** using algorithmic trading
- **Trade on their own terms** with code they can audit
- **Leverage AI** to read market context humans might miss
- **Manage risk mathematically** because emotions destroy traders

This is not a get-rich-quick scheme. This is infrastructure for disciplined wealth building.

**Open source because trust requires transparency.**

---

## Safety First

KeryxFlow is built with safety as the top priority:

### 🛡️ Multiple Protection Layers

| Protection | What it does |
|------------|--------------|
| **Paper Mode Default** | Starts with simulated money, not real |
| **Daily Loss Limit** | Stops trading if you lose too much in a day |
| **Position Limits** | Never puts too much in one trade |
| **Panic Button** | One key to close everything immediately |
| **AI Validation** | Claude checks if news makes trading risky |

### ⚠️ Warnings

- **Start with paper trading.** Practice until you're comfortable.
- **Never invest more than you can afford to lose.**
- **Understand the risks before going live.**

---

## Configuration

### Simple Mode

Answer a few questions and KeryxFlow configures itself:

```
What's your goal?
[1] 🐢 Safety first — slow and steady (Conservative)
[2] ⚖️ Balanced — moderate risk and reward (Balanced)
[3] 🚀 Growth focused — higher risk tolerance (Aggressive)
```

### Advanced Mode

Full control via `settings.toml`:

```toml
[risk]
risk_per_trade = 0.01       # Risk 1% per trade
max_daily_drawdown = 0.05   # Stop if down 5% today
max_open_positions = 3      # Max 3 trades at once

[oracle]
llm_enabled = true
llm_model = "claude-sonnet-4-20250514"

[system]
mode = "paper"              # "paper" or "live"
symbols = ["BTC/USDT", "ETH/USDT"]
```

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `q` | Quit |
| `p` | **Panic** — close all positions immediately |
| `Space` | Pause/Resume trading |
| `l` | Toggle logs panel |
| `s` | Cycle through symbols |
| `?` | Help / explain highlighted term |

---

## Live Trading

When you're ready to trade with real money, KeryxFlow has multiple safety layers.

### Enabling Live Mode

1. **Complete at least 30 paper trades** — Practice makes perfect
2. **Configure your API keys** in `.env`:
   ```bash
   BINANCE_API_KEY=your_api_key
   BINANCE_API_SECRET=your_api_secret
   ```
3. **Set mode to live** in `settings.toml`:
   ```toml
   [system]
   mode = "live"
   ```

### Safeguards

Before enabling live trading, KeryxFlow verifies:

| Check | Requirement |
|-------|-------------|
| API Credentials | Binance API key and secret configured |
| Minimum Balance | At least 100 USDT on exchange |
| Paper History | 30+ paper trades completed |
| Risk Settings | Conservative parameters |
| Circuit Breaker | Not currently tripped |

If any check fails, live trading is blocked with a clear explanation.

### Notifications

Get alerts on your phone when trades execute:

**Telegram** — Create a bot via [@BotFather](https://t.me/botfather):
```toml
[notifications]
telegram_enabled = true
telegram_token = "your_bot_token"
telegram_chat_id = "your_chat_id"
```

**Discord** — Create a webhook in Server Settings > Integrations:
```toml
[notifications]
discord_enabled = true
discord_webhook = "https://discord.com/api/webhooks/..."
```

Notifications include: order fills, circuit breaker triggers, daily summaries, and system errors.

---

## Backtesting

Test your strategy with historical data before risking real money.

```bash
# Backtest BTC/USDT for 6 months
poetry run keryxflow-backtest \
    --symbol BTC/USDT \
    --start 2024-01-01 \
    --end 2024-06-30 \
    --timeframe 1h \
    --balance 10000 \
    --profile balanced
```

**Output:**
```
==================================================
             BACKTEST REPORT
==================================================

PERFORMANCE
--------------------------------------------------
  Initial Balance:    $10,000.00
  Final Balance:      $12,450.00
  Total Return:       +24.50%

TRADES
--------------------------------------------------
  Total Trades:       45
  Win Rate:           62.2% (28/45)
  Avg Win:            $234.50
  Avg Loss:           $98.20
  Profit Factor:      2.15
  Expectancy:         $54.44/trade

RISK
--------------------------------------------------
  Max Drawdown:       -8.3%
  Sharpe Ratio:       1.84
==================================================
```

**Options:**
- `--chart` — Show ASCII equity curve
- `--trades N` — Show last N trades
- `--output ./reports` — Save CSV files (trades + equity)
- `--data ./csv/` — Load from local CSV instead of Binance

---

## Architecture (Technical)

For developers and curious minds:

```
┌─────────────────────────────────────────────────────────────┐
│                      HERMES (Interface)                      │
│         Terminal UI • Real-time Charts • System Status       │
├─────────────────────────────────────────────────────────────┤
│                   TRADING ENGINE (Orchestrator)              │
│      OHLCV Buffer • Signal Flow • Order Execution Loop       │
├─────────────────────────────────────────────────────────────┤
│                      ORACLE (Intelligence)                   │
│    Technical Analysis • News Feeds • Claude LLM Brain        │
├─────────────────────────────────────────────────────────────┤
│                      AEGIS (Risk & Math)                     │
│    Position Sizing • Risk Manager • Circuit Breaker          │
├─────────────────────────────────────────────────────────────┤
│                      EXCHANGE (Connectivity)                 │
│     Binance API • Paper Trading • Live Safeguards            │
├─────────────────────────────────────────────────────────────┤
│                    NOTIFICATIONS (Alerts)                    │
│           Telegram • Discord • Event Subscriptions           │
├─────────────────────────────────────────────────────────────┤
│                     BACKTESTER (Validation)                  │
│     Historical Replay • Performance Metrics • Reports        │
└─────────────────────────────────────────────────────────────┘
```

### Hermes — The Interface

Terminal UI built with [Textual](https://textual.textualize.io/). Inspired by `btop` and `htop`.

### Trading Engine — The Orchestrator

Central coordinator connecting all modules in a continuous loop:

- **OHLCV Buffer**: Aggregates price updates into 1-minute candles
- **Signal Flow**: Triggers Oracle analysis at configurable intervals
- **Order Loop**: Routes signals through Aegis approval to execution

### Oracle — The Intelligence

Hybrid signal generation: quantitative math + cognitive AI.

- **Technical Engine**: RSI, MACD, Bollinger Bands, OBV, ATR
- **News Aggregator**: RSS feeds + news APIs
- **LLM Brain**: Claude validates trading signals against news context

### Aegis — The Guardian

Mathematical risk management. Every order requires Aegis approval.

- **Position Sizing**: Kelly criterion + fixed fractional
- **Volatility Adaptation**: ATR-based dynamic stops
- **Circuit Breaker**: Automatic shutdown on drawdown limits

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.12+ |
| Package Manager | Poetry |
| Exchange | ccxt (Binance) |
| Database | SQLModel + aiosqlite |
| Analysis | numpy, pandas, pandas-ta |
| AI | LangChain + Anthropic Claude |
| Interface | Textual |

---

## Project Structure

```
keryxflow/
├── keryxflow/
│   ├── main.py              # Entrypoint
│   ├── config.py            # Configuration
│   ├── core/
│   │   ├── engine.py        # TradingEngine orchestrator
│   │   ├── events.py        # Event bus (pub/sub)
│   │   ├── database.py      # SQLite persistence
│   │   ├── models.py        # Data models
│   │   ├── repository.py    # Trade persistence
│   │   └── safeguards.py    # Live trading safety checks
│   ├── hermes/              # Terminal UI (Textual)
│   ├── oracle/              # Intelligence (TA + LLM)
│   ├── aegis/               # Risk Management
│   ├── exchange/            # Binance + Paper Trading
│   ├── backtester/          # Historical testing
│   └── notifications/       # Telegram + Discord alerts
├── tests/
├── settings.toml
└── pyproject.toml
```

---

## Development

```bash
# Run tests
poetry run pytest

# Lint and format
poetry run ruff check .
poetry run ruff format .
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## Roadmap

- [x] Project structure and documentation
- [x] Core infrastructure (database, events, logging)
- [x] Exchange connectivity (Binance via CCXT)
- [x] Paper trading engine
- [x] Risk engine (Aegis) - position sizing, risk manager, circuit breaker
- [x] **Runnable MVP** - `poetry run keryxflow`
- [x] Technical analysis (Oracle) - RSI, MACD, Bollinger, OBV, ATR, EMA
- [x] News feeds - RSS, CryptoPanic integration
- [x] LLM integration (Claude) - market context analysis
- [x] Terminal UI (Hermes) - Textual-based TUI
- [x] Guided onboarding - experience & risk profile wizard
- [x] Help modal with glossary integration
- [x] Splash screen with Bitcoin orange branding
- [x] TUI integrated with main entrypoint (`poetry run keryxflow`)
- [x] **Full integration loop** - TradingEngine orchestrator (Price → Oracle → Aegis → Order)
- [x] **Backtesting engine** - `poetry run keryxflow-backtest`
- [x] **Live trading mode** - Real orders on Binance with safeguards
- [x] **Notifications** - Telegram and Discord alerts
- [ ] Parameter optimization (grid search)
- [ ] Multi-timeframe analysis

---

## FAQ

### Is this safe to use?

KeryxFlow starts in **paper trading mode** by default. No real money is used until you explicitly enable live trading.

### Do I need trading experience?

No. Simple Mode guides you through everything. But understanding what you're doing is always recommended.

### How much money do I need?

For paper trading: $0. For live trading: whatever you're comfortable potentially losing. Start small.

### Can I lose money?

**Yes.** Trading involves risk. KeryxFlow has safety features, but losses are always possible. Never trade with money you can't afford to lose.

### Is this legal?

Using trading bots is legal in most jurisdictions. Check your local laws and Binance's terms of service.

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
