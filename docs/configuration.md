# KeryxFlow Configuration

This document describes all configuration options and how to customize KeryxFlow.

## Configuration Sources

KeryxFlow loads configuration from multiple sources (in order of precedence):

1. **Environment variables** (highest priority)
2. **`.env` file** (API keys and secrets)
3. **`settings.toml`** (application settings)
4. **Default values** (fallback)

---

## Quick Start

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your API keys:
   ```bash
   BINANCE_API_KEY=your_key_here
   BINANCE_API_SECRET=your_secret_here
   ANTHROPIC_API_KEY=your_key_here
   ```

3. (Optional) Customize `settings.toml` for your preferences.

---

## Environment Variables (`.env`)

These are sensitive credentials that should never be committed to version control.

### Required for Live Trading

| Variable | Description | Example |
|----------|-------------|---------|
| `BINANCE_API_KEY` | Binance API key | `abc123...` |
| `BINANCE_API_SECRET` | Binance API secret | `xyz789...` |

### Required for LLM Features

| Variable | Description | Example |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Claude API key | `sk-ant-...` |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `CRYPTOPANIC_API_KEY` | CryptoPanic news API | (empty) |
| `KERYXFLOW_ENV` | Environment mode | `development` |

### Notifications

| Variable | Description |
|----------|-------------|
| `KERYXFLOW_NOTIFY_TELEGRAM_ENABLED` | Enable Telegram (`true`/`false`) |
| `KERYXFLOW_NOTIFY_TELEGRAM_TOKEN` | Bot token from @BotFather |
| `KERYXFLOW_NOTIFY_TELEGRAM_CHAT_ID` | Chat ID from @userinfobot |
| `KERYXFLOW_NOTIFY_DISCORD_ENABLED` | Enable Discord (`true`/`false`) |
| `KERYXFLOW_NOTIFY_DISCORD_WEBHOOK` | Discord webhook URL |

---

## Application Settings (`settings.toml`)

### [system]

General system configuration.

```toml
[system]
exchange = "binance"              # Exchange to use
mode = "paper"                    # "paper" or "live"
symbols = ["BTC/USDT", "ETH/USDT"] # Trading pairs
base_currency = "USDT"            # Quote currency
log_level = "INFO"                # DEBUG, INFO, WARNING, ERROR
```

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `exchange` | string | `"binance"` | Exchange (only Binance supported) |
| `mode` | string | `"paper"` | Trading mode: `"paper"` or `"live"` |
| `symbols` | list | `["BTC/USDT", "ETH/USDT"]` | Trading pairs |
| `base_currency` | string | `"USDT"` | Quote currency |
| `log_level` | string | `"INFO"` | Logging verbosity |

---

### [risk]

Risk management parameters. **Critical for capital preservation.**

```toml
[risk]
model = "fixed_fractional"        # Position sizing model
risk_per_trade = 0.01             # 1% of balance per trade
max_daily_drawdown = 0.05         # 5% daily loss limit
max_open_positions = 3            # Maximum concurrent positions
min_risk_reward = 1.5             # Minimum R:R ratio
stop_loss_type = "atr"            # "atr", "fixed", or "percentage"
atr_multiplier = 2.0              # ATR multiplier for stops
```

| Setting | Type | Range | Default | Description |
|---------|------|-------|---------|-------------|
| `model` | string | `fixed_fractional`, `kelly` | `"fixed_fractional"` | Position sizing model |
| `risk_per_trade` | float | 0.001-0.1 | `0.01` | Risk per trade (1% = 0.01) |
| `max_daily_drawdown` | float | 0.01-0.5 | `0.05` | Max daily loss before circuit breaker |
| `max_open_positions` | int | 1-20 | `3` | Max concurrent positions |
| `min_risk_reward` | float | 0.5-10.0 | `1.5` | Minimum risk/reward ratio |
| `stop_loss_type` | string | `atr`, `fixed`, `percentage` | `"atr"` | Stop loss calculation method |
| `atr_multiplier` | float | 0.5-5.0 | `2.0` | ATR multiplier for dynamic stops |

**Risk Profiles:**

| Profile | risk_per_trade | max_daily_drawdown | max_open_positions |
|---------|----------------|--------------------|--------------------|
| Conservative | 0.5% | 3% | 2 |
| Balanced | 1% | 5% | 3 |
| Aggressive | 2% | 10% | 5 |

---

### [oracle]

Intelligence layer configuration.

```toml
[oracle]
# Technical Analysis
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

# LLM Integration
llm_enabled = true
llm_model = "claude-sonnet-4-20250514"
analysis_interval = 300           # Seconds between analyses
max_tokens = 1024

# News Sources
news_enabled = true
news_sources = ["cryptopanic", "rss"]
rss_feeds = [
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
]
news_lookback_hours = 4
```

#### Technical Indicators

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `indicators` | list | `["rsi", "macd", ...]` | Active indicators |
| `rsi_period` | int | `14` | RSI calculation period |
| `rsi_overbought` | int | `70` | Overbought threshold |
| `rsi_oversold` | int | `30` | Oversold threshold |
| `macd_fast` | int | `12` | MACD fast EMA period |
| `macd_slow` | int | `26` | MACD slow EMA period |
| `macd_signal` | int | `9` | MACD signal line period |
| `bbands_period` | int | `20` | Bollinger Bands period |
| `bbands_std` | float | `2.0` | Bollinger Bands std dev |
| `ema_periods` | list | `[9, 21, 50, 200]` | EMA periods for alignment |

#### LLM Settings

| Setting | Type | Range | Default | Description |
|---------|------|-------|---------|-------------|
| `llm_enabled` | bool | - | `true` | Enable Claude analysis |
| `llm_model` | string | - | `"claude-sonnet-4-20250514"` | Claude model to use |
| `analysis_interval` | int | 60-3600 | `300` | Seconds between LLM analyses |
| `max_tokens` | int | - | `1024` | Max tokens for LLM response |

#### News Settings

| Setting | Type | Range | Default | Description |
|---------|------|-------|---------|-------------|
| `news_enabled` | bool | - | `true` | Enable news aggregation |
| `news_sources` | list | - | `["cryptopanic", "rss"]` | News sources |
| `rss_feeds` | list | - | (CoinTelegraph, Decrypt) | RSS feed URLs |
| `news_lookback_hours` | int | 1-24 | `4` | Hours of news to fetch |

---

### [hermes]

Terminal UI configuration.

```toml
[hermes]
refresh_rate = 1.0                # TUI refresh rate in seconds
chart_width = 60                  # Chart width in characters
chart_height = 15                 # Chart height in characters
max_log_lines = 100               # Maximum log lines to display
theme = "cyberpunk"               # "cyberpunk" or "minimal"
```

| Setting | Type | Range | Default | Description |
|---------|------|-------|---------|-------------|
| `refresh_rate` | float | 0.1-10.0 | `1.0` | UI refresh interval (seconds) |
| `chart_width` | int | 20-200 | `60` | Chart width (characters) |
| `chart_height` | int | 5-50 | `15` | Chart height (characters) |
| `max_log_lines` | int | 10-1000 | `100` | Max log entries |
| `theme` | string | `cyberpunk`, `minimal` | `"cyberpunk"` | UI theme |

---

### [database]

Database configuration.

```toml
[database]
url = "sqlite+aiosqlite:///data/keryxflow.db"
```

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `url` | string | `"sqlite+aiosqlite:///data/keryxflow.db"` | Database connection URL |

---

### [live]

Live trading safeguards.

```toml
[live]
require_confirmation = true       # Require explicit confirmation
min_paper_trades = 30             # Minimum paper trades before live
min_balance = 100.0               # Minimum USDT balance
max_position_value = 1000.0       # Maximum position value in USDT
sync_interval = 60                # Balance sync interval (seconds)
```

| Setting | Type | Range | Default | Description |
|---------|------|-------|---------|-------------|
| `require_confirmation` | bool | - | `true` | Require explicit live mode confirmation |
| `min_paper_trades` | int | 0-1000 | `30` | Required paper trades before live |
| `min_balance` | float | 0+ | `100.0` | Minimum USDT balance |
| `max_position_value` | float | 10+ | `1000.0` | Max position value (USDT) |
| `sync_interval` | int | 10-300 | `60` | Balance sync interval (seconds) |

---

### [notifications]

Alert configuration.

```toml
[notifications]
# Telegram Bot
telegram_enabled = false
telegram_token = ""               # Bot token from @BotFather
telegram_chat_id = ""             # Chat ID from @userinfobot

# Discord Webhook
discord_enabled = false
discord_webhook = ""              # Webhook URL

# Notification preferences
notify_on_trade = true            # Notify on order fills
notify_on_circuit_breaker = true  # Notify on circuit breaker
notify_daily_summary = true       # Daily trading summary
notify_on_error = true            # System error alerts
```

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `telegram_enabled` | bool | `false` | Enable Telegram notifications |
| `telegram_token` | string | `""` | Bot token from @BotFather |
| `telegram_chat_id` | string | `""` | Your chat ID |
| `discord_enabled` | bool | `false` | Enable Discord notifications |
| `discord_webhook` | string | `""` | Discord webhook URL |
| `notify_on_trade` | bool | `true` | Notify on order fills |
| `notify_on_circuit_breaker` | bool | `true` | Notify on circuit breaker |
| `notify_daily_summary` | bool | `true` | Send daily summary |
| `notify_on_error` | bool | `true` | Notify on errors |

---

## Configuration Examples

### Conservative Paper Trading

```toml
[system]
mode = "paper"
symbols = ["BTC/USDT"]

[risk]
risk_per_trade = 0.005    # 0.5%
max_daily_drawdown = 0.03 # 3%
max_open_positions = 2
min_risk_reward = 2.0

[oracle]
llm_enabled = true
analysis_interval = 600   # 10 minutes
```

### Aggressive Multi-Symbol

```toml
[system]
mode = "paper"
symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]

[risk]
risk_per_trade = 0.02     # 2%
max_daily_drawdown = 0.10 # 10%
max_open_positions = 5
min_risk_reward = 1.0

[oracle]
analysis_interval = 180   # 3 minutes
```

### Live Trading (Careful!)

```toml
[system]
mode = "live"
symbols = ["BTC/USDT"]

[risk]
risk_per_trade = 0.01
max_daily_drawdown = 0.05
max_open_positions = 2
min_risk_reward = 1.5

[live]
require_confirmation = true
min_paper_trades = 50
min_balance = 500.0
max_position_value = 500.0

[notifications]
telegram_enabled = true
notify_on_trade = true
notify_on_circuit_breaker = true
```

---

## Environment Variable Overrides

Any setting can be overridden via environment variables using the prefix `KERYXFLOW_`:

```bash
# Override risk per trade
export KERYXFLOW_RISK_RISK_PER_TRADE=0.02

# Override trading mode
export KERYXFLOW_MODE=live

# Override log level
export KERYXFLOW_LOG_LEVEL=DEBUG
```

---

## Validation

Settings are validated on startup using Pydantic:

- **Range validation**: Values must be within allowed ranges
- **Type validation**: Values must match expected types
- **Required fields**: API keys validated when features are used

Invalid configuration will prevent startup with a clear error message.

---

## Security Best Practices

1. **Never commit `.env`** - Add to `.gitignore`
2. **Use minimal permissions** - Binance API keys should only have trading permissions (no withdrawal)
3. **Start with paper mode** - Always test with simulated money first
4. **Keep backups** - Backup `settings.toml` before major changes
5. **Review before live** - Double-check all settings before enabling live trading
