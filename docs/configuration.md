# KeryxFlow Configuration Reference

Complete reference for all configuration options. All settings are defined in `keryxflow/config.py`.

## Configuration Sources

KeryxFlow loads configuration from multiple sources (in order of precedence):

1. **Environment variables** (highest priority)
2. **`.env` file** (API keys and secrets)
3. **`settings.toml`** (application settings)
4. **Default values** (fallback)

## API Keys (`.env`)

Sensitive credentials loaded from `.env`. Never commit this file to version control.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `BINANCE_API_KEY` | SecretStr | `""` | Binance API key |
| `BINANCE_API_SECRET` | SecretStr | `""` | Binance API secret |
| `BYBIT_API_KEY` | SecretStr | `""` | Bybit API key |
| `BYBIT_API_SECRET` | SecretStr | `""` | Bybit API secret |
| `KRAKEN_API_KEY` | SecretStr | `""` | Kraken API key |
| `KRAKEN_API_SECRET` | SecretStr | `""` | Kraken API secret |
| `OKX_API_KEY` | SecretStr | `""` | OKX API key |
| `OKX_API_SECRET` | SecretStr | `""` | OKX API secret |
| `OKX_PASSPHRASE` | SecretStr | `""` | OKX API passphrase |
| `ANTHROPIC_API_KEY` | SecretStr | `""` | Anthropic API key (required for LLM/Agent features) |
| `CRYPTOPANIC_API_KEY` | SecretStr | `""` | CryptoPanic news API key |

Top-level setting:

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ENV` | string | `"development"` | Environment: `development` or `production` |

## System Settings

Env prefix: `KERYXFLOW_`

| Variable | Type | Default | Constraints | Description |
|----------|------|---------|-------------|-------------|
| `KERYXFLOW_EXCHANGE` | string | `"binance"` | — | Exchange to use: `binance`, `bybit`, etc. |
| `KERYXFLOW_MODE` | string | `"paper"` | `paper`, `live`, `demo` | Trading mode |
| `KERYXFLOW_AI_MODE` | string | `"disabled"` | `disabled`, `enhanced`, `autonomous` | AI integration level |
| `KERYXFLOW_SYMBOLS` | list | `["BTC/USDT", "ETH/USDT"]` | — | Trading pairs to watch |
| `KERYXFLOW_BASE_CURRENCY` | string | `"USDT"` | — | Quote currency |
| `KERYXFLOW_LOG_LEVEL` | string | `"INFO"` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | Logging verbosity |
| `KERYXFLOW_DEMO_MODE` | bool | `false` | — | Enable demo mode |

```toml
[system]
exchange = "binance"
mode = "paper"
ai_mode = "disabled"
symbols = ["BTC/USDT", "ETH/USDT"]
base_currency = "USDT"
log_level = "INFO"
demo_mode = false
```

## Risk Settings

Env prefix: `KERYXFLOW_RISK_`

**Critical for capital preservation.** Changes to `aegis/` require 100% test coverage.

| Variable | Type | Default | Constraints | Description |
|----------|------|---------|-------------|-------------|
| `KERYXFLOW_RISK_MODEL` | string | `"fixed_fractional"` | `fixed_fractional`, `kelly` | Position sizing model |
| `KERYXFLOW_RISK_RISK_PER_TRADE` | float | `0.01` | 0.001–0.1 | Risk per trade (0.01 = 1%) |
| `KERYXFLOW_RISK_MAX_DAILY_DRAWDOWN` | float | `0.05` | 0.01–0.5 | Max daily loss before circuit breaker |
| `KERYXFLOW_RISK_MAX_OPEN_POSITIONS` | int | `3` | 1–20 | Max concurrent positions |
| `KERYXFLOW_RISK_MIN_RISK_REWARD` | float | `1.5` | 0.5–10.0 | Minimum risk/reward ratio |
| `KERYXFLOW_RISK_STOP_LOSS_TYPE` | string | `"atr"` | `atr`, `fixed`, `percentage` | Stop loss calculation method |
| `KERYXFLOW_RISK_ATR_MULTIPLIER` | float | `2.0` | 0.5–5.0 | ATR multiplier for dynamic stops |
| `KERYXFLOW_RISK_TRAILING_STOP_ENABLED` | bool | `true` | — | Enable trailing stop |
| `KERYXFLOW_RISK_TRAILING_STOP_PCT` | float | `0.02` | 0.001–0.2 | Trailing stop distance (0.02 = 2%) |
| `KERYXFLOW_RISK_TRAILING_ACTIVATION_PCT` | float | `0.01` | 0.0–0.1 | Profit threshold to activate trailing stop |
| `KERYXFLOW_RISK_BREAKEVEN_TRIGGER_PCT` | float | `1.0` | 0.1–10.0 | Profit % to trigger break-even stop |

```toml
[risk]
model = "fixed_fractional"
risk_per_trade = 0.01
max_daily_drawdown = 0.05
max_open_positions = 3
min_risk_reward = 1.5
stop_loss_type = "atr"
atr_multiplier = 2.0
trailing_stop_enabled = true
trailing_stop_pct = 0.02
trailing_activation_pct = 0.01
breakeven_trigger_pct = 1.0
```

### Immutable Guardrails

These hardcoded safety limits in `aegis/guardrails.py` cannot be changed at runtime:

| Guardrail | Value | Description |
|-----------|-------|-------------|
| `MAX_POSITION_SIZE_PCT` | 10% | Single position cap |
| `MAX_TOTAL_EXPOSURE_PCT` | 50% | Total portfolio exposure |
| `MIN_CASH_RESERVE_PCT` | 20% | Minimum cash reserve |
| `MAX_DAILY_LOSS_PCT` | 5% | Daily circuit breaker trigger |
| `MAX_TOTAL_DRAWDOWN_PCT` | 20% | Maximum drawdown from peak |

## Multi-Timeframe (MTF) Settings

Env prefix: `KERYXFLOW_MTF_`

Nested under `oracle.mtf` in code. Configure via `[oracle]` section or env vars.

| Variable | Type | Default | Constraints | Description |
|----------|------|---------|-------------|-------------|
| `KERYXFLOW_MTF_ENABLED` | bool | `false` | — | Enable multi-timeframe analysis |
| `KERYXFLOW_MTF_TIMEFRAMES` | list | `["15m", "1h", "4h"]` | — | Timeframes to analyze |
| `KERYXFLOW_MTF_PRIMARY_TIMEFRAME` | string | `"1h"` | — | Primary analysis timeframe |
| `KERYXFLOW_MTF_FILTER_TIMEFRAME` | string | `"4h"` | — | Higher timeframe for trend filter |
| `KERYXFLOW_MTF_MIN_FILTER_CONFIDENCE` | float | `0.5` | 0.0–1.0 | Minimum confidence for filter signals |

## Oracle Settings

Env prefix: `KERYXFLOW_ORACLE_`

### Technical Analysis

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `KERYXFLOW_ORACLE_INDICATORS` | list | `["rsi", "macd", "bbands", "obv", "atr", "ema"]` | Active indicators |
| `KERYXFLOW_ORACLE_RSI_PERIOD` | int | `14` | RSI calculation period |
| `KERYXFLOW_ORACLE_RSI_OVERBOUGHT` | int | `70` | RSI overbought threshold |
| `KERYXFLOW_ORACLE_RSI_OVERSOLD` | int | `30` | RSI oversold threshold |
| `KERYXFLOW_ORACLE_MACD_FAST` | int | `12` | MACD fast EMA period |
| `KERYXFLOW_ORACLE_MACD_SLOW` | int | `26` | MACD slow EMA period |
| `KERYXFLOW_ORACLE_MACD_SIGNAL` | int | `9` | MACD signal line period |
| `KERYXFLOW_ORACLE_BBANDS_PERIOD` | int | `20` | Bollinger Bands period |
| `KERYXFLOW_ORACLE_BBANDS_STD` | float | `2.0` | Bollinger Bands standard deviation |
| `KERYXFLOW_ORACLE_EMA_PERIODS` | list | `[9, 21, 50, 200]` | EMA periods |

### LLM Integration

| Variable | Type | Default | Constraints | Description |
|----------|------|---------|-------------|-------------|
| `KERYXFLOW_ORACLE_LLM_ENABLED` | bool | `true` | — | Enable Claude analysis |
| `KERYXFLOW_ORACLE_LLM_MODEL` | string | `"claude-sonnet-4-20250514"` | — | Claude model |
| `KERYXFLOW_ORACLE_ANALYSIS_INTERVAL` | int | `300` | 60–3600 | Seconds between LLM analyses |
| `KERYXFLOW_ORACLE_MAX_TOKENS` | int | `1024` | — | Max tokens for LLM response |

### News Sources

| Variable | Type | Default | Constraints | Description |
|----------|------|---------|-------------|-------------|
| `KERYXFLOW_ORACLE_NEWS_ENABLED` | bool | `true` | — | Enable news aggregation |
| `KERYXFLOW_ORACLE_NEWS_SOURCES` | list | `["cryptopanic", "rss"]` | — | News sources |
| `KERYXFLOW_ORACLE_RSS_FEEDS` | list | `["https://cointelegraph.com/rss", "https://decrypt.co/feed"]` | — | RSS feed URLs |
| `KERYXFLOW_ORACLE_NEWS_LOOKBACK_HOURS` | int | `4` | 1–24 | Hours of news to fetch |

```toml
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
llm_enabled = true
llm_model = "claude-sonnet-4-20250514"
analysis_interval = 300
max_tokens = 1024
news_enabled = true
news_sources = ["cryptopanic", "rss"]
news_lookback_hours = 4
```

## Agent Settings

Env prefix: `KERYXFLOW_AGENT_`

| Variable | Type | Default | Constraints | Description |
|----------|------|---------|-------------|-------------|
| `KERYXFLOW_AGENT_ENABLED` | bool | `false` | — | Enable Cognitive Agent (replaces SignalGenerator) |
| `KERYXFLOW_AGENT_MODEL` | string | `"claude-sonnet-4-20250514"` | — | Claude model for agent decisions |
| `KERYXFLOW_AGENT_MAX_TOKENS` | int | `4096` | — | Max tokens per agent response |
| `KERYXFLOW_AGENT_TEMPERATURE` | float | `0.3` | — | Lower = more consistent trading decisions |
| `KERYXFLOW_AGENT_CYCLE_INTERVAL` | int | `60` | 10–600 | Seconds between agent cycles |
| `KERYXFLOW_AGENT_MAX_TOOL_CALLS_PER_CYCLE` | int | `20` | 5–50 | Max tool calls per cycle |
| `KERYXFLOW_AGENT_DECISION_TIMEOUT` | int | `30` | 10–120 | Decision timeout in seconds |
| `KERYXFLOW_AGENT_FALLBACK_TO_TECHNICAL` | bool | `true` | — | Fall back to technical signals on API failure |
| `KERYXFLOW_AGENT_MAX_CONSECUTIVE_ERRORS` | int | `3` | 1–10 | Errors before disabling agent |
| `KERYXFLOW_AGENT_ENABLE_PERCEPTION` | bool | `true` | — | Enable perception tools |
| `KERYXFLOW_AGENT_ENABLE_ANALYSIS` | bool | `true` | — | Enable analysis tools |
| `KERYXFLOW_AGENT_ENABLE_INTROSPECTION` | bool | `true` | — | Enable memory/introspection tools |
| `KERYXFLOW_AGENT_ENABLE_EXECUTION` | bool | `true` | — | Enable execution tools (guarded) |
| `KERYXFLOW_AGENT_DAILY_TOKEN_BUDGET` | int | `1000000` | 0 = unlimited | Daily token budget |
| `KERYXFLOW_AGENT_COST_PER_MILLION_INPUT_TOKENS` | float | `3.0` | — | USD per 1M input tokens |
| `KERYXFLOW_AGENT_COST_PER_MILLION_OUTPUT_TOKENS` | float | `15.0` | — | USD per 1M output tokens |
| `KERYXFLOW_AGENT_MULTI_AGENT_ENABLED` | bool | `false` | — | Use AgentOrchestrator instead of CognitiveAgent |
| `KERYXFLOW_AGENT_ANALYST_MODEL` | string | `null` | — | Override model for analyst agent |
| `KERYXFLOW_AGENT_RISK_MODEL` | string | `null` | — | Override model for risk agent |
| `KERYXFLOW_AGENT_EXECUTOR_MODEL` | string | `null` | — | Override model for executor agent |

```toml
[agent]
enabled = false
model = "claude-sonnet-4-20250514"
max_tokens = 4096
temperature = 0.3
cycle_interval = 60
max_tool_calls_per_cycle = 20
decision_timeout = 30
fallback_to_technical = true
max_consecutive_errors = 3
daily_token_budget = 1000000
```

## API Settings

Env prefix: `KERYXFLOW_API_`

| Variable | Type | Default | Constraints | Description |
|----------|------|---------|-------------|-------------|
| `KERYXFLOW_API_ENABLED` | bool | `false` | — | Enable REST API server |
| `KERYXFLOW_API_HOST` | string | `"127.0.0.1"` | — | Bind address |
| `KERYXFLOW_API_PORT` | int | `8080` | 1–65535 | Server port |
| `KERYXFLOW_API_TOKEN` | string | `""` | — | Bearer token (empty = no auth) |
| `KERYXFLOW_API_WEBHOOK_SECRET` | string | `""` | — | Webhook secret |
| `KERYXFLOW_API_CORS_ORIGINS` | list | `["*"]` | — | CORS allowed origins |

```toml
[api]
enabled = false
host = "127.0.0.1"
port = 8080
token = ""
cors_origins = ["*"]
```

## Hermes (TUI) Settings

Env prefix: `KERYXFLOW_HERMES_`

| Variable | Type | Default | Constraints | Description |
|----------|------|---------|-------------|-------------|
| `KERYXFLOW_HERMES_REFRESH_RATE` | float | `1.0` | 0.1–10.0 | UI refresh interval in seconds |
| `KERYXFLOW_HERMES_CHART_WIDTH` | int | `60` | 20–200 | Chart width in characters |
| `KERYXFLOW_HERMES_CHART_HEIGHT` | int | `15` | 5–50 | Chart height in characters |
| `KERYXFLOW_HERMES_MAX_LOG_LINES` | int | `100` | 10–1000 | Max log entries displayed |
| `KERYXFLOW_HERMES_THEME` | string | `"cyberpunk"` | `cyberpunk`, `minimal` | UI theme |

```toml
[hermes]
refresh_rate = 1.0
chart_width = 60
chart_height = 15
max_log_lines = 100
theme = "cyberpunk"
```

## Database Settings

Env prefix: `KERYXFLOW_DB_`

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `KERYXFLOW_DB_URL` | string | `"sqlite+aiosqlite:///data/keryxflow.db"` | Database connection URL |

```toml
[database]
url = "sqlite+aiosqlite:///data/keryxflow.db"
```

## Live Trading Settings

Env prefix: `KERYXFLOW_LIVE_`

| Variable | Type | Default | Constraints | Description |
|----------|------|---------|-------------|-------------|
| `KERYXFLOW_LIVE_REQUIRE_CONFIRMATION` | bool | `true` | — | Require explicit live mode confirmation |
| `KERYXFLOW_LIVE_MIN_PAPER_TRADES` | int | `30` | 0–1000 | Required paper trades before live |
| `KERYXFLOW_LIVE_MIN_BALANCE` | float | `100.0` | 0+ | Minimum USDT balance |
| `KERYXFLOW_LIVE_MAX_POSITION_VALUE` | float | `1000.0` | 10+ | Max position value in USDT |
| `KERYXFLOW_LIVE_SYNC_INTERVAL` | int | `60` | 10–300 | Balance sync interval in seconds |

```toml
[live]
require_confirmation = true
min_paper_trades = 30
min_balance = 100.0
max_position_value = 1000.0
sync_interval = 60
```

## Notification Settings

Env prefix: `KERYXFLOW_NOTIFY_`

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `KERYXFLOW_NOTIFY_TELEGRAM_ENABLED` | bool | `false` | Enable Telegram notifications |
| `KERYXFLOW_NOTIFY_TELEGRAM_TOKEN` | string | `""` | Bot token from @BotFather |
| `KERYXFLOW_NOTIFY_TELEGRAM_CHAT_ID` | string | `""` | Chat ID from @userinfobot |
| `KERYXFLOW_NOTIFY_DISCORD_ENABLED` | bool | `false` | Enable Discord notifications |
| `KERYXFLOW_NOTIFY_DISCORD_WEBHOOK` | string | `""` | Discord webhook URL |
| `KERYXFLOW_NOTIFY_NOTIFY_ON_TRADE` | bool | `true` | Notify on order fills |
| `KERYXFLOW_NOTIFY_NOTIFY_ON_CIRCUIT_BREAKER` | bool | `true` | Notify on circuit breaker trigger |
| `KERYXFLOW_NOTIFY_NOTIFY_DAILY_SUMMARY` | bool | `true` | Send daily trading summary |
| `KERYXFLOW_NOTIFY_NOTIFY_ON_ERROR` | bool | `true` | Notify on system errors |

```toml
[notifications]
telegram_enabled = false
telegram_token = ""
telegram_chat_id = ""
discord_enabled = false
discord_webhook = ""
notify_on_trade = true
notify_on_circuit_breaker = true
notify_daily_summary = true
notify_on_error = true
```

## Complete `.env` Example

```bash
# === Exchange Credentials ===
BINANCE_API_KEY=your_binance_key
BINANCE_API_SECRET=your_binance_secret
BYBIT_API_KEY=your_bybit_key
BYBIT_API_SECRET=your_bybit_secret
KRAKEN_API_KEY=your_kraken_key
KRAKEN_API_SECRET=your_kraken_secret
OKX_API_KEY=your_okx_key
OKX_API_SECRET=your_okx_secret
OKX_PASSPHRASE=your_okx_passphrase

# === AI ===
ANTHROPIC_API_KEY=sk-ant-your-key
CRYPTOPANIC_API_KEY=your_cryptopanic_key

# === Environment ===
ENV=development

# === Overrides (optional) ===
# KERYXFLOW_MODE=paper
# KERYXFLOW_LOG_LEVEL=DEBUG
# KERYXFLOW_DB_URL=sqlite+aiosqlite:///data/keryxflow.db
```

## Complete `settings.toml` Example

```toml
[system]
exchange = "binance"
mode = "paper"
symbols = ["BTC/USDT", "ETH/USDT"]
base_currency = "USDT"
log_level = "INFO"

[risk]
model = "fixed_fractional"
risk_per_trade = 0.01
max_daily_drawdown = 0.05
max_open_positions = 3
min_risk_reward = 1.5
stop_loss_type = "atr"
atr_multiplier = 2.0
trailing_stop_enabled = true
trailing_stop_pct = 0.02
trailing_activation_pct = 0.01

[oracle]
indicators = ["rsi", "macd", "bbands", "obv", "atr", "ema"]
llm_enabled = true
llm_model = "claude-sonnet-4-20250514"
analysis_interval = 300
news_enabled = true

[agent]
enabled = false
cycle_interval = 60
fallback_to_technical = true

[hermes]
refresh_rate = 1.0
theme = "cyberpunk"

[database]
url = "sqlite+aiosqlite:///data/keryxflow.db"

[live]
require_confirmation = true
min_paper_trades = 30
max_position_value = 1000.0

[notifications]
telegram_enabled = false
discord_enabled = false

[api]
enabled = false
host = "127.0.0.1"
port = 8080
```

## Validation

Settings are validated on startup using Pydantic:

- **Range validation**: Numeric values must be within allowed ranges (e.g., `risk_per_trade` must be 0.001–0.1)
- **Type validation**: Values must match expected types
- **Literal validation**: Enum-like fields only accept listed values (e.g., `mode` must be `paper`, `live`, or `demo`)
- **Required fields**: API keys are validated when features are used, not at startup

Invalid configuration prevents startup with a clear error message.

## Security Best Practices

1. **Never commit `.env`** — It's in `.gitignore` by default
2. **Use minimal API permissions** — Exchange keys should only have trading permissions (no withdrawal)
3. **Start with paper mode** — Always test with simulated money first
4. **Set `require_confirmation = true`** for live trading
5. **Set a bearer token** for the API server in production (`KERYXFLOW_API_TOKEN`)
