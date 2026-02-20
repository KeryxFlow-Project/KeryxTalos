# KeryxFlow Trading Guide

This guide explains how the trading system works, from signal generation to order execution.

## How Trading Works

KeryxFlow follows a systematic approach to trading:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   PRICES    │────▶│   ORACLE    │────▶│    AEGIS    │────▶│   EXECUTE   │
│ Real-time   │     │ "Should we  │     │ "Is it safe │     │  "Do the    │
│   updates   │     │   trade?"   │     │  to trade?" │     │   trade"    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

1. **Prices** arrive from the exchange in real-time
2. **Oracle** analyzes the market and generates signals
3. **Aegis** validates signals against risk rules
4. **Execute** places orders (paper or live)

---

## Trading Modes

### Paper Trading (Default)

Simulated trading with virtual money. No real funds are used.

**Features:**
- Starts with $10,000 USDT virtual balance
- Tracks positions with realistic PnL
- Simulates slippage (0.1%)
- Full trading history

**Use this to:**
- Learn how the system works
- Test strategies before going live
- Practice without risk

### Live Trading

Real money trading on Binance.

**Requirements:**
- 30+ paper trades completed
- Minimum 100 USDT balance
- API keys configured
- Explicit confirmation

**Safety Features:**
- All trades require Aegis approval
- Circuit breaker protects against large losses
- Panic button closes all positions instantly

---

## Signal Generation (Oracle)

Oracle combines multiple analysis methods to generate trading signals.

### Technical Analysis

Mathematical indicators calculated from price data:

| Indicator | What It Measures | Signal |
|-----------|------------------|--------|
| **RSI** | Overbought/Oversold | Buy when <30, Sell when >70 |
| **MACD** | Trend Momentum | Buy on bullish crossover |
| **Bollinger Bands** | Volatility & Extremes | Buy at lower band |
| **OBV** | Volume Confirmation | Confirms trend direction |
| **ATR** | Volatility | Used for stop loss sizing |
| **EMA** | Trend Alignment | Multiple timeframe confirmation |

### News Analysis

Aggregates news from multiple sources:

- **CryptoPanic** - Crypto-specific news API
- **RSS Feeds** - CoinTelegraph, Decrypt

News is analyzed for:
- Sentiment (bullish/bearish/neutral)
- Currency mentions
- Recency weighting

### LLM Analysis (Claude)

Claude AI provides:
- Market context interpretation
- News sentiment validation
- Signal confirmation or veto
- Risk factor identification

**Example LLM Output:**
```
Bias: BULLISH (75% confidence)
Action: BUY

Key Factors:
+ ETF inflows continue (+$500M this week)
+ RSI showing oversold conditions
- Regulatory concerns in EU

Recommendation: Technical setup is favorable.
ETF momentum provides fundamental support.
```

### Signal Combination

Final signal is a weighted combination:
- Technical analysis: 60%
- LLM analysis: 40%

**LLM Can Veto:**
- If technical says BUY but LLM is bearish → NO_ACTION
- If technical says SELL but LLM is bullish → NO_ACTION

### Multi-Timeframe Analysis (MTF)

When enabled, Oracle analyzes multiple timeframes to improve signal quality.

**Configuration** (`settings.toml`):
```toml
[oracle.mtf]
enabled = true
timeframes = ["15m", "1h", "4h"]
primary_timeframe = "1h"      # Main signal generation
filter_timeframe = "4h"       # Trend confirmation
min_filter_confidence = 0.5   # Minimum alignment required
```

**How MTF Works:**

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  15m (fast) │     │  1h (main)  │     │ 4h (filter) │
│  Entry      │────▶│  Signal     │────▶│  Trend      │
│  Timing     │     │  Generation │     │  Confirm    │
└─────────────┘     └─────────────┘     └─────────────┘
```

| Timeframe | Role | Weight |
|-----------|------|--------|
| 15m | Entry timing, momentum | 20% |
| 1h | Primary signal generation | 50% |
| 4h | Trend filter, bias | 30% |

**Signal Filtering:**
- LONG signals only pass if 4h trend is bullish or neutral
- SHORT signals only pass if 4h trend is bearish or neutral
- Signals against the higher timeframe trend are rejected

**Benefits:**
- Reduces false signals from noise
- Aligns entries with dominant trend
- Improves win rate at cost of fewer signals

---

## Signal Types

| Signal | Meaning | Action |
|--------|---------|--------|
| `LONG` | Buy opportunity | Open long position |
| `SHORT` | Sell opportunity | Open short position |
| `CLOSE_LONG` | Exit long | Close long position |
| `CLOSE_SHORT` | Exit short | Close short position |
| `NO_ACTION` | No clear opportunity | Wait |

### Signal Strength

| Strength | Confidence | Meaning |
|----------|------------|---------|
| Strong | 70%+ | High conviction signal |
| Moderate | 50-70% | Reasonable opportunity |
| Weak | 30-50% | Low conviction |
| None | <30% | Not actionable |

---

## Risk Management (Aegis)

Every order must pass Aegis validation before execution.

### Position Sizing

Aegis calculates position size based on:

```
Position Size = (Balance × Risk%) / (Entry - Stop Loss)
```

**Example:**
- Balance: $10,000
- Risk per trade: 1% ($100)
- Entry: $67,000
- Stop Loss: $66,000 (1.5% away)
- Position Size: $100 / $1,000 = 0.001 BTC

> **Aggregate Risk Protection (v0.11.0):** The guardrails layer now tracks aggregate portfolio risk.
> Multiple positions are evaluated together - if 3 positions each risking 2% would total 6%,
> the third position is REJECTED because it exceeds the 5% daily loss limit.
> See [Issue #9](https://github.com/KeryxFlow-Project/KeryxFlow/issues/9) (fixed in v0.11.0).

**Recommended Settings for Safety:**

| Risk Tolerance | risk_per_trade | max_open_positions | Max Theoretical Loss |
|----------------|----------------|--------------------|-----------------------|
| Conservative | 0.5% | 2 | 1% |
| Moderate | 1% | 3 | 3% |
| Aggressive | 2% | 3 | 6% |

### Approval Checks

| Check | Rule | Rejection Reason |
|-------|------|------------------|
| Position Size | ≤ max_position_value | "Position too large" |
| Open Positions | < max_open_positions | "Too many open positions" |
| Daily Drawdown | < max_daily_drawdown | "Daily loss limit reached" |
| Risk/Reward | ≥ min_risk_reward | "R:R ratio too low" |
| Symbol | In whitelist | "Symbol not allowed" |
| Stop Loss | Present | "Stop loss required" |

### Circuit Breaker

Automatic trading halt when limits are exceeded:

| Trigger | Default | Effect |
|---------|---------|--------|
| Daily drawdown | 5% | Halt trading for day |
| Total drawdown | 10% | Halt until reset |
| Consecutive losses | 5 | Halt and review |
| Rapid losses | 3 in 1 hour | Temporary halt |

**Cooldown:** 1 hour before manual reset is allowed.

---

## Order Execution

### Paper Trading

Orders are simulated immediately:

1. Signal approved by Aegis
2. Paper Engine creates virtual position
3. Entry price recorded (with slippage)
4. Position tracked until exit

### Live Trading

Orders are sent to Binance:

1. Signal approved by Aegis
2. Market order submitted
3. Fill price recorded
4. Balance and position updated

---

## Position Management

### Entry

When a LONG/SHORT signal is approved:

1. Calculate position size from risk parameters
2. Determine stop loss (ATR-based or fixed)
3. Calculate take profit (R:R ratio)
4. Execute order

### Monitoring

Active positions are tracked for:

- Current price vs entry
- Unrealized PnL
- Distance to stop/target
- Time in position

### Exit

Positions are closed when:

1. **Stop Loss Hit** - Price reaches stop level
2. **Take Profit Hit** - Price reaches target
3. **Exit Signal** - Oracle generates CLOSE signal
4. **Manual Exit** - User closes position
5. **Panic Mode** - All positions closed instantly

---

## Trailing Stop-Loss

A trailing stop-loss automatically follows price in your favor, locking in profit while keeping downside protection.

### How It Works

```
Entry: $60,000  →  Price rises to $65,000  →  Stop trails upward
Stop:  $58,800     Stop moves to: $63,700     (always 2% below peak)
```

1. **Initial stop** is placed at entry using ATR or fixed percentage (same as regular stop)
2. As price moves in your favor, the stop **ratchets up** (for longs) or **down** (for shorts)
3. The stop never moves against you — it only tightens
4. When price reverses and hits the trailing stop, the position is closed

### Configuration

Configure trailing stops in `settings.toml` or via environment variables:

```toml
[risk]
trailing_stop_enabled = true
trailing_stop_type = "percentage"   # "percentage" or "atr"
trailing_stop_percentage = 0.02     # 2% trailing distance
trailing_stop_atr_multiplier = 2.0  # ATR multiplier (when type = "atr")
```

| Setting | Default | Description |
|---------|---------|-------------|
| `trailing_stop_enabled` | `false` | Enable trailing stop-loss |
| `trailing_stop_type` | `"percentage"` | `"percentage"` or `"atr"` |
| `trailing_stop_percentage` | `0.02` | Trailing distance as decimal (2%) |
| `trailing_stop_atr_multiplier` | `2.0` | ATR periods for trailing distance |

### Break-Even Logic

The break-even feature automatically moves your stop to the entry price once the trade reaches a configurable profit threshold, ensuring you don't turn a winner into a loser.

```toml
[risk]
breakeven_enabled = true
breakeven_trigger_pct = 0.01   # Move stop to entry after 1% profit
```

**How break-even works:**

1. Trade opens at $60,000 with stop at $58,800
2. Price rises 1% to $60,600 → **break-even triggers**
3. Stop moves from $58,800 to $60,000 (entry price)
4. If trailing is also enabled, the stop continues trailing from there

**Priority:** Break-even fires first, then trailing takes over once the stop has been moved to entry.

---

## Notifications Setup

KeryxFlow sends real-time alerts for trades, circuit breaker events, and daily summaries.

### Discord Webhook

1. In your Discord server, go to **Server Settings → Integrations → Webhooks**
2. Click **New Webhook**, choose a channel, and copy the webhook URL
3. Add to `.env`:

```bash
KERYXFLOW_NOTIFY_DISCORD_ENABLED=true
KERYXFLOW_NOTIFY_DISCORD_WEBHOOK="https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN"
```

### Telegram Bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram and create a new bot with `/newbot`
2. Copy the bot token
3. Start a chat with your bot and send any message
4. Get your chat ID by visiting `https://api.telegram.org/bot<TOKEN>/getUpdates`
5. Add to `.env`:

```bash
KERYXFLOW_NOTIFY_TELEGRAM_ENABLED=true
KERYXFLOW_NOTIFY_TELEGRAM_TOKEN="123456:ABC-DEF..."
KERYXFLOW_NOTIFY_TELEGRAM_CHAT_ID="your-chat-id"
```

### Notification Events

Control which events trigger notifications:

```toml
[notify]
notify_on_trade = true             # Order filled alerts
notify_on_circuit_breaker = true   # Circuit breaker triggers
notify_daily_summary = true        # End-of-day summary
notify_on_error = true             # System errors
```

### Test Notifications

Verify your setup:

```bash
poetry run pytest tests/test_notifications/
```

---

## API Monitoring

KeryxFlow provides a REST API and WebSocket for monitoring trading activity programmatically.

### Starting the API Server

```bash
poetry run uvicorn keryxflow.api:app --host 0.0.0.0 --port 8000
```

### REST API

Query trading state via HTTP:

```bash
# Get engine status
curl http://localhost:8000/api/status

# Get open positions
curl http://localhost:8000/api/positions

# Get account balance
curl http://localhost:8000/api/balance

# Get trade history
curl http://localhost:8000/api/trades

# Emergency: close all positions
curl -X POST http://localhost:8000/api/panic
```

### WebSocket (Real-Time Events)

Connect to the WebSocket for live event streaming:

```python
import asyncio
import websockets
import json

async def monitor():
    async with websockets.connect("ws://localhost:8000/ws/events") as ws:
        async for message in ws:
            event = json.loads(message)
            print(f"[{event['type']}] {event['data']}")

asyncio.run(monitor())
```

Events streamed include: `PRICE_UPDATE`, `SIGNAL_GENERATED`, `ORDER_FILLED`, `POSITION_OPENED`, `POSITION_CLOSED`, `CIRCUIT_BREAKER_TRIGGERED`.

---

## Multi-Exchange Support

KeryxFlow supports multiple exchanges through the CCXT library. You can switch between Binance and Bybit.

### Switching Exchanges

Set the exchange in `settings.toml`:

```toml
[system]
exchange = "bybit"   # "binance" (default) or "bybit"
```

Or via environment variable:

```bash
KERYXFLOW_EXCHANGE=bybit
```

### Exchange-Specific Configuration

**Binance:**
```bash
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret
```

**Bybit:**
```bash
BYBIT_API_KEY=your_key
BYBIT_API_SECRET=your_secret
```

### Differences Between Exchanges

| Feature | Binance | Bybit |
|---------|---------|-------|
| Spot trading | Yes | Yes |
| Sandbox/Testnet | Yes | Yes |
| WebSocket feeds | Yes | Yes |
| Fee structure | Maker 0.1% / Taker 0.1% | Maker 0.1% / Taker 0.1% |

Both exchanges are accessed through the CCXT unified API, so trading behavior is consistent. Paper trading mode works identically regardless of exchange selection.

---

## Trading Statistics

KeryxFlow tracks comprehensive statistics:

| Metric | Description | Good Value |
|--------|-------------|------------|
| Win Rate | % of winning trades | >55% |
| Avg Win | Average profit on winners | Higher than Avg Loss |
| Avg Loss | Average loss on losers | Lower than Avg Win |
| Profit Factor | Gross Profit / Gross Loss | >1.5 |
| Expectancy | Average profit per trade | Positive |
| Max Drawdown | Largest peak-to-trough decline | <20% |
| Sharpe Ratio | Risk-adjusted return | >1.0 |

---

## Backtesting

Test strategies on historical data before live trading.

```bash
poetry run keryxflow-backtest \
    --symbol BTC/USDT \
    --start 2024-01-01 \
    --end 2024-06-30 \
    --timeframe 1h
```

**Output includes:**
- Total return
- Win rate
- Profit factor
- Max drawdown
- Trade list

---

## Parameter Optimization

Find optimal parameters through grid search.

```bash
poetry run keryxflow-optimize \
    --symbol BTC/USDT \
    --start 2024-01-01 \
    --end 2024-06-30 \
    --grid quick
```

**Optimizable parameters:**
- RSI period (7, 14, 21)
- Risk per trade (0.5%, 1%, 2%)
- Minimum R:R (1.0, 1.5, 2.0)

See [optimization.md](optimization.md) for details.

---

## Walk-Forward and Monte Carlo Validation

Advanced backtester validation methods help ensure your strategy is robust and not overfit to historical data.

### Walk-Forward Analysis

Walk-forward testing splits historical data into rolling in-sample (training) and out-of-sample (testing) windows to validate that optimized parameters generalize to unseen data.

```bash
poetry run keryxflow-backtest \
    --symbol BTC/USDT \
    --start 2024-01-01 \
    --end 2024-12-31 \
    --walk-forward \
    --in-sample-pct 70 \
    --steps 5
```

**How it works:**

```
|---- In-Sample (70%) ----|-- Out-of-Sample (30%) --|
        Window 1: Optimize → Test
              Window 2: Optimize → Test
                    Window 3: Optimize → Test
                          ... (rolling forward)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--in-sample-pct` | `70` | Percentage of each window used for optimization |
| `--steps` | `5` | Number of walk-forward windows |

**Output includes:**
- Per-window optimized parameters and out-of-sample performance
- Walk-forward efficiency ratio (out-of-sample / in-sample return)
- Aggregate out-of-sample equity curve

A walk-forward efficiency ratio above 0.5 suggests the strategy generalizes well.

### Monte Carlo Simulation

Monte Carlo simulation randomizes trade order and applies variations to assess the range of possible outcomes from the same strategy.

```bash
poetry run keryxflow-backtest \
    --symbol BTC/USDT \
    --start 2024-01-01 \
    --end 2024-06-30 \
    --monte-carlo \
    --simulations 1000
```

**How it works:**

1. Run a standard backtest to get the list of trades
2. Randomly shuffle trade order across N simulations
3. Calculate statistics across all simulations (percentiles for drawdown, return, etc.)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--simulations` | `1000` | Number of Monte Carlo iterations |

**Output includes:**
- Median, 5th, and 95th percentile for total return
- Worst-case max drawdown (95th percentile)
- Probability of ruin (chance of hitting max drawdown limit)
- Confidence intervals for key metrics

**Interpreting results:**
- If the 5th percentile return is still positive, the strategy is likely robust
- If the 95th percentile drawdown exceeds your risk tolerance, reduce position sizing
- Compare median Monte Carlo return to the original backtest — large gaps indicate sequence dependency

### Running Both Together

```bash
poetry run keryxflow-backtest \
    --symbol BTC/USDT \
    --start 2024-01-01 \
    --end 2024-12-31 \
    --walk-forward --steps 5 \
    --monte-carlo --simulations 1000
```

Tests for these features are in `tests/test_backtester/test_walk_forward.py` and `tests/test_backtester/test_monte_carlo.py`.

---

## Best Practices

### Starting Out

1. **Paper trade first** - At least 30 trades
2. **Start conservative** - Low risk, few positions
3. **Watch the system** - Understand each decision
4. **Review trades** - Learn from wins and losses

### Risk Management

1. **Never skip Aegis** - All trades must be approved
2. **Respect the circuit breaker** - It exists for a reason
3. **Keep positions small** - 1-2% risk per trade max
4. **Diversify symbols** - Don't put everything in one trade

### Going Live

1. **Start with small amounts** - Test with minimum size
2. **Enable notifications** - Know what's happening
3. **Check daily** - Review positions and stats
4. **Have a plan** - Know when to stop

---

## Keyboard Shortcuts

| Key | Action | When to Use |
|-----|--------|-------------|
| `p` | **Panic** | Emergency - close everything now |
| `Space` | Pause/Resume | Take a break from trading |
| `q` | Quit | Exit the application |
| `l` | Toggle logs | View activity history |
| `s` | Cycle symbol | Switch between trading pairs |
| `?` | Help | View shortcuts and glossary |

---

## Troubleshooting

### No Signals Generated

**Possible causes:**
- Market is ranging (no clear direction)
- Indicators are neutral
- LLM vetoed the signal

**Solution:** This is normal. The system waits for clear opportunities.

### Signal Rejected by Aegis

**Possible causes:**
- Too many open positions
- Daily drawdown limit reached
- Position size too large
- R:R ratio too low

**Solution:** Check the rejection reason in logs. Adjust risk settings if needed.

### Circuit Breaker Triggered

**Cause:** Loss limits exceeded.

**Solution:**
1. Stop trading for the day
2. Review what went wrong
3. Wait for cooldown (1 hour)
4. Reset only if you understand the issue

### No Price Updates

**Possible causes:**
- Exchange API issues
- Network problems
- Rate limiting

**Solution:** Check Binance status. Restart the application.

---

## Known Limitations

Current system limitations being actively addressed:

| Limitation | Impact | Status |
|------------|--------|--------|
| ~~**Isolated position risk**~~ | ~~Multiple positions can compound losses~~ | ✅ **FIXED in v0.11.0** |
| **No correlation analysis** | Correlated assets (BTC/ETH) may move together, amplifying risk | Planned |
| **Fixed rule-based signals** | Oracle uses predetermined indicator thresholds | See Future Roadmap |
| **No memory between sessions** | System doesn't learn from past trades | See Future Roadmap |
| ~~**Single exchange**~~ | ~~Binance only - if unavailable, system stops~~ | ✅ **Multi-exchange** (Binance, Bybit) |
| **Latency for scalping** | ~1-3s signal generation not suitable for HFT | By design (swing trading focus) |

**Guardrails (v0.11.0):**

The system now enforces immutable guardrails that cannot be bypassed:

| Guardrail | Limit | Effect |
|-----------|-------|--------|
| Max position size | 10% | Single position cannot exceed 10% of portfolio |
| Max total exposure | 50% | All positions combined cannot exceed 50% |
| Max loss per trade | 2% | Individual trade risk capped at 2% |
| Max daily loss | 5% | Aggregate risk across all positions capped |
| Consecutive losses | 5 | Trading halts after 5 losses in a row |

**Additional Mitigations:**
- Avoid highly correlated pairs simultaneously
- Monitor the system regularly

---

## Future Roadmap

KeryxFlow is evolving toward an **AI-First Architecture** where Claude operates autonomously within strict guardrails, rather than just validating fixed rules.

**Current State:**
```
Prices → Indicators → FIXED RULES → Signal → Claude validates
                          ↑                      ↓
                      (decides)              (ok/not ok)
```

**Future State (RFC #11):**
```
Data → Claude PERCEIVES → Claude ANALYZES → Claude DECIDES
           ↓                                    ↓
       (via tools)                      (within guardrails)
           ↓                                    ↓
Claude EXECUTES → Claude EVALUATES → Claude LEARNS
```

**Implementation Progress:**

| Phase | Status | Description |
|-------|--------|-------------|
| 1. Guardrails | ✅ **COMPLETE** | Immutable safety limits (v0.11.0) |
| 2. Memory | 🔜 Next | Episodic + Semantic + Procedural memory |
| 3. Tools | Planned | Claude tools for data and execution |
| 4. Agent | Planned | Claude as primary decision maker |
| 5. Learning | Planned | Continuous improvement from trades |

**Guardrails (Implemented in v0.11.0):**
- ✅ Max 10% capital per position
- ✅ Max 50% total exposure
- ✅ Max 2% loss per trade
- ✅ Max 5% daily loss (aggregate risk)
- ✅ Halt after 5 consecutive losses

See [Issue #11](https://github.com/KeryxFlow-Project/KeryxFlow/issues/11), `docs/ai-trading-architecture.md` for the full RFC, and `docs/plans/ai-first-implementation-plan.md` for the implementation plan.

---

## Glossary

| Term | Definition |
|------|------------|
| **Stop Loss** | Price at which to exit a losing trade |
| **Take Profit** | Price at which to exit a winning trade |
| **R:R Ratio** | Risk/Reward - potential profit vs potential loss |
| **Drawdown** | Peak-to-trough decline in account value |
| **Slippage** | Difference between expected and actual fill price |
| **Paper Trading** | Simulated trading with virtual money |
| **Circuit Breaker** | Automatic trading halt on excessive losses |
| **MTF (Multi-Timeframe)** | Analysis using multiple chart timeframes for confirmation |
| **Guardrails** | Hard limits in code that cannot be bypassed by the system |
| **Correlation** | How closely two assets move together (high = similar moves) |
| **Exposure** | Total capital at risk across all open positions |
| **Swing Trading** | Trading style holding positions for hours to days |
| **Trailing Stop** | Stop-loss that follows price in your favor, locking in profit |
| **Break-Even Stop** | Moving stop to entry price after reaching a profit threshold |
| **Walk-Forward** | Rolling optimization+testing to validate strategy robustness |
| **Monte Carlo** | Randomized simulation to estimate range of possible outcomes |
