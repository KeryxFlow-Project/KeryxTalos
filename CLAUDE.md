# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Development Commands

```bash
# Install dependencies
poetry install --with dev

# Run the application (paper trading mode by default)
poetry run keryxflow

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

KeryxFlow is an AI-powered cryptocurrency trading engine with a 4-layer architecture:

```
┌─ HERMES (keryxflow/hermes/) ────────────────┐
│  Terminal UI - Textual framework             │
│  Real-time dashboards, onboarding wizard     │
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

**Modules communicate via async event bus, not direct calls:**
```python
await event_bus.publish(Event(type=EventType.SIGNAL_GENERATED, data={...}))
```

**Key event types:** PRICE_UPDATE, SIGNAL_GENERATED, ORDER_*, POSITION_*, RISK_ALERT, CIRCUIT_BREAKER_TRIGGERED

## Code Patterns

- **Async everywhere**: All I/O operations use async/await with tenacity retries
- **Configuration**: Pydantic Settings (`config.py`) loads from `.env` and `settings.toml`
- **Type hints required**: All functions need complete type annotations
- **Database**: SQLModel with aiosqlite (async SQLite)

## Commit Format

```
<type>(<scope>): <description>
```
Types: feat, fix, refactor, test, docs, chore

Scopes: core, hermes, oracle, aegis, exchange

## Safety Rules

Changes to `aegis/` (risk management) require 100% test coverage. Never bypass risk checks, remove safety limits, or disable circuit breakers.
