# 5-Minute Quickstart Guide

Get KeryxFlow running in under 5 minutes. By the end, you'll have a paper trading bot watching crypto markets in your terminal.

---

## Prerequisites

Before you begin, make sure you have:

- **Python 3.12+** — Check with `python3 --version`
- **Poetry** — Install with `curl -sSL https://install.python-poetry.org | python3 -`
- **Git** — For cloning the repository
- **Anthropic API key** (optional) — For AI-powered analysis ([get one here](https://console.anthropic.com))

> **Note:** You do **not** need a Binance account or API keys for paper trading. KeryxFlow connects to Binance's public endpoints for live price data.

---

## Step 1: Install (1 minute)

```bash
# Clone the repository
git clone https://github.com/KeryxFlow-Project/Kerykeion.git
cd Kerykeion

# Install dependencies
poetry install

# Copy the example environment file
cp .env.example .env
```

If you have an Anthropic API key, add it to `.env`:

```bash
# Edit .env and set your key
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

Without this key, KeryxFlow runs in **technical-only mode** — it uses math-based indicators (RSI, MACD, Bollinger Bands) without AI analysis. This is perfectly fine for getting started.

---

## Step 2: Launch Paper Trading (30 seconds)

```bash
poetry run keryxflow
```

KeryxFlow starts in **paper trading mode** by default with **$10,000 virtual USDT**. No real money is ever at risk.

On first launch, you'll see the **onboarding wizard**:

```
┌─ Welcome to KeryxFlow ─────────────────────────────────────┐
│                                                            │
│  How much trading experience do you have?                  │
│                                                            │
│  [1] 🌱 I'm completely new to trading                      │
│  [2] 📊 I know the basics (buy low, sell high)             │
│  [3] 🎯 I'm an experienced trader                          │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

Pick your experience level, then choose a risk profile (conservative, balanced, or aggressive). KeryxFlow configures everything automatically based on your answers.

---

## Step 3: Navigate the TUI (1 minute)

After setup, the terminal interface launches. Here's what you'll see:

```
┌─ BTC/USDT ──────────┐  ┌─ POSITIONS ───────┐
│  Price chart + RSI   │  │  Open trades       │
├─ ORACLE ─────────────┤  ├─ AEGIS ────────────┤
│  Signals + analysis  │  │  Risk status       │
├─ LOGS ───────────────┤  ├─ AGENT ────────────┤
│  Event stream        │  │  AI session stats  │
└──────────────────────┘  └────────────────────┘
```

**Keyboard shortcuts:**

| Key | Action |
|-----|--------|
| `q` | Quit |
| `p` | **Panic** — close all positions immediately |
| `Space` | Pause / Resume trading |
| `a` | Toggle AI Agent (start/pause autonomous trading) |
| `l` | Toggle logs panel |
| `s` | Cycle through symbols (BTC/USDT, ETH/USDT, etc.) |
| `?` | Show help with term glossary |

The trading engine runs automatically: it watches prices, generates signals via technical analysis, validates them through risk checks, and executes paper trades.

---

## Step 4: Run a Backtest (1 minute)

Test a strategy on historical data before trusting it with your virtual balance:

```bash
poetry run keryxflow-backtest \
    --symbol BTC/USDT \
    --start 2024-01-01 \
    --end 2024-06-30 \
    --profile balanced
```

This downloads 6 months of BTC/USDT data from Binance (no API key needed) and simulates trades. You'll get a performance report:

```
==================================================
             BACKTEST REPORT
==================================================
  Initial Balance:    $10,000.00
  Final Balance:      $12,450.00
  Total Return:       +24.50%
  Win Rate:           62.2%
  Max Drawdown:       -8.3%
  Sharpe Ratio:       1.84
==================================================
```

**Useful flags:**
- `--timeframe 1h` — Candle timeframe (default: 1h)
- `--balance 10000` — Starting balance
- `--chart` — Show ASCII equity curve
- `--output ./reports` — Save CSV reports

---

## Step 5: Choose Your Trading Mode (1 minute)

KeryxFlow supports two analysis modes:

### Technical Mode (no API key needed)

Uses quantitative indicators only: RSI, MACD, Bollinger Bands, OBV, ATR, and EMA. Set in `settings.toml`:

```toml
[oracle]
llm_enabled = false
```

### AI-Enhanced Mode (requires Anthropic API key)

Combines technical analysis with Claude AI for market context analysis and news sentiment. This is the default when an API key is configured:

```toml
[oracle]
llm_enabled = true
llm_model = "claude-sonnet-4-20250514"
```

### Autonomous Agent Mode (advanced)

Let Claude autonomously manage the full trading cycle — perceive, analyze, decide, and execute:

```toml
[agent]
enabled = true
```

Or press `a` in the TUI to toggle the agent on/off at any time.

---

## Paper Trading Configuration

The defaults work well for most users. To customize, edit `settings.toml`:

```toml
[system]
mode = "paper"                      # Always starts as paper
symbols = ["BTC/USDT", "ETH/USDT"]  # Markets to watch

[risk]
risk_per_trade = 0.01               # Risk 1% per trade
max_daily_drawdown = 0.05           # Stop trading if down 5% today
max_open_positions = 3              # Max 3 concurrent trades

[oracle]
llm_enabled = true                  # true = AI+TA, false = TA only
analysis_interval = 300             # Seconds between analysis checks
```

Configuration priority: environment variables > `.env` > `settings.toml` > defaults.

---

## Next Steps

Now that you're up and running:

| Goal | Resource |
|------|----------|
| Understand the trading system | [Trading Guide](trading-guide.md) |
| Tune strategy parameters | [Optimization Guide](optimization.md) |
| Explore all config options | [Configuration Reference](configuration.md) |
| Learn the architecture | [Architecture Overview](architecture.md) |
| Set up live trading | [README — Live Trading](../README.md#live-trading) |
| Contribute to development | [Development Guide](development.md) |

**Remember:** Paper trade extensively before considering live trading. KeryxFlow requires at least 30 completed paper trades before live mode can be enabled.
