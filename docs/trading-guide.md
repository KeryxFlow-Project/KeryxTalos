# KeryxFlow Trading Guide

The complete reference for how trading works in KeryxFlow — from signal generation through order execution, risk management, memory, and reflection.

## Trading Loop

```
Price Update → OHLCV Buffer → Memory Context → Oracle (Signal) → Aegis (Approval) → Execute (Order) → Memory Record
```

1. **Prices** arrive from the exchange in real-time
2. **Oracle** analyzes the market and generates signals
3. **Aegis** validates signals against risk rules
4. **Execute** places orders (paper or live)
5. **Memory** records the trade for future learning

---

## Trading Modes

### Paper Trading (Default)

Simulated trading with virtual money. No real funds are used.

- Starts with $10,000 USDT virtual balance
- Tracks positions with realistic PnL
- Simulates slippage (0.1%)
- Full trading history persisted in SQLite

### Live Trading

Real money trading on Binance or Bybit.

**Requirements:**
- 30+ paper trades completed
- Minimum 100 USDT balance
- API keys configured
- Explicit confirmation

**Safety:** All trades require Aegis approval, circuit breaker protects against large losses, panic button closes all positions instantly.

---

## Signal Generation (Oracle)

Oracle combines multiple analysis methods to generate trading signals. The module lives in `keryxflow/oracle/`.

### Technical Analysis

The `TechnicalAnalyzer` (`keryxflow/oracle/technical.py`) computes indicators from OHLCV data:

| Indicator | What It Measures | Signal |
|-----------|------------------|--------|
| **RSI** | Overbought/Oversold | Buy when <30, Sell when >70 |
| **MACD** | Trend Momentum | Buy on bullish crossover |
| **Bollinger Bands** | Volatility & Extremes | Buy at lower band |
| **OBV** | Volume Confirmation | Confirms trend direction |
| **ATR** | Volatility | Used for stop loss sizing |
| **EMA** | Trend Alignment | Multiple timeframe confirmation |

### LLM Analysis (Claude)

When `oracle.llm_enabled = true`, Claude AI provides:
- Market context interpretation
- News sentiment validation
- Signal confirmation or veto
- Risk factor identification

**LLM Can Veto:** If technical says BUY but LLM is bearish → NO_ACTION, and vice versa.

### Signal Combination

Final signal is a weighted combination:
- Technical analysis: 60%
- LLM analysis: 40%

### Multi-Timeframe Analysis (MTF)

When enabled, Oracle analyzes multiple timeframes to improve signal quality.

```toml
[oracle.mtf]
enabled = true
timeframes = ["15m", "1h", "4h"]
primary_timeframe = "1h"
filter_timeframe = "4h"
min_filter_confidence = 0.5
```

| Timeframe | Role | Weight |
|-----------|------|--------|
| 15m | Entry timing, momentum | 20% |
| 1h | Primary signal generation | 50% |
| 4h | Trend filter, bias | 30% |

LONG signals only pass if the 4h trend is bullish or neutral. SHORT signals only pass if bearish or neutral.

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

Every order must pass Aegis validation before execution. The module lives in `keryxflow/aegis/`.

### Immutable Guardrails

The `TradingGuardrails` class (`keryxflow/aegis/guardrails.py`) is a frozen dataclass with hardcoded safety limits that cannot be modified at runtime:

| Guardrail | Limit | Purpose |
|-----------|-------|---------|
| `MAX_POSITION_SIZE_PCT` | 10% | Single position cap |
| `MAX_TOTAL_EXPOSURE_PCT` | 50% | Total portfolio exposure |
| `MIN_CASH_RESERVE_PCT` | 20% | Minimum cash reserve |
| `MAX_LOSS_PER_TRADE_PCT` | 2% | Per-trade risk cap |
| `MAX_DAILY_LOSS_PCT` | 5% | Daily circuit breaker trigger |
| `MAX_WEEKLY_LOSS_PCT` | 10% | Weekly loss halt |
| `MAX_TOTAL_DRAWDOWN_PCT` | 20% | Maximum drawdown from peak |
| `CONSECUTIVE_LOSSES_HALT` | 5 | Halt after 5 losses |
| `MAX_TRADES_PER_HOUR` | 10 | Rate limiting |
| `MAX_TRADES_PER_DAY` | 50 | Rate limiting |

### Position Sizing

The `QuantEngine.position_size()` method (`keryxflow/aegis/quant.py`) uses fixed fractional sizing:

```
quantity = (balance × risk_per_trade) / |entry_price - stop_loss|
```

**Example:** With $10,000 balance, 1% risk, entry at $67,000 and stop at $66,000:

```
quantity = ($10,000 × 0.01) / |$67,000 - $66,000| = $100 / $1,000 = 0.1 BTC
```

**Aggregate Risk Protection:** The guardrails layer tracks aggregate portfolio risk. Multiple positions are evaluated together — if 3 positions each risking 2% would total 6%, the third position is rejected because it exceeds the 5% daily loss limit.

### Approval Checks

The `RiskManager.approve_order()` method (`keryxflow/aegis/risk.py`) validates:

| Check | Rule | Rejection Reason |
|-------|------|------------------|
| Position Size | ≤ max_position_value | "Position too large" |
| Open Positions | < max_open_positions | "Too many open positions" |
| Daily Drawdown | < max_daily_drawdown | "Daily loss limit reached" |
| Risk/Reward | ≥ min_risk_reward | "R:R ratio too low" |
| Symbol | In whitelist | "Symbol not allowed" |
| Stop Loss | Present | "Stop loss required" |

### Circuit Breaker

The `CircuitBreaker` class (`keryxflow/aegis/circuit.py`) automatically halts trading:

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

1. Signal approved by Aegis
2. `PaperTradingEngine` (`keryxflow/exchange/paper.py`) creates virtual position
3. Entry price recorded with simulated slippage (0.1%)
4. Position tracked until exit

### Live Trading

1. Signal approved by Aegis
2. `ExchangeClient` submits market order to exchange
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

### Exit

Positions are closed when:
1. **Stop Loss Hit** — Price reaches stop level
2. **Take Profit Hit** — Price reaches target
3. **Exit Signal** — Oracle generates CLOSE signal
4. **Manual Exit** — User closes position
5. **Panic Mode** — All positions closed instantly

---

## Trailing Stop-Loss

The `TrailingStopManager` (`keryxflow/aegis/trailing.py`) automatically follows price in your favor.

### How It Works

```
Entry: $60,000  →  Price rises to $65,000  →  Stop trails upward
Stop:  $58,800     Stop moves to: $63,700     (always 2% below peak)
```

1. Initial stop is placed at entry
2. As price moves in your favor, the stop ratchets up (longs) or down (shorts)
3. The stop never moves against you — it only tightens
4. When price reverses and hits the trailing stop, the position is closed

### Configuration

```toml
[risk]
trailing_stop_enabled = true
trailing_stop_type = "percentage"       # "percentage" or "atr"
trailing_stop_percentage = 0.02         # 2% trailing distance
trailing_stop_atr_multiplier = 2.0      # ATR multiplier (when type = "atr")
```

Or via environment variables:

```bash
KERYXFLOW_RISK_TRAILING_STOP_ENABLED=true
KERYXFLOW_RISK_TRAILING_STOP_PCT=2.0
KERYXFLOW_RISK_TRAILING_ACTIVATION_PCT=1.0
```

### Break-Even Logic

Automatically moves your stop to entry price after reaching a configurable profit threshold:

```toml
[risk]
breakeven_enabled = true
breakeven_trigger_pct = 0.01   # Move stop to entry after 1% profit
```

**Priority:** Break-even fires first, then trailing takes over.

**Events:** `STOP_LOSS_TRAILED` (stop level moved up), `STOP_LOSS_BREAKEVEN` (stop moved to entry price).

---

## Memory System

The Memory module (`keryxflow/memory/`) records trade context for learning.

### Episodic Memory

Records complete trade episodes with full context:

```python
from keryxflow.memory.manager import get_memory_manager

memory = get_memory_manager()

# Build context for a trading decision
context = await memory.build_context_for_decision(
    symbol="BTC/USDT",
    technical_context={"trend": "bullish", "rsi": 45},
)

# Record trade entry
episode_id = await memory.record_trade_entry(
    trade_id="trade_001",
    symbol="BTC/USDT",
    side="buy",
    entry_price=50000.0,
    quantity=0.1,
    reasoning="EMA crossover with bullish MACD confirmation",
)

# Record trade exit
await memory.record_trade_exit(
    episode_id=episode_id,
    exit_price=51500.0,
    outcome="win",
    pnl=150.0,
    lessons_learned="EMA crossover signals are reliable in trending markets",
)
```

### Semantic Memory

Stores trading rules and market patterns with performance tracking:
- **TradingRule** — Rules with source (learned/user/backtest) and success_rate
- **MarketPattern** — Patterns with win_rate and validation status

---

## Reflection & Learning

The Reflection Engine (`keryxflow/agent/reflection.py`) generates insights from trading activity.

### Post-Mortem

Single trade analysis with lessons learned. Runs after each trade closes.

```python
from keryxflow.agent import get_reflection_engine

engine = get_reflection_engine()
result = await engine.post_mortem(episode)
```

### Daily Reflection

End-of-day summary with key lessons, mistakes, and recommendations. Scheduled at 23:00 UTC.

```python
daily = await engine.daily_reflection()
```

### Weekly Reflection

Weekly review with patterns identified, rules created/updated. Scheduled Sunday 23:30 UTC.

```python
weekly = await engine.weekly_reflection()
```

When AI is disabled, heuristic-based fallback methods provide basic reflections without LLM calls.

---

## Notifications

Real-time alerts for trades, circuit breaker events, and daily summaries.

### Discord

```bash
KERYXFLOW_NOTIFY_DISCORD_ENABLED=true
KERYXFLOW_NOTIFY_DISCORD_WEBHOOK="https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN"
```

### Telegram

```bash
KERYXFLOW_NOTIFY_TELEGRAM_ENABLED=true
KERYXFLOW_NOTIFY_TELEGRAM_TOKEN="123456:ABC-DEF..."
KERYXFLOW_NOTIFY_TELEGRAM_CHAT_ID="your-chat-id"
```

### Notification Events

```toml
[notify]
notify_on_trade = true
notify_on_circuit_breaker = true
notify_daily_summary = true
notify_on_error = true
```

---

## Multi-Exchange Support

KeryxFlow supports Binance and Bybit through the CCXT library.

### Configuration

```toml
[system]
exchange = "bybit"   # "binance" (default) or "bybit"
```

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

Both exchanges use the CCXT unified API, so trading behavior is consistent. Paper trading works identically regardless of exchange selection.

---

## Cognitive Agent Mode

When enabled (`KERYXFLOW_AGENT_ENABLED=true`), the `CognitiveAgent` replaces the standard `SignalGenerator` in the trading loop.

The agent uses Claude's Tool Use API to autonomously:
1. **Perceive** — Read market data via perception tools
2. **Remember** — Query episodic and semantic memory
3. **Analyze** — Calculate indicators and position sizes
4. **Decide** — Make trading decisions (HOLD, ENTRY_LONG, ENTRY_SHORT, EXIT)
5. **Validate** — Check against Aegis guardrails
6. **Execute** — Place orders via guarded execution tools
7. **Learn** — Record outcomes for future improvement

```bash
KERYXFLOW_AGENT_ENABLED=true
KERYXFLOW_AGENT_MODEL=claude-sonnet-4-20250514
KERYXFLOW_AGENT_CYCLE_INTERVAL=60
KERYXFLOW_AGENT_FALLBACK_TO_TECHNICAL=true
```

If Claude API fails, the agent falls back to technical signals automatically.

---

## Keyboard Shortcuts (TUI)

| Key | Action |
|-----|--------|
| `A` | Toggle Agent (start/pause/resume) |
| `P` | Panic — emergency stop |
| `Space` | Pause/Resume trading |
| `Q` | Quit |
| `L` | Toggle logs panel |
| `S` | Switch symbol |
| `?` | Help |

---

## Troubleshooting

### No Signals Generated

Market is ranging, indicators are neutral, or LLM vetoed the signal. This is normal — the system waits for clear opportunities.

### Signal Rejected by Aegis

Check the rejection reason in logs. Common causes: too many open positions, daily drawdown limit reached, position size too large, R:R ratio too low.

### Circuit Breaker Triggered

Stop trading for the day. Review what went wrong. Wait for cooldown (1 hour). Reset only if you understand the issue.

### No Price Updates

Check exchange API status. Verify network connectivity. Restart the application.
