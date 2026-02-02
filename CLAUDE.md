# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Development Commands

```bash
# Install dependencies
poetry install --with dev

# Run the application (paper trading mode by default)
poetry run keryxflow

# Run backtests
poetry run keryxflow-backtest --symbol BTC/USDT --start 2024-01-01 --end 2024-06-30

# Run parameter optimization
poetry run keryxflow-optimize --symbol BTC/USDT --start 2024-01-01 --end 2024-06-30 --grid quick

# Run all tests
poetry run pytest

# Run tests with coverage
poetry run pytest --cov=keryxflow --cov-report=term-missing

# Run specific test module
poetry run pytest tests/test_aegis/

# Run single test
poetry run pytest tests/test_aegis/test_quant.py::test_position_size_returns_zero_when_stop_equals_entry

# Lint and format (run before committing)
poetry run ruff check .
poetry run ruff check --fix .
poetry run ruff format .
```

## Architecture

KeryxFlow is an AI-powered cryptocurrency trading engine with a 7-layer architecture:

```
┌─ HERMES (keryxflow/hermes/) ────────────────┐
│  Terminal UI - Textual framework             │
│  Real-time dashboards, onboarding wizard     │
├─ ENGINE (keryxflow/core/engine.py) ─────────┤
│  TradingEngine - Central orchestrator        │
│  OHLCV buffer, signal flow, order loop       │
├─ BACKTESTER (keryxflow/backtester/) ────────┤
│  Strategy validation with historical data    │
│  DataLoader, BacktestEngine, Reports         │
├─ OPTIMIZER (keryxflow/optimizer/) ──────────┤
│  Parameter optimization via grid search      │
│  ParameterGrid, ResultComparator, Reports    │
├─ ORACLE (keryxflow/oracle/) ────────────────┤
│  Intelligence - Technical analysis + LLM     │
│  RSI, MACD, Bollinger, signal generation     │
├─ AEGIS (keryxflow/aegis/) ──────────────────┤
│  Risk Management - Position sizing, limits   │
│  Circuit breaker, Kelly criterion            │
├─ EXCHANGE (keryxflow/exchange/) ────────────┤
│  Connectivity - CCXT/Binance wrapper         │
│  Paper trading engine, order execution       │
└─ CORE (keryxflow/core/) ────────────────────┘
   Event bus, SQLite/SQLModel, logging, models
```

**Trading Loop (TradingEngine):**
```
Price Update → OHLCV Buffer → Oracle (Signal) → Aegis (Approval) → Paper Engine (Order)
```

**Modules communicate via async event bus, not direct calls:**
```python
await event_bus.publish(Event(type=EventType.SIGNAL_GENERATED, data={...}))
```

**Key event types:** PRICE_UPDATE, SIGNAL_GENERATED, ORDER_APPROVED, ORDER_REJECTED, ORDER_FILLED, POSITION_OPENED, POSITION_CLOSED, CIRCUIT_BREAKER_TRIGGERED, PANIC_TRIGGERED

## Code Patterns

- **Async everywhere**: All I/O operations use async/await with tenacity retries
- **Configuration**: Pydantic Settings (`config.py`) loads from `.env` and `settings.toml`. Access via `get_settings()` singleton.
- **Global singletons**: Use `get_event_bus()` and `get_settings()` for shared instances
- **Type hints required**: All functions need complete type annotations
- **Database**: SQLModel with aiosqlite (async SQLite)
- **Event dispatch**: `publish()` queues async, `publish_sync()` dispatches immediately and waits

## Commit Format

```
<type>(<scope>): <description>
```
Types: feat, fix, refactor, test, docs, chore

Scopes: core, hermes, oracle, aegis, exchange, backtester, optimizer, notifications

## Safety Rules

Changes to `aegis/` (risk management) require 100% test coverage. Never bypass risk checks, remove safety limits, or disable circuit breakers.
