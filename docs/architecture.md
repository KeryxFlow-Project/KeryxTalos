# KeryxFlow Architecture

> **This is the single source of truth for KeryxFlow's system architecture.**
> All other documents reference this file for architectural details.

## Table of Contents

- [Overview](#overview)
- [Design Principles](#design-principles)
- [Layer Reference](#layer-reference)
  - [Core](#core)
  - [Exchange](#exchange)
  - [Notifications](#notifications)
  - [Aegis (Risk Management)](#aegis-risk-management)
  - [Oracle (Intelligence)](#oracle-intelligence)
  - [Memory](#memory)
  - [Agent](#agent)
  - [Backtester](#backtester)
  - [Optimizer](#optimizer)
  - [API](#api)
  - [Engine](#engine)
  - [Hermes (Interface)](#hermes-interface)
- [Event Bus](#event-bus)
- [Trading Loop](#trading-loop)
- [Cognitive Agent Cycle](#cognitive-agent-cycle)
- [Database Schema](#database-schema)
- [Module Dependency Graph](#module-dependency-graph)
- [Technology Stack](#technology-stack)

---

## Overview

KeryxFlow is an AI-powered cryptocurrency trading engine with a 12-layer, event-driven architecture. Modules communicate through an async event bus rather than direct method calls, enabling loose coupling, testability, and extensibility.

```
┌─ HERMES (keryxflow/hermes/) ────────────────┐
│  Terminal UI - Textual framework             │
│  Real-time dashboards, onboarding wizard     │
├─ ENGINE (keryxflow/core/engine.py) ─────────┤
│  TradingEngine - Central orchestrator        │
│  OHLCV buffer, signal flow, order loop       │
├─ API (keryxflow/api/) ──────────────────────┤
│  REST API & WebSocket - FastAPI server       │
│  Status, positions, trades, agent endpoints  │
├─ BACKTESTER (keryxflow/backtester/) ────────┤
│  Strategy validation with historical data    │
│  DataLoader, BacktestEngine, Reports         │
├─ OPTIMIZER (keryxflow/optimizer/) ──────────┤
│  Parameter optimization via grid search      │
│  ParameterGrid, ResultComparator, Reports    │
├─ AGENT (keryxflow/agent/) ──────────────────┤
│  AI Tool Framework - Anthropic Tool Use API  │
│  Perception, Analysis, Execution tools       │
├─ MEMORY (keryxflow/memory/) ────────────────┤
│  Trade memory - Episodes, Rules, Patterns    │
│  Episodic (trades), Semantic (rules/patterns)│
├─ ORACLE (keryxflow/oracle/) ────────────────┤
│  Intelligence - Technical analysis + LLM     │
│  RSI, MACD, Bollinger, signal generation     │
├─ AEGIS (keryxflow/aegis/) ──────────────────┤
│  Risk Management - Position sizing, limits   │
│  Immutable guardrails, circuit breaker       │
├─ NOTIFICATIONS (keryxflow/notifications/) ──┤
│  Webhook notifications - Discord & Telegram  │
│  Trade alerts, position updates              │
├─ EXCHANGE (keryxflow/exchange/) ────────────┤
│  Multi-exchange - Binance, Bybit adapters    │
│  Paper trading engine, order execution       │
└─ CORE (keryxflow/core/) ────────────────────┘
   Event bus, SQLite/SQLModel, logging, models
```

---

## Design Principles

### 1. Event-Driven Communication

Modules communicate via an async event bus, not direct method calls:

```python
# Publishing
await event_bus.publish(Event(type=EventType.SIGNAL_GENERATED, data={...}))

# Subscribing
event_bus.subscribe(EventType.SIGNAL_GENERATED, self._on_signal)
```

### 2. Async-First

All I/O operations use `async`/`await`. Retry logic uses `tenacity`.

### 3. Configuration Over Hardcoding

All parameters are configurable via `settings.toml` or environment variables (prefix `KERYXFLOW_`). See [Configuration Guide](configuration.md).

### 4. Safety by Design

Risk management (Aegis) must approve every order before execution. Immutable guardrails in code cannot be bypassed.

### 5. Global Singletons

Shared instances are accessed via getter functions (e.g., `get_event_bus()`, `get_settings()`, `get_risk_manager()`). Each module provides its own singleton getters.

---

## Layer Reference

### Core

**Path:** `keryxflow/core/`
**Purpose:** Foundation layer providing shared infrastructure.

| File | Key Classes | Purpose |
|------|-------------|---------|
| `events.py` | `EventBus`, `Event`, `EventType` | Async pub/sub event bus |
| `database.py` | `init_database()`, `get_session()` | SQLite with SQLModel (async via aiosqlite) |
| `models.py` | `Trade`, `Signal`, `Position`, `DailyStats`, `PaperBalance`, `TradeEpisode`, `TradingRule`, `MarketPattern` | All SQLModel data models |
| `engine.py` | `TradingEngine` | Central orchestrator |
| `repository.py` | `TradeRepository` | Trade persistence layer |
| `safeguards.py` | `LiveTradingSafeguards` | Pre-live-trading safety checks |
| `logging.py` | `get_logger()`, `setup_logging()` | Structured logging with structlog |
| `glossary.py` | `GLOSSARY` | Trading term definitions for UI |
| `mtf_buffer.py` | `MTFBuffer` | Multi-timeframe OHLCV aggregation |

**Events emitted:** `SYSTEM_STARTED`, `SYSTEM_STOPPED`, `SYSTEM_PAUSED`, `SYSTEM_RESUMED`, `PANIC_TRIGGERED`

---

### Exchange

**Path:** `keryxflow/exchange/`
**Purpose:** Multi-exchange connectivity via a unified adapter interface.

| File | Key Classes | Purpose |
|------|-------------|---------|
| `adapter.py` | `ExchangeAdapter` (ABC) | Common interface for all exchanges |
| `client.py` | `ExchangeClient` | Binance implementation via CCXT |
| `bybit.py` | `BybitClient` | Bybit implementation via CCXT |
| `paper.py` | `PaperEngine` | Paper trading simulation |
| `orders.py` | `OrderManager` | Order management abstraction |

**Public API:**

```python
class ExchangeAdapter(ABC):
    async def connect() -> None
    async def fetch_ticker(symbol: str) -> dict
    async def fetch_ohlcv(symbol: str, timeframe: str, limit: int) -> list
    async def create_order(symbol: str, side: str, amount: float, price: float | None) -> dict
    async def cancel_order(order_id: str, symbol: str) -> dict
    async def fetch_balance() -> dict
    async def get_open_orders(symbol: str | None) -> list
```

**Factory:** `get_exchange_adapter()` selects implementation based on `KERYXFLOW_EXCHANGE` setting (default: `binance`).

**Trading modes:** `paper` (default, simulated) and `live` (real money, requires safeguard checks).

**Events emitted:** `PRICE_UPDATE`, `OHLCV_UPDATE`, `ORDER_FILLED`, `ORDER_CANCELLED`

---

### Notifications

**Path:** `keryxflow/notifications/`
**Purpose:** Event-driven alert system using Discord and Telegram webhooks.

| File | Key Classes | Purpose |
|------|-------------|---------|
| `manager.py` | `NotificationManager` | Event subscriber and dispatcher |
| `discord.py` | `DiscordNotifier` | Discord webhook sender |
| `telegram.py` | `TelegramNotifier` | Telegram Bot API sender |
| `base.py` | `BaseNotifier` | Abstract notifier base class |

**Subscribed events:** `POSITION_OPENED`, `POSITION_CLOSED`, `ORDER_FILLED`, `CIRCUIT_BREAKER_TRIGGERED`

**Singleton:** `get_notification_manager()`

---

### Aegis (Risk Management)

**Path:** `keryxflow/aegis/`
**Purpose:** Mathematical risk management. Every order must be approved before execution.

| File | Key Classes | Purpose |
|------|-------------|---------|
| `risk.py` | `RiskManager` | Order approval/rejection |
| `quant.py` | `QuantEngine` | Position sizing, R:R calculations |
| `circuit.py` | `CircuitBreaker` | Emergency stop on drawdown limits |
| `guardrails.py` | `TradingGuardrails`, `GuardrailEnforcer` | Immutable safety limits |
| `profiles.py` | `RiskProfileManager` | Conservative, balanced, aggressive profiles |
| `trailing.py` | `TrailingStopManager` | Dynamic trailing stop-loss |
| `portfolio.py` | `PortfolioTracker` | Portfolio-level exposure tracking |

**Immutable Guardrails** (frozen dataclass, cannot be modified at runtime):

| Guardrail | Value | Description |
|-----------|-------|-------------|
| `MAX_POSITION_SIZE_PCT` | 10% | Single position cap |
| `MAX_TOTAL_EXPOSURE_PCT` | 50% | Total portfolio exposure |
| `MIN_CASH_RESERVE_PCT` | 20% | Minimum cash reserve |
| `MAX_LOSS_PER_TRADE_PCT` | 2% | Per-trade loss limit |
| `MAX_DAILY_LOSS_PCT` | 5% | Daily circuit breaker trigger |
| `MAX_WEEKLY_LOSS_PCT` | 10% | Weekly loss limit |
| `MAX_TOTAL_DRAWDOWN_PCT` | 20% | Maximum drawdown from peak |
| `MAX_TRADES_PER_HOUR` | 10 | Hourly rate limit |
| `MAX_TRADES_PER_DAY` | 50 | Daily rate limit |

**Approval checks:** Position size, open position count, daily drawdown, risk/reward ratio, symbol whitelist, stop-loss requirement.

**Trailing Stop:** `TrailingStopManager` ratchets stop-loss levels upward as price moves favorably. Integrates into the TradingEngine price loop.

**Events emitted:** `ORDER_APPROVED`, `ORDER_REJECTED`, `CIRCUIT_BREAKER_TRIGGERED`, `RISK_ALERT`, `DRAWDOWN_WARNING`, `STOP_LOSS_TRAILED`, `STOP_LOSS_BREAKEVEN`

**Singletons:** `get_risk_manager()`, `get_trailing_stop_manager()`

---

### Oracle (Intelligence)

**Path:** `keryxflow/oracle/`
**Purpose:** Hybrid signal generation combining quantitative analysis with cognitive AI.

| File | Key Classes | Purpose |
|------|-------------|---------|
| `technical.py` | `TechnicalAnalyzer` | Technical indicators (RSI, MACD, BBands, OBV, ATR, EMA) |
| `feeds.py` | `NewsFeedAggregator` | RSS and CryptoPanic news aggregation |
| `brain.py` | `LLMBrain` | Claude integration for market context analysis |
| `signals.py` | `SignalGenerator` | Signal generation combining all sources |
| `mtf_signals.py` | `MTFSignalGenerator` | Multi-timeframe signal generation |
| `mtf_analyzer.py` | `MTFAnalyzer` | Multi-timeframe trend analysis |

**Signal types:** `LONG`, `SHORT`, `CLOSE_LONG`, `CLOSE_SHORT`, `NO_ACTION`

**Signal generation flow:**

```
Technical Analysis ──┐
News Aggregator ─────┼──▶ Signal Generator ──▶ SIGNAL_GENERATED event
LLM Brain ───────────┘
```

**Events emitted:** `SIGNAL_GENERATED`, `SIGNAL_VALIDATED`, `SIGNAL_REJECTED`, `LLM_ANALYSIS_STARTED`, `LLM_ANALYSIS_COMPLETED`, `LLM_ANALYSIS_FAILED`, `NEWS_FETCHED`

**Singleton:** `get_signal_generator()`

---

### Memory

**Path:** `keryxflow/memory/`
**Purpose:** Persistent trade memory enabling learning from experience.

| File | Key Classes | Purpose |
|------|-------------|---------|
| `episodic.py` | `EpisodicMemory` | Records trade episodes with full context |
| `semantic.py` | `SemanticMemory` | Stores trading rules and market patterns |
| `manager.py` | `MemoryManager` | Unified interface for building decision context |

**Memory types:**

- **Episodic Memory:** Complete trade episodes including entry reasoning, technical/market context, outcome, and lessons learned (`TradeEpisode` model).
- **Semantic Memory:** Trading rules with source tracking and success rates (`TradingRule` model), and market patterns with win rates and validation status (`MarketPattern` model).

**Public API:**

```python
class MemoryManager:
    async def build_context_for_decision(symbol, technical_context) -> dict
    async def record_trade_entry(trade_id, symbol, ...) -> int
    async def record_trade_exit(episode_id, exit_price, outcome, pnl, ...) -> None
```

**Singletons:** `get_episodic_memory()`, `get_semantic_memory()`, `get_memory_manager()`

---

### Agent

**Path:** `keryxflow/agent/`
**Purpose:** AI-first autonomous trading using Claude's Tool Use API.

| File | Key Classes | Purpose |
|------|-------------|---------|
| `cognitive.py` | `CognitiveAgent` | Autonomous trading agent |
| `tools.py` | `TradingToolkit`, `Tool` | Tool framework and registry |
| `executor.py` | `SafeExecutor` | Guardrail-validated tool execution |
| `perception_tools.py` | 7 perception tools | Read-only market data |
| `analysis_tools.py` | 7 analysis tools | Computation and memory access |
| `execution_tools.py` | 6 execution tools | Guarded order execution |
| `reflection.py` | `ReflectionEngine` | Post-mortems, daily/weekly reflections |
| `strategy.py` | `StrategyManager` | Market regime detection, strategy selection |
| `strategy_gen.py` | `StrategyGenerator` | AI-powered strategy generation |
| `scheduler.py` | `TaskScheduler` | Periodic task scheduling |
| `session.py` | `TradingSession` | Session lifecycle management |
| `orchestrator.py` | `AgentOrchestrator` | Multi-agent coordination |
| `base_agent.py` | `BaseSpecializedAgent` | Base class for specialized agents |
| `analyst_agent.py` | `AnalystAgent` | Market analysis specialist |
| `risk_agent.py` | `RiskAgent` | Risk assessment specialist |
| `executor_agent.py` | `ExecutorAgent` | Trade execution specialist |
| `multi_agent.py` | Multi-agent utilities | Shared multi-agent infrastructure |

**Tool categories:**

| Category | Guarded | Tools |
|----------|---------|-------|
| PERCEPTION | No | `get_current_price`, `get_ohlcv`, `get_order_book`, `get_portfolio_state`, `get_balance`, `get_positions`, `get_open_orders` |
| ANALYSIS | No | `calculate_indicators`, `calculate_position_size`, `calculate_risk_reward`, `calculate_stop_loss`, `get_trading_rules`, `recall_similar_trades`, `get_market_patterns` |
| EXECUTION | **Yes** | `place_order`, `close_position`, `set_stop_loss`, `set_take_profit`, `cancel_order`, `close_all_positions` |

**Cognitive Agent cycle:** `Perceive -> Remember -> Analyze -> Decide -> Validate -> Execute -> Learn`

**Reflection Engine:** Generates insights using Claude for post-mortems (single trade), daily reflections, and weekly reflections that create/update trading rules.

**Strategy Manager:** Detects market regimes (`TRENDING_UP`, `TRENDING_DOWN`, `RANGING`, `HIGH_VOLATILITY`, `LOW_VOLATILITY`, `BREAKOUT`, `UNKNOWN`) and selects strategies (`TREND_FOLLOWING`, `MEAN_REVERSION`, `BREAKOUT`, `MOMENTUM`, `SCALPING`).

**Multi-Agent Architecture:** `AgentOrchestrator` coordinates specialized agents (`AnalystAgent`, `RiskAgent`, `ExecutorAgent`) that each focus on their domain of expertise.

**Events emitted:** `AGENT_CYCLE_STARTED`, `AGENT_CYCLE_COMPLETED`, `AGENT_CYCLE_FAILED`, `SESSION_STATE_CHANGED`, `AGENT_ANALYSIS_COMPLETED`, `AGENT_RISK_ASSESSED`, `AGENT_EXECUTION_COMPLETED`, `TOOL_EXECUTED`

**Singletons:** `get_cognitive_agent()`, `get_trading_toolkit()`, `get_tool_executor()`, `get_reflection_engine()`, `get_strategy_manager()`, `get_task_scheduler()`, `get_trading_session()`

---

### Backtester

**Path:** `keryxflow/backtester/`
**Purpose:** Historical strategy validation with walk-forward analysis and Monte Carlo simulation.

| File | Key Classes | Purpose |
|------|-------------|---------|
| `data.py` | `DataLoader` | OHLCV data loading from exchange or CSV |
| `engine.py` | `BacktestEngine` | Backtest simulation engine |
| `walk_forward.py` | `WalkForwardEngine` | Out-of-sample validation |
| `monte_carlo.py` | `MonteCarloSimulator` | Statistical analysis via randomized permutations |
| `report.py` | `ReportGenerator` | Text performance reports |
| `html_report.py` | `HTMLReportGenerator` | Interactive HTML reports with charts |
| `runner.py` | CLI runner | `keryxflow-backtest` CLI interface |

**Walk-Forward Engine:** Splits data into rolling in-sample/out-of-sample windows to guard against overfitting.

**Monte Carlo Simulator:** Runs thousands of randomized trade sequence permutations to estimate drawdown distribution, probability of ruin, and confidence intervals.

**Metrics:** Total return, win rate, profit factor, max drawdown, Sharpe ratio, expectancy.

---

### Optimizer

**Path:** `keryxflow/optimizer/`
**Purpose:** Parameter optimization via grid search.

| File | Key Classes | Purpose |
|------|-------------|---------|
| `grid.py` | `ParameterGrid` | Parameter combination generation |
| `engine.py` | `OptimizationEngine` | Optimization loop |
| `comparator.py` | `ResultComparator` | Result analysis and ranking |
| `report.py` | `OptimizationReport` | Optimization reports |
| `runner.py` | CLI runner | `keryxflow-optimize` CLI interface |

**Optimizable parameters:** Oracle (rsi_period, macd_fast, macd_slow, bbands_std) and Risk (risk_per_trade, min_risk_reward, atr_multiplier).

---

### API

**Path:** `keryxflow/api/`
**Purpose:** REST and WebSocket interface built with FastAPI.

| File | Key Classes | Purpose |
|------|-------------|---------|
| `server.py` | `APIServer` | FastAPI application and lifecycle |
| `webhook.py` | Route handlers | REST endpoint definitions |

**REST Endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/status` | Engine status, uptime, active symbols |
| `GET` | `/api/positions` | Open positions with unrealized PnL |
| `GET` | `/api/trades` | Trade history |
| `GET` | `/api/balance` | Current balance and equity |
| `POST` | `/api/panic` | Emergency stop — close all positions |
| `POST` | `/api/pause` | Pause/resume trading |
| `GET` | `/api/agent/status` | Cognitive agent session status |

**WebSocket:** `ws://host:port/ws/events` — Real-time event stream forwarded from the internal event bus.

**Lifecycle:** Started and stopped by `TradingEngine`. Runs alongside the Hermes TUI as an alternative interface.

---

### Engine

**Path:** `keryxflow/core/engine.py`
**Purpose:** Central orchestrator connecting all modules in the trading loop.

**Key class:** `TradingEngine`

```python
class TradingEngine:
    async def start() -> None          # Start engine and all subsystems
    async def stop() -> None           # Graceful shutdown
    async def _run_analysis() -> None  # Trigger Oracle signal generation
    async def _handle_signal() -> None # Route signal through Aegis to execution
```

**Components:**

- **OHLCVBuffer:** Aggregates price updates into 1-minute candles
- **Signal Flow:** Triggers Oracle analysis at configurable intervals
- **Order Loop:** Routes signals through Aegis approval to execution
- **Agent Mode:** When `KERYXFLOW_AGENT_ENABLED=true`, `CognitiveAgent` replaces `SignalGenerator`

---

### Hermes (Interface)

**Path:** `keryxflow/hermes/`
**Purpose:** Terminal User Interface built with Textual.

| File | Key Classes | Purpose |
|------|-------------|---------|
| `app.py` | `KeryxFlowApp` | Main TUI application |
| `theme.tcss` | — | CSS styling |
| `onboarding.py` | `OnboardingWizard` | First-run setup wizard |

**Widgets** (`hermes/widgets/`):

| Widget | Purpose |
|--------|---------|
| `ChartWidget` | ASCII price chart with indicators |
| `PositionsWidget` | Open positions with PnL |
| `OracleWidget` | Market context and signals |
| `AegisWidget` | Risk status and circuit breaker |
| `StatsWidget` | Trading statistics |
| `LogsWidget` | Activity log |
| `AgentWidget` | Agent session state, cycles, trades, tokens |
| `HelpModal` | Glossary and keyboard shortcuts |
| `BalanceWidget` | Account balance display |
| `SplashWidget` | Startup splash screen |

**Keyboard shortcuts:**

| Key | Action |
|-----|--------|
| `Q` | Quit |
| `P` | Panic — close all positions immediately |
| `Space` | Pause/Resume trading |
| `A` | Toggle Agent (start/pause/resume) |
| `L` | Toggle logs panel |
| `S` | Cycle through symbols |
| `?` | Help |

---

## Event Bus

The event bus (`keryxflow/core/events.py`) is the backbone of inter-module communication. Events are published asynchronously via a queue and dispatched to registered handlers.

**Two dispatch modes:**
- `publish()` — Queues event for async processing
- `publish_sync()` — Dispatches immediately and waits for all handlers

### Complete Event Type Reference

| Category | Event | Description |
|----------|-------|-------------|
| **Price** | `PRICE_UPDATE` | New price tick from exchange |
| | `OHLCV_UPDATE` | New OHLCV candle completed |
| **Signal** | `SIGNAL_GENERATED` | Oracle produced a trading signal |
| | `SIGNAL_VALIDATED` | Signal passed validation |
| | `SIGNAL_REJECTED` | Signal failed validation |
| **Order** | `ORDER_REQUESTED` | Order submitted for approval |
| | `ORDER_APPROVED` | Aegis approved the order |
| | `ORDER_REJECTED` | Aegis rejected the order |
| | `ORDER_SUBMITTED` | Order sent to exchange |
| | `ORDER_FILLED` | Order executed on exchange |
| | `ORDER_CANCELLED` | Order cancelled |
| **Position** | `POSITION_OPENED` | New position opened |
| | `POSITION_UPDATED` | Position price/PnL updated |
| | `POSITION_CLOSED` | Position closed |
| **Risk** | `RISK_ALERT` | Risk threshold warning |
| | `CIRCUIT_BREAKER_TRIGGERED` | Trading halted due to losses |
| | `DRAWDOWN_WARNING` | Drawdown approaching limit |
| **System** | `SYSTEM_STARTED` | Engine started |
| | `SYSTEM_STOPPED` | Engine stopped |
| | `SYSTEM_PAUSED` | Trading paused |
| | `SYSTEM_RESUMED` | Trading resumed |
| | `PANIC_TRIGGERED` | Emergency stop activated |
| **LLM** | `LLM_ANALYSIS_STARTED` | Claude analysis began |
| | `LLM_ANALYSIS_COMPLETED` | Claude analysis finished |
| | `LLM_ANALYSIS_FAILED` | Claude analysis failed |
| **News** | `NEWS_FETCHED` | News feed updated |
| **Agent** | `AGENT_CYCLE_STARTED` | Cognitive agent cycle began |
| | `AGENT_CYCLE_COMPLETED` | Cognitive agent cycle finished |
| | `AGENT_CYCLE_FAILED` | Cognitive agent cycle failed |
| | `SESSION_STATE_CHANGED` | Trading session state change |
| **Multi-Agent** | `AGENT_ANALYSIS_COMPLETED` | Analyst agent finished |
| | `AGENT_RISK_ASSESSED` | Risk agent finished |
| | `AGENT_EXECUTION_COMPLETED` | Executor agent finished |
| **Tool** | `TOOL_EXECUTED` | Agent tool call completed |

**Total: 33 event types across 10 categories.**

---

## Trading Loop

### Standard Mode (Oracle-driven)

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
6. PaperEngine / LiveExchange executes
          │
          ▼
7. Notifications sent (Discord/Telegram)
          │
          ▼
8. Memory records trade episode
```

### Agent Mode (Cognitive Agent-driven)

When `KERYXFLOW_AGENT_ENABLED=true`, the CognitiveAgent replaces the Oracle-driven flow:

```
1. CognitiveAgent.run_cycle() triggered at configured interval
          │
          ▼
2. PERCEIVE — Fetch prices, portfolio, order book via tools
          │
          ▼
3. REMEMBER — Query Memory for similar trades, rules, patterns
          │
          ▼
4. ANALYZE — Calculate indicators, assess risk/reward via tools
          │
          ▼
5. DECIDE — Claude decides: entry, exit, or hold
          │
          ▼
6. VALIDATE — GuardrailEnforcer checks all limits
          │
          ▼
7. EXECUTE — Place order via guarded execution tools
          │
          ▼
8. LEARN — Record episode, update rules, schedule reflections
```

**Fallback:** If Claude API fails, agent falls back to technical signals when `KERYXFLOW_AGENT_FALLBACK_TO_TECHNICAL=true`.

---

## Cognitive Agent Cycle

The `CognitiveAgent` uses Claude's Tool Use API in an agentic loop:

1. **Context building** — Assembles market data, portfolio state, and memory context
2. **Claude reasoning** — Sends context + available tools to Claude
3. **Tool use loop** — Claude calls perception/analysis tools iteratively
4. **Decision** — Claude produces a trading decision (`HOLD`, `ENTRY_LONG`, `ENTRY_SHORT`, `EXIT`, etc.)
5. **Guardrail validation** — `GuardrailEnforcer` validates execution tools
6. **Execution** — Approved actions execute against paper/live exchange
7. **Learning** — Results recorded in episodic memory

**Reflection schedule:**
- Daily reflection at 23:00 UTC — Summarizes day's trades, key lessons, mistakes
- Weekly reflection at Sunday 23:30 UTC — Identifies patterns, creates/updates rules

---

## Database Schema

SQLite database via SQLModel (async with aiosqlite).

| Table | Model | Purpose |
|-------|-------|---------|
| `user_profiles` | `UserProfile` | User preferences, experience level, risk profile |
| `trades` | `Trade` | Trade history (entries, exits, PnL) |
| `signals` | `Signal` | Trading signals with validation status |
| `positions` | `Position` | Currently open positions |
| `market_contexts` | `MarketContext` | LLM market analysis results |
| `daily_stats` | `DailyStats` | Daily performance metrics |
| `paper_balances` | `PaperBalance` | Paper trading balance tracker |
| `trade_episodes` | `TradeEpisode` | Complete trade episodes with reasoning and lessons |
| `trading_rules` | `TradingRule` | Learned/user-defined trading rules |
| `market_patterns` | `MarketPattern` | Identified market patterns with statistics |

---

## Module Dependency Graph

```
                    ┌──────────┐
                    │  HERMES  │
                    └────┬─────┘
                         │
              ┌──────────┴──────────┐
              │      ENGINE         │
              └──┬────┬────┬────┬───┘
                 │    │    │    │
         ┌───────┘    │    │    └───────┐
         │            │    │            │
    ┌────┴────┐  ┌────┴──┐ │      ┌────┴────┐
    │  AGENT  │  │ ORACLE │ │      │   API   │
    └────┬────┘  └────┬───┘ │      └─────────┘
         │            │     │
    ┌────┴────┐       │  ┌──┴──────┐
    │ MEMORY  │       │  │  AEGIS  │
    └─────────┘       │  └────┬────┘
                      │       │
              ┌───────┴───────┴───────┐
              │      EXCHANGE         │
              └───────────────────────┘
                         │
              ┌──────────┴──────────┐
              │       CORE          │
              │  Events • DB • Log  │
              └─────────────────────┘

  BACKTESTER ──► ORACLE + AEGIS + EXCHANGE (reuses for simulation)
  OPTIMIZER  ──► BACKTESTER (runs multiple backtests)
  NOTIFICATIONS ──► CORE (subscribes to events)
```

All modules depend on **Core** for events, database, logging, and models. Arrows indicate runtime dependencies.

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.12+ |
| Package Manager | Poetry |
| Exchange API | CCXT (Binance, Bybit) |
| Database | SQLModel + aiosqlite |
| Analysis | numpy, pandas, pandas-ta |
| AI | Anthropic Claude (Tool Use API) |
| Interface | Textual (TUI), FastAPI (REST/WS) |
| Logging | structlog |
| Testing | pytest, pytest-asyncio |
| Linting | ruff |
