# KeryxFlow User Guide

> **Version:** 0.13.0 | **Last updated:** February 2026

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Installation](#2-installation)
3. [Configuration](#3-configuration)
4. [Paper Trading (Getting Started)](#4-paper-trading-getting-started)
5. [TUI Navigation](#5-tui-navigation)
6. [Understanding Signals](#6-understanding-signals)
7. [Risk Management](#7-risk-management)
8. [AI Agent Mode](#8-ai-agent-mode)
9. [Backtesting](#9-backtesting)
10. [Parameter Optimization](#10-parameter-optimization)
11. [REST API & WebSocket](#11-rest-api--websocket)
12. [Notifications](#12-notifications)
13. [Multi-Exchange Support](#13-multi-exchange-support)
14. [Live Trading Checklist](#14-live-trading-checklist)
15. [Troubleshooting & FAQ](#15-troubleshooting--faq)
16. [Glossary](#16-glossary)

---

## 1. Introduction

KeryxFlow is a hybrid AI and quantitative trading engine for cryptocurrency markets. It
combines traditional technical analysis with AI-powered decision-making to help you trade
smarter, not harder.

**What KeryxFlow does:**

- **Paper trading** — Practice trading with simulated funds and real market data
- **AI-powered signals** — Technical indicators enhanced by Claude AI for smarter analysis
- **Autonomous trading** — A cognitive AI agent that can trade on your behalf
- **Backtesting** — Validate strategies against historical data before risking real money
- **Risk management** — Hardcoded safety guardrails that protect your capital at all times
- **Multi-exchange** — Trade on Binance or Bybit from a single interface
- **Real-time dashboard** — A terminal UI with live prices, signals, positions, and logs
- **Alerts** — Get notified on Discord or Telegram when trades happen

**Who is this for?**

KeryxFlow is built for crypto traders who want to augment their trading with AI and
quantitative analysis. You should be comfortable with basic trading concepts (positions,
stop losses, take profits) but you do not need to know how to code.

---

## 2. Installation

### Prerequisites

| Requirement | Version | How to check |
|-------------|---------|--------------|
| Python | 3.12 or higher | `python --version` |
| Poetry | 1.7+ | `poetry --version` |
| Git | any | `git --version` |

> **Tip:** Install Poetry via the official installer: `curl -sSL https://install.python-poetry.org | python3 -`

### Step-by-step install

```bash
# 1. Clone the repository
git clone <repository-url>
cd keryxflow

# 2. Install all dependencies
poetry install --with dev

# 3. Verify installation
poetry run keryxflow --help
```

If the last command prints usage information, your installation is working.

### Quick test

Run the test suite to make sure everything is set up correctly:

```bash
poetry run pytest
```

> **Note:** AI features (enhanced signals, agent mode) require an Anthropic API key.
> Paper trading works without any API keys — KeryxFlow will use its built-in paper
> trading engine with technical-only signals.

---

## 3. Configuration

KeryxFlow uses two configuration files:

| File | Purpose | Contains |
|------|---------|----------|
| `.env` | API keys and secrets | Exchange credentials, AI keys |
| `settings.toml` | Trading parameters | Risk limits, indicators, agent settings |

Settings priority: **Environment variables > `.env` file > `settings.toml` > Defaults**

### 3.1 API Keys (`.env`)

Create a `.env` file in the project root:

```bash
# Exchange credentials (choose one or both)
BINANCE_API_KEY=your-binance-api-key
BINANCE_API_SECRET=your-binance-api-secret

BYBIT_API_KEY=your-bybit-api-key
BYBIT_API_SECRET=your-bybit-api-secret

# AI features (optional but recommended)
ANTHROPIC_API_KEY=your-anthropic-api-key

# News sentiment (optional)
CRYPTOPANIC_API_KEY=your-cryptopanic-api-key
```

> **Warning:** Never commit your `.env` file to version control. It is already in
> `.gitignore`.

You only need credentials for the exchange you plan to use. For paper trading without
AI features, you can skip all keys entirely.

### 3.2 Trading Settings (`settings.toml`)

Create a `settings.toml` file in the project root. Here is a complete example with
all common settings:

```toml
[system]
exchange = "binance"          # "binance" or "bybit"
mode = "paper"                # "paper", "live", or "demo"
ai_mode = "disabled"          # "disabled", "enhanced", or "autonomous"
symbols = ["BTC/USDT", "ETH/USDT"]
base_currency = "USDT"
log_level = "INFO"            # "DEBUG", "INFO", "WARNING", "ERROR"

[risk]
model = "fixed_fractional"    # "fixed_fractional" or "kelly"
risk_per_trade = 0.01         # 1% of portfolio per trade
max_daily_drawdown = 0.05     # 5% max daily loss
max_open_positions = 3        # Maximum simultaneous positions
min_risk_reward = 1.5         # Minimum risk:reward ratio
stop_loss_type = "atr"        # "atr", "fixed", or "percentage"
atr_multiplier = 2.0          # ATR multiplier for stop loss distance
trailing_stop_enabled = true
trailing_stop_pct = 0.02      # 2% trailing distance
trailing_activation_pct = 0.01  # Activate after 1% profit

[oracle]
indicators = ["rsi", "macd", "bbands", "obv", "atr", "ema"]
rsi_period = 14
rsi_overbought = 70
rsi_oversold = 30
macd_fast = 12
macd_slow = 26
macd_signal = 9
bbands_period = 20
bbands_std = 2.0
ema_periods = [9, 21, 50, 200]
llm_enabled = true            # Enable AI-enhanced analysis
analysis_interval = 300       # Seconds between LLM analyses
news_enabled = true           # Enable news sentiment analysis

[agent]
enabled = false               # Enable autonomous AI agent
cycle_interval = 60           # Seconds between agent cycles
max_tool_calls_per_cycle = 20
fallback_to_technical = true  # Fall back to technical signals if AI fails
daily_token_budget = 1000000  # Max AI tokens per day (0 = unlimited)

[api]
enabled = false
host = "127.0.0.1"
port = 8080
token = ""                    # Bearer token for authentication

[notifications]
telegram_enabled = false
telegram_token = ""
telegram_chat_id = ""
discord_enabled = false
discord_webhook = ""

[live]
require_confirmation = true
min_paper_trades = 30         # Minimum paper trades before going live
min_balance = 100.0           # Minimum account balance in USDT
max_position_value = 1000.0   # Max value per position in USDT
```

### 3.3 Environment Variable Mapping

Every `settings.toml` field can be overridden with an environment variable using the
`KERYXFLOW_` prefix:

| Section | Prefix | Example |
|---------|--------|---------|
| `[system]` | `KERYXFLOW_` | `KERYXFLOW_MODE=paper` |
| `[risk]` | `KERYXFLOW_RISK_` | `KERYXFLOW_RISK_MAX_OPEN_POSITIONS=5` |
| `[oracle]` | `KERYXFLOW_ORACLE_` | `KERYXFLOW_ORACLE_RSI_PERIOD=21` |
| `[agent]` | `KERYXFLOW_AGENT_` | `KERYXFLOW_AGENT_ENABLED=true` |
| `[api]` | `KERYXFLOW_API_` | `KERYXFLOW_API_PORT=9000` |
| `[notifications]` | `KERYXFLOW_NOTIFY_` | `KERYXFLOW_NOTIFY_DISCORD_ENABLED=true` |
| `[live]` | `KERYXFLOW_LIVE_` | `KERYXFLOW_LIVE_MIN_BALANCE=500` |

### 3.4 AI Mode Explained

The `ai_mode` setting is the primary knob for controlling AI features:

| Mode | What happens |
|------|-------------|
| `disabled` | Technical indicators only. No AI calls. Free to run. |
| `enhanced` | Technical indicators + AI analysis. LLM reviews signals and adds context. Uses API tokens. |
| `autonomous` | Full AI agent. Perceives markets, remembers past trades, decides and executes. Uses the most tokens. |

---

## 4. Paper Trading (Getting Started)

Paper trading lets you practice with simulated funds and real market data. No API keys
are required for basic paper trading.

### Starting the dashboard

```bash
poetry run keryxflow
```

This launches the terminal UI (TUI) in paper mode by default. You will see:

- **Price panel** — Live price data and mini chart for the active symbol
- **Signals panel** — Current trading signals with confidence levels
- **Positions panel** — Open paper positions with unrealized P&L
- **Trades panel** — Recent trade history
- **Status bar** — Current mode, symbol, exchange, and session state

### Your first session

1. Launch KeryxFlow with `poetry run keryxflow`
2. Watch the price panel update with real market data
3. Observe signals as they appear (BUY/SELL/HOLD with confidence)
4. Press `?` to view the help screen at any time
5. Press `q` to quit when done

Paper trades are executed automatically when signals meet your configured risk criteria.
All positions use simulated funds — no real money is at risk.

### Switching symbols

Press `s` to cycle through your configured symbols. The default symbols are
`BTC/USDT` and `ETH/USDT`. Add more in `settings.toml`:

```toml
[system]
symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
```

---

## 5. TUI Navigation

The terminal UI uses keyboard shortcuts for all actions. There is no mouse input.

### Keyboard shortcuts

| Key | Action | Description |
|-----|--------|-------------|
| `q` | Quit | Exit KeryxFlow immediately |
| `p` | Panic | Emergency stop — closes all positions immediately |
| `Space` | Pause / Resume | Pause or resume signal processing and trading |
| `a` | Toggle Agent | Start, pause, or resume the AI agent (requires `ai_mode` not `disabled`) |
| `b` | Backtest | Toggle the backtest results panel |
| `?` | Help | Show the help screen with all shortcuts |
| `l` | Toggle Logs | Show or hide the log panel |
| `s` | Next Symbol | Cycle to the next symbol in your list |

### Panic mode

Pressing `p` triggers an emergency stop:

- All open positions are closed immediately at market price
- All pending orders are cancelled
- Trading is halted until you restart

Use this if you see unexpected market movement and want to exit everything fast.

### TUI themes

KeryxFlow supports two themes:

```toml
[hermes]
theme = "cyberpunk"    # Default neon theme
# theme = "minimal"   # Clean, minimal theme
```

You can also adjust the refresh rate, chart size, and log buffer:

```toml
[hermes]
refresh_rate = 1.0     # Seconds between UI updates
chart_width = 60       # Character width of price chart
chart_height = 15      # Character height of price chart
max_log_lines = 100    # Maximum log lines to display
```

---

## 6. Understanding Signals

KeryxFlow generates trading signals by combining multiple technical indicators. When
`ai_mode` is set to `enhanced` or `autonomous`, AI analysis is layered on top.

### Technical indicators

KeryxFlow uses six indicators by default:

| Indicator | What it measures | Key parameters |
|-----------|-----------------|----------------|
| **RSI** (Relative Strength Index) | Overbought/oversold momentum | Period: 14, Overbought: 70, Oversold: 30 |
| **MACD** (Moving Average Convergence Divergence) | Trend direction and momentum | Fast: 12, Slow: 26, Signal: 9 |
| **Bollinger Bands** | Volatility and price extremes | Period: 20, Std Dev: 2.0 |
| **OBV** (On-Balance Volume) | Volume-confirmed price moves | EMA smoothing: 20 periods |
| **ATR** (Average True Range) | Volatility for stop placement | Period: 14 |
| **EMA** (Exponential Moving Average) | Trend alignment across timeframes | Periods: 9, 21, 50, 200 |

### How signals are generated

Each indicator produces a direction (bullish, bearish, or neutral) and a strength:

| Strength | Weight | Meaning |
|----------|--------|---------|
| Strong | 3 | High-confidence directional signal |
| Moderate | 2 | Directional lean with some uncertainty |
| Weak | 1 | Slight lean, low significance |
| None | 0 | No meaningful signal |

Indicators are combined into an aggregate confidence score (0.0 to 1.0):

| Confidence | Strength label | Action |
|------------|---------------|--------|
| Above 0.7 | Strong | Signal generated (LONG or SHORT) |
| 0.5 to 0.7 | Moderate | Signal generated (LONG or SHORT) |
| 0.3 to 0.5 | Weak | No trade signal |
| Below 0.3 | None | No trade signal |

Only **Strong** and **Moderate** signals trigger trade entries. Weak and None result in
HOLD (no action).

### AI-enhanced signals

When `ai_mode` is `enhanced`, KeryxFlow sends market data to Claude for analysis. The
final confidence is a weighted blend:

```
Final confidence = (Technical × 0.6) + (AI × 0.4)
```

The AI can also **veto** a signal if it detects conditions the technical indicators
miss (e.g., major news events, unusual volume patterns).

### Customizing indicators

You can change indicator parameters in `settings.toml`:

```toml
[oracle]
rsi_period = 21          # Longer RSI period for smoother signals
rsi_overbought = 75      # Higher threshold to reduce false signals
rsi_oversold = 25
macd_fast = 8            # Faster MACD for quicker signals
macd_slow = 21
bbands_std = 2.5         # Wider bands for volatile markets
ema_periods = [10, 20, 50, 100]  # Custom EMA periods
```

You can also choose which indicators to use:

```toml
[oracle]
indicators = ["rsi", "macd", "ema"]  # Only use these three
```

---

## 7. Risk Management

KeryxFlow has a built-in risk management system called **Aegis**. It enforces safety
limits that protect your capital, and these limits cannot be overridden — they are
hardcoded into the system by design.

### Safety guardrails

Every order must pass through these checks before execution:

| Guardrail | Limit | What it does |
|-----------|-------|-------------|
| Max position size | **10%** of portfolio | No single position can exceed 10% of your total account value |
| Max total exposure | **50%** of portfolio | Total value of all open positions cannot exceed 50% |
| Min cash reserve | **20%** of portfolio | At least 20% of your portfolio stays in cash at all times |
| Max loss per trade | **2%** of portfolio | Any single trade cannot lose more than 2% |
| Daily loss limit | **5%** of portfolio | Trading halts if daily losses reach 5% |
| Weekly loss limit | **10%** of portfolio | Trading halts if weekly losses reach 10% |
| Max drawdown | **20%** from peak | Trading halts if account drops 20% from its highest point |
| Max trades per hour | **10** | Rate limit to prevent overtrading |
| Max trades per day | **50** | Daily rate limit |
| Consecutive loss halt | **5** losses | Trading halts after 5 consecutive losing trades |

> **Important:** These guardrails are immutable. They exist to prevent catastrophic
> losses and cannot be changed through configuration. This is a deliberate safety
> feature.

### Circuit breaker

When a loss limit is hit (daily, weekly, or drawdown), the circuit breaker activates:

- All new orders are rejected
- Existing positions remain open (they are not force-closed)
- Trading resumes automatically the next day (for daily limits) or next week (for weekly)
- You will see a notification in the TUI and receive alerts if notifications are enabled

### Position sizing

KeryxFlow calculates position size automatically based on your risk settings:

| Setting | Default | What it controls |
|---------|---------|-----------------|
| `risk_per_trade` | 1% | Percentage of portfolio risked per trade |
| `model` | `fixed_fractional` | Sizing model (`fixed_fractional` or `kelly`) |
| `min_risk_reward` | 1.5 | Minimum reward:risk ratio required to take a trade |

**Fixed fractional** (default): Risks a fixed percentage of your portfolio on each trade.
A 1% risk with a $10,000 account means risking $100 per trade.

**Kelly criterion**: Dynamically adjusts position size based on your historical win rate
and average win/loss ratio. Can be more aggressive when you are winning.

### Trailing stops

Trailing stops lock in profits as the price moves in your favor:

| Setting | Default | What it does |
|---------|---------|-------------|
| `trailing_stop_enabled` | `true` | Enable trailing stops |
| `trailing_stop_pct` | 2% | Distance the stop trails behind the price |
| `trailing_activation_pct` | 1% | Minimum profit before the trailing stop activates |

Example: You enter a long position at $100. The trailing stop activates when the price
reaches $101 (1% profit). If the price then rises to $110, your stop is at $107.80
(2% below the high). If the price drops to $107.80, the position is closed
automatically, locking in the gain.

### Stop loss types

| Type | How it works |
|------|-------------|
| `atr` (default) | Stop distance based on Average True Range — adapts to volatility |
| `fixed` | Fixed dollar amount below entry |
| `percentage` | Fixed percentage below entry |

---

## 8. AI Agent Mode

The Cognitive Agent is an autonomous AI trader that uses Claude to perceive markets,
analyze conditions, remember past trades, and execute orders — all without human
intervention.

### How it works

The agent runs a continuous cycle:

1. **Perceive** — Fetches current prices, order book, and portfolio state
2. **Remember** — Recalls similar past trades and relevant trading rules
3. **Analyze** — Computes indicators, position sizing, and risk/reward
4. **Decide** — AI evaluates all data and decides: hold, enter, or exit
5. **Validate** — Decision is checked against safety guardrails
6. **Execute** — If approved, the order is placed
7. **Learn** — Trade outcome is recorded for future reference

This cycle repeats at a configurable interval (default: every 60 seconds).

### Enabling the agent

Set these in your `settings.toml`:

```toml
[system]
ai_mode = "autonomous"

[agent]
enabled = true
cycle_interval = 60           # Seconds between cycles
fallback_to_technical = true  # Use technical signals if AI fails
daily_token_budget = 1000000  # Token spending limit per day
```

You also need an Anthropic API key in your `.env`:

```bash
ANTHROPIC_API_KEY=your-key-here
```

### Controlling the agent from the TUI

Press `a` in the TUI to start the agent. Press `a` again to pause it, and again to
resume. The agent panel shows:

- Current state (Running, Paused, Stopped)
- Cycles completed and success rate
- Trades made, win rate, and P&L
- Tool calls and token usage

### Fallback behavior

If `fallback_to_technical` is `true` (the default), the agent will fall back to
standard technical signals when:

- The AI API is unavailable
- The daily token budget is exhausted
- The AI returns an error or times out
- Consecutive errors exceed the threshold (default: 3)

This ensures trading continues even when AI is temporarily unavailable.

### Token budget

The agent uses AI tokens for each decision cycle. Monitor your usage:

| Setting | Default | Description |
|---------|---------|-------------|
| `daily_token_budget` | 1,000,000 | Max tokens per day (0 = unlimited) |
| `cost_per_million_input_tokens` | $3.00 | For cost tracking |
| `cost_per_million_output_tokens` | $15.00 | For cost tracking |

### Multi-agent mode

For advanced users, KeryxFlow supports running multiple specialized AI agents:

```toml
[agent]
multi_agent_enabled = true
analyst_model = "claude-sonnet-4-20250514"   # Market analysis
risk_model = "claude-sonnet-4-20250514"      # Risk assessment
executor_model = "claude-sonnet-4-20250514"  # Trade execution
```

When enabled, separate AI instances handle analysis, risk evaluation, and execution,
providing more thorough decision-making at the cost of higher token usage.

---

## 9. Backtesting

Backtesting lets you test trading strategies against historical data to see how they
would have performed.

### Running a backtest

```bash
poetry run keryxflow-backtest --symbol BTC/USDT --start 2024-01-01 --end 2024-06-30
```

### CLI options

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--symbol` | `-s` | (required) | Trading pair(s), e.g., `BTC/USDT ETH/USDT` |
| `--start` | | (required) | Start date `YYYY-MM-DD` |
| `--end` | | (required) | End date `YYYY-MM-DD` |
| `--balance` | `-b` | 10000 | Starting balance in USDT |
| `--profile` | `-p` | `balanced` | Risk profile: `conservative`, `balanced`, `aggressive` |
| `--timeframe` | `-t` | `1h` | Candle timeframe |
| `--data` | `-d` | | Path to directory with local CSV files |
| `--slippage` | | 0.001 | Simulated slippage (0.1%) |
| `--commission` | | 0.001 | Simulated commission (0.1%) |
| `--output` | `-o` | | Directory to save CSV reports |
| `--chart` | | | Show ASCII equity chart in terminal |
| `--trades` | | 0 | Show last N trades (0 = hide) |
| `--mtf` | | | Enable multi-timeframe analysis |
| `--timeframes` | | | Timeframes for MTF mode (e.g., `15m 1h 4h`) |
| `--filter-tf` | | `4h` | Filter timeframe for trend direction |
| `--walk-forward` | | | Enable walk-forward analysis |
| `--wf-windows` | | 5 | Number of walk-forward windows |
| `--wf-oos-pct` | | 0.3 | Out-of-sample fraction per window (30%) |
| `--monte-carlo` | | | Enable Monte Carlo simulation |
| `--simulations` | | 1000 | Number of Monte Carlo simulations |
| `--html` | | | Path for interactive HTML report |

### Examples

```bash
# Basic backtest with chart
poetry run keryxflow-backtest -s BTC/USDT --start 2024-01-01 --end 2024-06-30 --chart

# Multiple symbols with HTML report
poetry run keryxflow-backtest -s BTC/USDT ETH/USDT --start 2024-01-01 \
  --end 2024-12-31 --html report.html

# Conservative profile with custom balance
poetry run keryxflow-backtest -s BTC/USDT --start 2024-01-01 --end 2024-06-30 \
  -b 50000 -p conservative

# Use local CSV data instead of fetching from exchange
poetry run keryxflow-backtest -s BTC/USDT --start 2024-01-01 --end 2024-06-30 \
  --data ./my-data/
```

### Reading results

The backtest output includes:

- **Total return** — Percentage gain/loss over the period
- **Sharpe ratio** — Risk-adjusted return (above 1.0 is good, above 2.0 is excellent)
- **Max drawdown** — Largest peak-to-trough decline
- **Win rate** — Percentage of profitable trades
- **Profit factor** — Gross profit divided by gross loss (above 1.5 is good)
- **Total trades** — Number of completed trades

### HTML reports

Pass `--html report.html` to generate an interactive HTML report with:

- Equity curve chart
- Drawdown chart
- Trade-by-trade table
- Performance statistics

### Walk-forward analysis

Walk-forward analysis splits your data into rolling train/test windows to detect
overfitting:

```bash
poetry run keryxflow-backtest -s BTC/USDT --start 2024-01-01 --end 2024-12-31 \
  --walk-forward --wf-windows 5 --wf-oos-pct 0.3
```

This runs 5 rolling windows where 70% of each window trains the strategy and 30%
tests it on unseen data. Consistent performance across windows means the strategy
is robust.

### Monte Carlo simulation

Monte Carlo runs thousands of randomized trade sequences to estimate risk:

```bash
poetry run keryxflow-backtest -s BTC/USDT --start 2024-01-01 --end 2024-06-30 \
  --monte-carlo --simulations 1000
```

This helps you understand the range of possible outcomes and the probability of
extreme drawdowns.

---

## 10. Parameter Optimization

The optimizer tests different parameter combinations to find the best-performing
settings for your strategy.

### Running the optimizer

```bash
poetry run keryxflow-optimize --symbol BTC/USDT --start 2024-01-01 --end 2024-06-30
```

### CLI options

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--symbol` | `-s` | (required) | Trading pair(s) |
| `--start` | | (required) | Start date `YYYY-MM-DD` |
| `--end` | | (required) | End date `YYYY-MM-DD` |
| `--grid` | `-g` | `quick` | Grid search mode |
| `--param` | `-P` | | Custom parameter: `name:val1,val2,val3[:category]` |
| `--metric` | `-m` | `sharpe_ratio` | Optimization target |
| `--balance` | `-b` | 10000 | Starting balance |
| `--profile` | `-p` | `balanced` | Risk profile |
| `--timeframe` | `-t` | `1h` | Candle timeframe |
| `--data` | `-d` | | Path to directory with local CSV files |
| `--slippage` | | 0.001 | Simulated slippage (0.1%) |
| `--commission` | | 0.001 | Simulated commission (0.1%) |
| `--output` | `-o` | | Directory for results |
| `--top` | | 5 | Number of top results to show |
| `--compact` | | | Use compact output format |

### Grid search modes

| Mode | Combinations | What it tests |
|------|-------------|---------------|
| `quick` | 27 | RSI period, risk per trade, min risk:reward |
| `oracle` | 81 | RSI, MACD, and Bollinger Band parameters |
| `risk` | 27 | Risk per trade, min risk:reward, ATR multiplier |
| `full` | 2,187 | All oracle + risk parameters combined |

> **Tip:** Start with `quick` to get a fast overview, then use `oracle` or `risk` to
> fine-tune specific areas. `full` takes significantly longer but is the most thorough.

### Optimization metrics

| Metric | What it optimizes for |
|--------|----------------------|
| `sharpe_ratio` (default) | Best risk-adjusted returns |
| `total_return` | Highest raw returns |
| `profit_factor` | Best profit/loss ratio |
| `win_rate` | Highest percentage of winning trades |

### Custom parameters

Define custom parameter ranges with `--param`:

```bash
poetry run keryxflow-optimize -s BTC/USDT --start 2024-01-01 --end 2024-06-30 \
  --param "rsi_period:10,14,21" --param "risk_per_trade:0.005,0.01,0.02:risk"
```

Format: `name:value1,value2,value3[:category]`

### Examples

```bash
# Quick optimization targeting Sharpe ratio
poetry run keryxflow-optimize -s BTC/USDT --start 2024-01-01 --end 2024-06-30

# Full grid targeting total return, show top 10
poetry run keryxflow-optimize -s BTC/USDT --start 2024-01-01 --end 2024-06-30 \
  -g full -m total_return --top 10

# Save results to file
poetry run keryxflow-optimize -s BTC/USDT --start 2024-01-01 --end 2024-06-30 \
  -o ./optimization-results/
```

> **Warning:** Optimization results can overfit to historical data. Always validate
> optimized parameters with walk-forward analysis before using them in live trading.

---

## 11. REST API & WebSocket

KeryxFlow includes a REST API and WebSocket server for external integrations — connect
custom dashboards, trading bots, or monitoring systems.

### Enabling the API

```toml
[api]
enabled = true
host = "127.0.0.1"          # Bind address
port = 8080                  # Server port
token = "your-secret-token"  # Authentication token
```

### Authentication

All API requests require a Bearer token in the `Authorization` header:

```bash
curl -H "Authorization: Bearer your-secret-token" http://localhost:8080/api/status
```

### REST endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/status` | Engine status, uptime, current mode |
| `GET` | `/api/positions` | All open positions with unrealized P&L |
| `GET` | `/api/trades` | Trade history |
| `GET` | `/api/balance` | Current account balance |
| `POST` | `/api/panic` | Emergency stop — closes all positions |
| `POST` | `/api/pause` | Pause or resume trading |
| `GET` | `/api/agent/status` | AI agent session status |

### WebSocket events

Connect to the WebSocket for real-time event streaming:

```
ws://localhost:8080/ws/events
```

Events are JSON messages with a `type` field. Common event types:

| Event | Fired when |
|-------|-----------|
| `PRICE_UPDATE` | New price data received |
| `SIGNAL_GENERATED` | A trading signal is produced |
| `ORDER_FILLED` | An order is executed |
| `POSITION_OPENED` | A new position is opened |
| `POSITION_CLOSED` | A position is closed |
| `CIRCUIT_BREAKER_TRIGGERED` | A safety limit is hit |

### CORS configuration

To access the API from a web browser, configure allowed origins:

```toml
[api]
cors_origins = ["http://localhost:3000", "https://my-dashboard.com"]
```

---

## 12. Notifications

Get alerts on Discord or Telegram when important trading events happen.

### Discord setup

1. Create a webhook in your Discord server:
   - Server Settings > Integrations > Webhooks > New Webhook
   - Copy the webhook URL

2. Configure KeryxFlow:

```toml
[notifications]
discord_enabled = true
discord_webhook = "https://discord.com/api/webhooks/..."
```

Or via environment variables:

```bash
KERYXFLOW_NOTIFY_DISCORD_ENABLED=true
KERYXFLOW_NOTIFY_DISCORD_WEBHOOK=https://discord.com/api/webhooks/...
```

### Telegram setup

1. Create a bot via [@BotFather](https://t.me/BotFather) on Telegram
2. Get your chat ID (message [@userinfobot](https://t.me/userinfobot))

3. Configure KeryxFlow:

```toml
[notifications]
telegram_enabled = true
telegram_token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
telegram_chat_id = "987654321"
```

### Notification events

You can control which events trigger notifications:

| Setting | Default | Events |
|---------|---------|--------|
| `notify_on_trade` | `true` | Position opened and closed |
| `notify_on_circuit_breaker` | `true` | Safety limits triggered |
| `notify_daily_summary` | `true` | End-of-day performance summary |
| `notify_on_error` | `true` | Critical errors |

---

## 13. Multi-Exchange Support

KeryxFlow supports trading on **Binance** and **Bybit** through a unified interface.

### Switching exchanges

Set the exchange in `settings.toml`:

```toml
[system]
exchange = "binance"   # or "bybit"
```

Or via environment variable:

```bash
KERYXFLOW_EXCHANGE=bybit
```

### Exchange-specific setup

**Binance:**

1. Create an API key at [binance.com](https://www.binance.com/en/my/settings/api-management)
2. Enable "Enable Reading" and "Enable Spot & Margin Trading" permissions
3. Add to `.env`:

```bash
BINANCE_API_KEY=your-key
BINANCE_API_SECRET=your-secret
```

**Bybit:**

1. Create an API key at [bybit.com](https://www.bybit.com/app/user/api-management)
2. Set permissions for reading and trading
3. Add to `.env`:

```bash
BYBIT_API_KEY=your-key
BYBIT_API_SECRET=your-secret
```

### Paper trading without exchange keys

For paper trading, you do not need any exchange API keys. KeryxFlow uses a built-in
paper trading engine that simulates order execution with configurable slippage and
commission.

---

## 14. Live Trading Checklist

Before switching from paper to live trading, work through this checklist to ensure
you are ready.

### Pre-flight checks

- [ ] **Paper trade first** — Complete at least 30 paper trades (configurable via
      `min_paper_trades` in `[live]` settings)
- [ ] **Review backtest results** — Run backtests across multiple time periods and
      confirm consistent performance
- [ ] **Validate with walk-forward** — Ensure your strategy is not overfit to
      historical data
- [ ] **Set up notifications** — Configure Discord or Telegram alerts so you stay
      informed
- [ ] **Check API key permissions** — Ensure your exchange API key has trading permissions
- [ ] **Start with small positions** — Set a conservative `max_position_value`
- [ ] **Understand the guardrails** — Review the safety limits in
      [Section 7](#7-risk-management) and know they cannot be changed
- [ ] **Enable confirmation mode** — Keep `require_confirmation = true` for extra safety
- [ ] **Monitor your first trades** — Watch the TUI during your first live session

### Switching to live mode

```toml
[system]
mode = "live"                  # Change from "paper" to "live"

[live]
require_confirmation = true    # Confirm orders before execution
min_paper_trades = 30          # Must complete this many paper trades first
min_balance = 100.0            # Minimum USDT balance required
max_position_value = 1000.0    # Maximum value per position
sync_interval = 60             # Seconds between balance syncs with exchange
```

> **Warning:** Live trading uses real money. Start with small amounts and increase
> gradually as you gain confidence in the system.

### Minimum requirements

| Requirement | Default | Setting |
|-------------|---------|---------|
| Minimum paper trades | 30 | `KERYXFLOW_LIVE_MIN_PAPER_TRADES` |
| Minimum balance | $100 USDT | `KERYXFLOW_LIVE_MIN_BALANCE` |
| Max position value | $1,000 USDT | `KERYXFLOW_LIVE_MAX_POSITION_VALUE` |

---

## 15. Troubleshooting & FAQ

### Common errors

**"Missing Anthropic API key"**
You need an `ANTHROPIC_API_KEY` in your `.env` file to use AI features. Paper trading
with `ai_mode = "disabled"` works without it.

**"Insufficient candle data for indicators"**
Indicators need historical data to calculate. Make sure at least 50 candles are
available. This may take a few minutes on first launch as data is fetched.

**"Circuit breaker triggered"**
You have hit a daily/weekly loss limit. This is a safety feature. Trading will
resume automatically when the time limit expires (next day for daily, next week
for weekly). See [Section 7](#7-risk-management) for details.

**"Symbol not allowed"**
The symbol you are trying to trade is not in your `symbols` list. Add it to
`settings.toml`:

```toml
[system]
symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
```

**"Agent cycle failed"**
The AI agent encountered an error. If `fallback_to_technical` is enabled (default),
trading continues with technical signals. Check the logs for details.

**"Exchange connection failed"**
Verify your API keys are correct and your internet connection is stable. KeryxFlow
uses automatic retries with exponential backoff.

### Debug mode

Enable verbose logging to diagnose issues:

```toml
[system]
log_level = "DEBUG"
```

Or via environment variable:

```bash
KERYXFLOW_LOG_LEVEL=DEBUG
```

Press `l` in the TUI to show the log panel, which displays real-time log messages.

### Data and log locations

| What | Location |
|------|----------|
| Database | `data/keryxflow.db` (SQLite) |
| Configuration | `settings.toml` (project root) |
| Secrets | `.env` (project root) |

### FAQ

**Q: Can I run KeryxFlow 24/7?**
A: Yes. KeryxFlow is designed for continuous operation. Use a server, VPS, or
`tmux`/`screen` session to keep it running.

**Q: How much does the AI agent cost to run?**
A: Costs depend on your `cycle_interval` and token usage. With the default settings
(60-second cycles, Sonnet model), expect roughly $5-15/day. Set `daily_token_budget`
to cap spending.

**Q: Can I trade spot only, or does it support futures?**
A: KeryxFlow currently supports spot trading. Futures support may be added in
future releases.

**Q: Can I run multiple instances?**
A: Yes, but use separate data directories and configuration files to avoid conflicts.

**Q: Does paper trading use real market data?**
A: Yes. Paper trading fetches real-time prices from your configured exchange and
simulates order execution locally.

---

## 16. Glossary

| Term | Definition |
|------|-----------|
| **ATR** | Average True Range — a volatility indicator used for dynamic stop-loss placement |
| **Bollinger Bands** | Bands plotted above and below a moving average to identify price extremes |
| **Circuit breaker** | An automatic halt triggered when loss limits are reached, preventing further trading |
| **Cognitive Agent** | The autonomous AI trader that runs the Perceive-Analyze-Decide-Execute cycle |
| **Confidence** | A score from 0.0 to 1.0 representing how strongly indicators agree on a direction |
| **Drawdown** | The decline from a portfolio's peak value to its lowest point |
| **EMA** | Exponential Moving Average — a smoothed average giving more weight to recent prices |
| **Episode** | A complete trade record including entry reasoning, market context, and lessons learned |
| **Guardrail** | A hardcoded safety limit that cannot be overridden, protecting your capital |
| **Kelly criterion** | A position-sizing formula that adjusts trade size based on historical win rate |
| **MACD** | Moving Average Convergence Divergence — a trend-following momentum indicator |
| **Monte Carlo** | A simulation technique that randomizes trade sequences to estimate risk distributions |
| **OBV** | On-Balance Volume — uses volume flow to confirm price trends |
| **Oracle** | KeryxFlow's signal generation system that combines technical analysis with AI |
| **Paper trading** | Simulated trading with fake funds and real market data, used for practice |
| **Panic** | Emergency action that immediately closes all positions and halts trading |
| **Position sizing** | Calculating how large a trade should be based on risk parameters |
| **RSI** | Relative Strength Index — a momentum oscillator measuring overbought/oversold conditions |
| **Sharpe ratio** | A measure of risk-adjusted return; higher is better (1.0+ is good, 2.0+ is excellent) |
| **Signal** | A trading recommendation (LONG, SHORT, or HOLD) generated by analysis |
| **Trailing stop** | A stop-loss that moves in your favor as the price rises, locking in profits |
| **Walk-forward** | A backtesting technique that validates strategy performance on unseen data |

---

*KeryxFlow is open-source software. For developer documentation, see the
[Architecture Guide](architecture.md). For API details, see the [API Reference](api.md).*
