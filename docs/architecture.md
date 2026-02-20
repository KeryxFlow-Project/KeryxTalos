# KeryxFlow Architecture

This document describes the system architecture, module interactions, and design principles.

## Overview

KeryxFlow is built as a modular, event-driven trading system with 9 distinct layers:

```
┌─────────────────────────────────────────────────────────────┐
│                      HERMES (Interface)                      │
│         Terminal UI - Real-time Charts - System Status       │
├─────────────────────────────────────────────────────────────┤
│                        API (REST & WebSocket)                │
│       FastAPI Server - REST Endpoints - WS Event Stream      │
├─────────────────────────────────────────────────────────────┤
│                   TRADING ENGINE (Orchestrator)              │
│      OHLCV Buffer - Signal Flow - Order Execution Loop       │
├─────────────────────────────────────────────────────────────┤
│                      ORACLE (Intelligence)                   │
│    Technical Analysis - News Feeds - Claude LLM Brain        │
├─────────────────────────────────────────────────────────────┤
│                      AEGIS (Risk & Math)                     │
│  Position Sizing - Risk Manager - Circuit Breaker - Trailing │
├─────────────────────────────────────────────────────────────┤
│                      EXCHANGE (Connectivity)                 │
│   Multi-Exchange Adapter - Paper Trading - Live Safeguards   │
├─────────────────────────────────────────────────────────────┤
│                    NOTIFICATIONS (Alerts)                    │
│      Discord/Telegram Webhooks - Event Subscriptions         │
├─────────────────────────────────────────────────────────────┤
│                     BACKTESTER (Validation)                  │
│  Walk-Forward - Monte Carlo - Performance Metrics - Reports  │
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
| Trailing Stop | `STOP_LOSS_TRAILED`, `STOP_LOSS_BREAKEVEN` |
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

### API (`keryxflow/api/`)

REST and WebSocket interface built with [FastAPI](https://fastapi.tiangolo.com/). Provides programmatic access to the trading engine as an alternative to the Hermes TUI.

| File | Purpose |
|------|---------|
| `server.py` | FastAPI application and lifecycle management |
| `routes.py` | REST endpoint definitions |
| `websocket.py` | WebSocket event streaming |

**Lifecycle Integration:**

The API server is started and stopped by the TradingEngine lifecycle. When the engine starts, it launches the FastAPI server in the background; when the engine stops, the server shuts down gracefully.

**REST Endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/status` | Engine status, uptime, active symbols |
| `GET` | `/api/positions` | Open positions with unrealized PnL |
| `GET` | `/api/trades` | Trade history |
| `GET` | `/api/balance` | Current balance and equity |
| `POST` | `/api/panic` | Emergency stop — close all positions |
| `POST` | `/api/pause` | Pause/resume trading |
| `GET` | `/api/agent/status` | Cognitive agent state and statistics |

**WebSocket:**

| Endpoint | Description |
|----------|-------------|
| `WS /ws/events` | Real-time event stream (price updates, signals, orders, positions) |

The WebSocket endpoint subscribes to the event bus and forwards events to connected clients as JSON messages, enabling external dashboards and monitoring tools.

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

**Trailing Stop (`aegis/trailing.py`):**

The `TrailingStopManager` automatically ratchets stop-loss levels upward as price moves in favor of an open position.

| Feature | Description |
|---------|-------------|
| Price tracking | Monitors highest price per symbol since entry |
| Stop ratcheting | Moves stop-loss up by ATR-based trail distance |
| Break-even logic | Moves stop to entry price once a configurable profit threshold is reached |
| Event integration | Publishes `STOP_LOSS_TRAILED` and `STOP_LOSS_BREAKEVEN` events |

The TrailingStopManager is integrated into the TradingEngine price loop. On each `PRICE_UPDATE`, it checks all open positions and adjusts stop-loss levels accordingly.

```python
class TrailingStopManager:
    async def on_price_update(self, symbol: str, price: float) -> None
    async def register_position(self, symbol: str, entry_price: float, stop_loss: float) -> None
    async def unregister_position(self, symbol: str) -> None
```

---

### Exchange (`keryxflow/exchange/`)

Connectivity layer for exchange interactions with a multi-exchange adapter architecture.

| File | Purpose |
|------|---------|
| `adapter.py` | `ExchangeAdapter` ABC — common interface for all exchanges |
| `client.py` | `ExchangeClient` — Binance implementation via CCXT |
| `bybit.py` | `BybitClient` — Bybit implementation via CCXT |
| `paper.py` | Paper trading simulation |
| `orders.py` | Order management abstraction |

**Multi-Exchange Architecture:**

All exchange implementations inherit from the `ExchangeAdapter` abstract base class, which defines the standard interface for fetching prices, placing orders, and managing positions.

```python
class ExchangeAdapter(ABC):
    async def fetch_ticker(self, symbol: str) -> dict
    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> list
    async def create_order(self, symbol: str, side: str, amount: float, price: float | None) -> dict
    async def cancel_order(self, order_id: str, symbol: str) -> dict
    async def fetch_balance(self) -> dict
```

The `get_exchange_adapter()` factory function selects the appropriate implementation based on the `KERYXFLOW_EXCHANGE` configuration setting (default: `binance`).

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

Event-driven alert system using Discord and Telegram webhooks.

| File | Purpose |
|------|---------|
| `telegram.py` | Telegram Bot API webhook sender |
| `discord.py` | Discord webhook sender |
| `manager.py` | `NotificationManager` — event subscriber and dispatcher |

**NotificationManager:**

The `NotificationManager` subscribes to the event bus and dispatches formatted messages to configured webhook endpoints. It listens for key trading events and sends notifications asynchronously.

**Subscribed Events:**

| Event | Notification |
|-------|--------------|
| `POSITION_OPENED` | Entry details — symbol, side, size, entry price, stop-loss |
| `POSITION_CLOSED` | Exit details — symbol, PnL, duration, exit reason |
| `ORDER_FILLED` | Trade execution details |
| `CIRCUIT_BREAKER_TRIGGERED` | Emergency stop alert |
| Daily summary | End of day report |
| System error | Error details |

**Webhook Configuration:**

```toml
[notifications]
discord_webhook_url = "https://discord.com/api/webhooks/..."
telegram_bot_token = "bot123:ABC..."
telegram_chat_id = "123456789"
enabled_events = ["POSITION_OPENED", "POSITION_CLOSED", "CIRCUIT_BREAKER_TRIGGERED"]
```

---

### Backtester (`keryxflow/backtester/`)

Historical strategy validation with walk-forward analysis and Monte Carlo simulation.

| File | Purpose |
|------|---------|
| `data.py` | OHLCV data loading |
| `engine.py` | Backtest simulation |
| `walk_forward.py` | `WalkForwardEngine` — out-of-sample validation |
| `monte_carlo.py` | `MonteCarloSimulator` — statistical analysis |
| `report.py` | Performance reports (text and HTML) |
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

**Walk-Forward Engine:**

The `WalkForwardEngine` performs out-of-sample validation by splitting historical data into rolling in-sample (training) and out-of-sample (testing) windows. This guards against overfitting by ensuring strategy parameters are validated on unseen data.

```
│◄── In-Sample (optimize) ──►│◄── Out-of-Sample (validate) ──►│
│         Window 1            │           Window 1              │
│              │◄── In-Sample ──►│◄── Out-of-Sample ──►│
│              │     Window 2    │      Window 2        │
```

**Monte Carlo Simulator:**

The `MonteCarloSimulator` runs thousands of randomized trade sequence permutations to produce statistical confidence intervals for strategy performance. Outputs include:

- Median and percentile return distributions (5th, 25th, 75th, 95th)
- Probability of ruin (drawdown exceeding threshold)
- Confidence intervals for Sharpe ratio and max drawdown

**HTML Reports:**

Backtester results can be exported as self-contained HTML reports with interactive charts, equity curves, drawdown plots, and trade-by-trade analysis.

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
1. ExchangeAdapter fetches prices
          │
          ▼
2. Prices published to EventBus ──────► API (WS /ws/events)
          │
          ▼
3. TradingEngine aggregates OHLCV
          │
          ├──► TrailingStopManager checks stops
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
7. Notifications sent (Discord/Telegram webhooks)
          │
          ▼
8. API streams event to WebSocket clients
```

The API layer provides an alternative interface alongside Hermes TUI. External clients can monitor the trading loop via `WS /ws/events` and control the engine via REST endpoints (`POST /api/panic`, `POST /api/pause`).

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
│   ├── api/
│   │   ├── server.py         # FastAPI app & lifecycle
│   │   ├── routes.py         # REST endpoints
│   │   └── websocket.py      # WS event streaming
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
│   │   ├── trailing.py       # Trailing stop manager
│   │   └── profiles.py       # Risk profiles
│   ├── exchange/
│   │   ├── adapter.py        # ExchangeAdapter ABC
│   │   ├── client.py         # Binance (CCXT)
│   │   ├── bybit.py          # Bybit (CCXT)
│   │   ├── paper.py          # Paper trading
│   │   └── orders.py         # Order management
│   ├── notifications/
│   │   ├── telegram.py       # Telegram webhook
│   │   ├── discord.py        # Discord webhook
│   │   └── manager.py        # NotificationManager
│   ├── backtester/
│   │   ├── data.py           # Data loading
│   │   ├── engine.py         # Backtest engine
│   │   ├── walk_forward.py   # Walk-forward validation
│   │   ├── monte_carlo.py    # Monte Carlo simulation
│   │   ├── report.py         # Reports (text & HTML)
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
