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

> **Known Limitation:** The current position sizing model calculates risk per trade in isolation.
> With multiple concurrent positions (up to `max_open_positions`), total portfolio exposure can
> exceed expected limits. For example, 3 positions each risking 2% could result in 6% total risk
> if all hit stop loss simultaneously. See [Issue #9](https://github.com/KeryxFlow-Project/KeryxFlow/issues/9)
> for ongoing improvements.

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
| **Isolated position risk** | Multiple positions can compound losses beyond `risk_per_trade` | [Issue #9](https://github.com/KeryxFlow-Project/KeryxFlow/issues/9) |
| **No correlation analysis** | Correlated assets (BTC/ETH) may move together, amplifying risk | Planned |
| **Fixed rule-based signals** | Oracle uses predetermined indicator thresholds | See Future Roadmap |
| **No memory between sessions** | System doesn't learn from past trades | See Future Roadmap |
| **Single exchange** | Binance only - if unavailable, system stops | Planned |
| **Latency for scalping** | ~1-3s signal generation not suitable for HFT | By design (swing trading focus) |

**Mitigations:**
- Use conservative `risk_per_trade` settings (0.5-1%)
- Limit `max_open_positions` to 2-3
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

**Key Proposed Changes:**

| Feature | Current | Future |
|---------|---------|--------|
| Decision maker | Fixed indicator rules | Claude with tools |
| Memory | None | Episodic + Semantic + Procedural |
| Learning | Manual parameter tuning | Continuous from trades |
| Guardrails | Aegis approval checks | Immutable code limits |

**Proposed Guardrails (hardcoded, AI cannot bypass):**
- Max 10% capital per position
- Max 50% total exposure
- Max 2% loss per trade
- Max 5% daily loss
- Halt after 5 consecutive losses

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
