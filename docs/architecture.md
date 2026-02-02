# KeryxFlow Architecture

This document describes the system architecture, module interactions, and design principles.

## Overview

KeryxFlow is built as a modular, event-driven trading system with 7 distinct layers:

```
┌─────────────────────────────────────────────────────────────┐
│                      HERMES (Interface)                      │
│         Terminal UI - Real-time Charts - System Status       │
├─────────────────────────────────────────────────────────────┤
│                   TRADING ENGINE (Orchestrator)              │
│      OHLCV Buffer - Signal Flow - Order Execution Loop       │
├─────────────────────────────────────────────────────────────┤
│                      ORACLE (Intelligence)                   │
│    Technical Analysis - News Feeds - Claude LLM Brain        │
├─────────────────────────────────────────────────────────────┤
│                      AEGIS (Risk & Math)                     │
│    Position Sizing - Risk Manager - Circuit Breaker          │
├─────────────────────────────────────────────────────────────┤
│                      EXCHANGE (Connectivity)                 │
│     Binance API - Paper Trading - Live Safeguards            │
├─────────────────────────────────────────────────────────────┤
│                    NOTIFICATIONS (Alerts)                    │
│           Telegram - Discord - Event Subscriptions           │
├─────────────────────────────────────────────────────────────┤
│                     BACKTESTER (Validation)                  │
│     Historical Replay - Performance Metrics - Reports        │
├─────────────────────────────────────────────────────────────┤
│                     OPTIMIZER (Tuning)                       │
│    Parameter Grid - Grid Search - Sensitivity Analysis       │
├─────────────────────────────────────────────────────────────┤
│                        CORE (Foundation)                     │
│    Event Bus - Database - Logging - Models - Configuration   │
└─────────────────────────────────────────────────────────────┘
```

## Design Principles

### 1. Event-Driven Communication

Modules communicate via an async event bus, not direct method calls. This provides:

- **Loose coupling**: Modules don't need to know about each other
- **Testability**: Easy to mock events for testing
- **Extensibility**: New modules can subscribe to existing events

```python
# Publishing an event
await event_bus.publish(Event(
    type=EventType.SIGNAL_GENERATED,
    data={"symbol": "BTC/USDT", "signal_type": "long"}
))

# Subscribing to events
event_bus.subscribe(EventType.SIGNAL_GENERATED, self._on_signal)
```

### 2. Async-First

All I/O operations are async to avoid blocking the event loop:

```python
async def fetch_price(symbol: str) -> float:
    ticker = await self.exchange.fetch_ticker(symbol)
    return ticker["last"]
```

### 3. Configuration Over Hardcoding

All parameters are configurable via `settings.toml` or environment variables:

```python
risk_per_trade = settings.risk.risk_per_trade  # Not hardcoded 0.01
```

### 4. Safety by Design

Risk management (Aegis) must approve every order before execution. No shortcuts.

---

## Module Details

### Core (`keryxflow/core/`)

Foundation layer providing shared infrastructure.

| File | Purpose |
|------|---------|
| `events.py` | Async event bus (pub/sub) |
| `database.py` | SQLite with SQLModel (async) |
| `models.py` | Data models (Trade, Signal, Position) |
| `logging.py` | Structured logging with structlog |
| `engine.py` | TradingEngine orchestrator |
| `repository.py` | Trade persistence |
| `safeguards.py` | Live trading safety checks |
| `glossary.py` | Trading term definitions |

**Event Types:**

| Category | Events |
|----------|--------|
| Price | `PRICE_UPDATE`, `OHLCV_UPDATE` |
| Signal | `SIGNAL_GENERATED`, `SIGNAL_VALIDATED`, `SIGNAL_REJECTED` |
| Order | `ORDER_REQUESTED`, `ORDER_APPROVED`, `ORDER_REJECTED`, `ORDER_FILLED` |
| Position | `POSITION_OPENED`, `POSITION_UPDATED`, `POSITION_CLOSED` |
| Risk | `RISK_ALERT`, `CIRCUIT_BREAKER_TRIGGERED`, `DRAWDOWN_WARNING` |
| System | `SYSTEM_STARTED`, `SYSTEM_STOPPED`, `SYSTEM_PAUSED`, `PANIC_TRIGGERED` |

---

### Trading Engine (`keryxflow/core/engine.py`)

Central orchestrator that coordinates the trading loop.

```
Price Update → OHLCV Buffer → Oracle (Signal) → Aegis (Approval) → Paper Engine (Order)
```

**Components:**

- **OHLCVBuffer**: Aggregates price updates into 1-minute candles
- **Signal Flow**: Triggers Oracle analysis at configurable intervals
- **Order Loop**: Routes signals through Aegis approval to execution

**Key Methods:**

```python
class TradingEngine:
    async def start() -> None          # Start the engine
    async def stop() -> None           # Stop gracefully
    async def _run_analysis() -> None  # Generate signals
    async def _handle_signal() -> None # Process signal → order
```

---

### Hermes (`keryxflow/hermes/`)

Terminal User Interface built with [Textual](https://textual.textualize.io/).

| File | Purpose |
|------|---------|
| `app.py` | Main TUI application |
| `theme.tcss` | CSS styling |
| `onboarding.py` | First-run wizard |
| `widgets/` | UI components |

**Widgets:**

| Widget | Purpose |
|--------|---------|
| `ChartWidget` | ASCII price chart with indicators |
| `PositionsWidget` | Open positions with PnL |
| `OracleWidget` | Market context and signals |
| `AegisWidget` | Risk status and circuit breaker |
| `StatsWidget` | Trading statistics |
| `LogsWidget` | Activity log |
| `HelpModal` | Glossary and keyboard shortcuts |

**Keyboard Shortcuts:**

| Key | Action |
|-----|--------|
| `q` | Quit |
| `p` | Panic - close all positions |
| `Space` | Pause/Resume trading |
| `l` | Toggle logs |
| `s` | Cycle symbols |
| `?` | Help |

---

### Oracle (`keryxflow/oracle/`)

Intelligence layer combining quantitative and cognitive analysis.

| File | Purpose |
|------|---------|
| `technical.py` | Technical indicators (RSI, MACD, BBands, etc.) |
| `feeds.py` | News aggregation (RSS, CryptoPanic) |
| `brain.py` | LLM integration (Claude) |
| `signals.py` | Signal generation |

**Signal Generation Flow:**

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Technical   │───▶│    News      │───▶│     LLM      │
│  Analysis    │    │  Aggregator  │    │    Brain     │
└──────────────┘    └──────────────┘    └──────────────┘
       │                   │                   │
       └───────────────────┴───────────────────┘
                           │
                           ▼
                   ┌──────────────┐
                   │   Signal     │
                   │  Generator   │
                   └──────────────┘
```

**Technical Indicators:**

| Indicator | Purpose |
|-----------|---------|
| RSI | Overbought/oversold detection |
| MACD | Trend momentum |
| Bollinger Bands | Volatility and price extremes |
| OBV | Volume confirmation |
| ATR | Volatility measurement |
| EMA | Trend alignment (9, 21, 50, 200) |

**Signal Types:**

| Type | Action |
|------|--------|
| `LONG` | Open long position |
| `SHORT` | Open short position |
| `CLOSE_LONG` | Close long position |
| `CLOSE_SHORT` | Close short position |
| `NO_ACTION` | Wait |

---

### Aegis (`keryxflow/aegis/`)

Risk management layer. Every order must be approved before execution.

| File | Purpose |
|------|---------|
| `quant.py` | Mathematical calculations |
| `risk.py` | Order approval/rejection |
| `circuit.py` | Circuit breaker (emergency stop) |
| `profiles.py` | Risk profiles (conservative, balanced, aggressive) |

**Approval Checks:**

| Check | Rejection Condition |
|-------|---------------------|
| Position Size | Exceeds max position value |
| Open Positions | Exceeds max concurrent positions |
| Daily Drawdown | Exceeds max daily loss |
| Risk/Reward | Below minimum R:R ratio |
| Symbol | Not in whitelist |
| Stop Loss | Missing required stop loss |

**Circuit Breaker Triggers:**

| Trigger | Default |
|---------|---------|
| Daily drawdown | 5% |
| Total drawdown | 10% |
| Consecutive losses | 5 |
| Rapid losses | 3 in 1 hour |

---

### Exchange (`keryxflow/exchange/`)

Connectivity layer for exchange interactions.

| File | Purpose |
|------|---------|
| `client.py` | CCXT wrapper for Binance |
| `paper.py` | Paper trading simulation |
| `orders.py` | Order management abstraction |

**Trading Modes:**

| Mode | Description |
|------|-------------|
| `paper` | Simulated trading (default) |
| `live` | Real money (requires safeguards) |

**Paper Trading Features:**

- Virtual balance management
- Position tracking with PnL
- Slippage simulation
- Panic mode (close all)

---

### Notifications (`keryxflow/notifications/`)

Alert system for trade notifications.

| File | Purpose |
|------|---------|
| `telegram.py` | Telegram Bot API |
| `discord.py` | Discord Webhook |
| `manager.py` | Notification coordinator |

**Notification Events:**

| Event | Notification |
|-------|--------------|
| Order filled | Trade execution details |
| Circuit breaker | Emergency stop alert |
| Daily summary | End of day report |
| System error | Error details |

---

### Backtester (`keryxflow/backtester/`)

Historical strategy validation.

| File | Purpose |
|------|---------|
| `data.py` | OHLCV data loading |
| `engine.py` | Backtest simulation |
| `report.py` | Performance reports |
| `runner.py` | CLI interface |

**Metrics Calculated:**

| Metric | Description |
|--------|-------------|
| Total Return | Percentage gain/loss |
| Win Rate | Winning trades percentage |
| Profit Factor | Gross profit / gross loss |
| Max Drawdown | Largest peak-to-trough decline |
| Sharpe Ratio | Risk-adjusted return |
| Expectancy | Average profit per trade |

---

### Optimizer (`keryxflow/optimizer/`)

Parameter optimization via grid search.

| File | Purpose |
|------|---------|
| `grid.py` | Parameter combinations |
| `engine.py` | Optimization loop |
| `comparator.py` | Result analysis |
| `report.py` | Optimization reports |
| `runner.py` | CLI interface |

**Optimizable Parameters:**

| Category | Parameters |
|----------|------------|
| Oracle | rsi_period, macd_fast, macd_slow, bbands_std |
| Risk | risk_per_trade, min_risk_reward, atr_multiplier |

---

## Data Flow

### Trading Loop

```
1. ExchangeClient fetches prices
          │
          ▼
2. Prices published to EventBus
          │
          ▼
3. TradingEngine aggregates OHLCV
          │
          ▼
4. Oracle generates signal
          │
          ▼
5. Aegis approves/rejects order
          │
          ▼
6. PaperEngine/LiveExchange executes
          │
          ▼
7. Notifications sent (if enabled)
```

### Event Flow Example

```python
# Price update arrives
Event(type=PRICE_UPDATE, data={"symbol": "BTC/USDT", "price": 67000})

# Oracle generates signal
Event(type=SIGNAL_GENERATED, data={"symbol": "BTC/USDT", "signal_type": "long"})

# Aegis approves
Event(type=ORDER_APPROVED, data={"symbol": "BTC/USDT", "side": "buy"})

# Order filled
Event(type=ORDER_FILLED, data={"symbol": "BTC/USDT", "price": 67050})
```

---

## Database Schema

SQLite database with SQLModel (async).

### Tables

| Table | Purpose |
|-------|---------|
| `user_profiles` | User preferences and settings |
| `trades` | Trade history |
| `daily_stats` | Daily performance metrics |
| `paper_balances` | Paper trading balances |
| `paper_positions` | Paper trading positions |

---

## File Structure

```
keryxflow/
├── keryxflow/
│   ├── __init__.py          # Version
│   ├── main.py               # Entrypoint
│   ├── config.py             # Configuration
│   ├── core/
│   │   ├── engine.py         # TradingEngine
│   │   ├── events.py         # Event bus
│   │   ├── database.py       # SQLite
│   │   ├── models.py         # Data models
│   │   ├── repository.py     # Trade persistence
│   │   ├── safeguards.py     # Live trading checks
│   │   ├── logging.py        # Structured logging
│   │   └── glossary.py       # Term definitions
│   ├── hermes/
│   │   ├── app.py            # TUI application
│   │   ├── theme.tcss        # CSS styling
│   │   ├── onboarding.py     # First-run wizard
│   │   └── widgets/          # UI components
│   ├── oracle/
│   │   ├── technical.py      # Technical analysis
│   │   ├── feeds.py          # News aggregation
│   │   ├── brain.py          # LLM integration
│   │   └── signals.py        # Signal generation
│   ├── aegis/
│   │   ├── quant.py          # Math engine
│   │   ├── risk.py           # Risk manager
│   │   ├── circuit.py        # Circuit breaker
│   │   └── profiles.py       # Risk profiles
│   ├── exchange/
│   │   ├── client.py         # CCXT wrapper
│   │   ├── paper.py          # Paper trading
│   │   └── orders.py         # Order management
│   ├── notifications/
│   │   ├── telegram.py       # Telegram
│   │   ├── discord.py        # Discord
│   │   └── manager.py        # Coordinator
│   ├── backtester/
│   │   ├── data.py           # Data loading
│   │   ├── engine.py         # Backtest engine
│   │   ├── report.py         # Reports
│   │   └── runner.py         # CLI
│   └── optimizer/
│       ├── grid.py           # Parameter grid
│       ├── engine.py         # Optimization
│       ├── comparator.py     # Analysis
│       ├── report.py         # Reports
│       └── runner.py         # CLI
├── tests/                    # Mirror structure
├── docs/                     # Documentation
├── settings.toml             # Configuration
└── pyproject.toml            # Dependencies
```

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.12+ |
| Package Manager | Poetry |
| Exchange API | ccxt (Binance) |
| Database | SQLModel + aiosqlite |
| Analysis | numpy, pandas, pandas-ta |
| AI | LangChain + Anthropic Claude |
| Interface | Textual |
| Logging | structlog |
| Testing | pytest, pytest-asyncio |
| Linting | ruff |
