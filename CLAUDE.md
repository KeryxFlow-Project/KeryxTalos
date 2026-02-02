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

KeryxFlow is an AI-powered cryptocurrency trading engine with an 8-layer architecture:

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
├─ MEMORY (keryxflow/memory/) ────────────────┤
│  Trade memory - Episodes, Rules, Patterns    │
│  Episodic (trades), Semantic (rules/patterns)│
├─ ORACLE (keryxflow/oracle/) ────────────────┤
│  Intelligence - Technical analysis + LLM     │
│  RSI, MACD, Bollinger, signal generation     │
├─ AEGIS (keryxflow/aegis/) ──────────────────┤
│  Risk Management - Position sizing, limits   │
│  Immutable guardrails, circuit breaker       │
├─ EXCHANGE (keryxflow/exchange/) ────────────┤
│  Connectivity - CCXT/Binance wrapper         │
│  Paper trading engine, order execution       │
└─ CORE (keryxflow/core/) ────────────────────┘
   Event bus, SQLite/SQLModel, logging, models
```

**Trading Loop (TradingEngine):**
```
Price Update → OHLCV Buffer → Memory Context → Oracle (Signal) → Aegis (Approval) → Paper Engine (Order) → Memory Record
```

**Modules communicate via async event bus, not direct calls:**
```python
await event_bus.publish(Event(type=EventType.SIGNAL_GENERATED, data={...}))
```

**Key event types:** PRICE_UPDATE, SIGNAL_GENERATED, ORDER_APPROVED, ORDER_REJECTED, ORDER_FILLED, POSITION_OPENED, POSITION_CLOSED, CIRCUIT_BREAKER_TRIGGERED, PANIC_TRIGGERED

## Code Patterns

- **Async everywhere**: All I/O operations use async/await with tenacity retries
- **Configuration**: Pydantic Settings (`config.py`) loads from `.env` and `settings.toml`. Access via `get_settings()` singleton. Nested settings use prefixes (e.g., `KERYXFLOW_RISK_`, `KERYXFLOW_ORACLE_`).
- **Global singletons**: Use `get_event_bus()`, `get_settings()`, `get_risk_manager()`, `get_signal_generator()`, `get_memory_manager()` for shared instances
- **Type hints required**: All functions need complete type annotations
- **Database**: SQLModel with aiosqlite (async SQLite)
- **Event dispatch**: `publish()` queues async, `publish_sync()` dispatches immediately and waits

## Testing

Tests use pytest-asyncio in auto mode. Important patterns:

- **Global singleton reset**: The `conftest.py` fixture `setup_test_database` resets all global singletons before each test. If you add a new singleton, add its reset to this fixture. Current singletons reset: `config._settings`, `database._engine`, `database._async_session_factory`, `events._event_bus`, `paper._paper_engine`, `episodic._episodic_memory`, `semantic._semantic_memory`, `manager._memory_manager`
- **Async fixtures**: Use `@pytest_asyncio.fixture` for async fixtures, regular `@pytest.fixture` for sync
- **Database isolation**: Each test gets a fresh SQLite database in `tmp_path`

## Commit Format

```
<type>(<scope>): <description>
```
Types: feat, fix, refactor, test, docs, chore

Scopes: core, hermes, oracle, aegis, exchange, backtester, optimizer, notifications, memory

## Memory System

The Memory module (`keryxflow/memory/`) provides learning capabilities:

- **Episodic Memory** (`episodic.py`): Records trade episodes with full context (entry reasoning, technical/market context, lessons learned). Use `get_episodic_memory()` singleton.
- **Semantic Memory** (`semantic.py`): Stores trading rules and market patterns with performance tracking. Use `get_semantic_memory()` singleton.
- **Memory Manager** (`manager.py`): Unified interface for building decision context. Use `get_memory_manager()` singleton.

**Key Models** (`core/models.py`):
- `TradeEpisode` - Complete trade with reasoning and lessons_learned
- `TradingRule` - Rules with source (learned/user/backtest) and success_rate
- `MarketPattern` - Patterns with win_rate and validation status

**Usage in Trading:**
```python
# Build context for decision
context = await memory_manager.build_context_for_decision(symbol, technical_context)

# Record trade entry
episode_id = await memory_manager.record_trade_entry(trade_id, symbol, ...)

# Record trade exit with outcome
await memory_manager.record_trade_exit(episode_id, exit_price, outcome, pnl, ...)
```

## Safety Rules

Changes to `aegis/` (risk management) require 100% test coverage. Never bypass risk checks, remove safety limits, or disable circuit breakers.

**Immutable Guardrails** (`aegis/guardrails.py`): The `TradingGuardrails` class is a frozen dataclass with hardcoded safety limits that cannot be modified at runtime. Key limits include:
- `MAX_POSITION_SIZE_PCT = 10%` — Single position cap
- `MAX_TOTAL_EXPOSURE_PCT = 50%` — Total portfolio exposure
- `MIN_CASH_RESERVE_PCT = 20%` — Minimum cash reserve
- `MAX_DAILY_LOSS_PCT = 5%` — Daily circuit breaker trigger
- `MAX_TOTAL_DRAWDOWN_PCT = 20%` — Maximum drawdown from peak

The `GuardrailEnforcer` validates all orders against these limits before approval.

## Serena MCP Server

This project includes [Serena](https://github.com/oraios/serena) configuration for enhanced code navigation and editing. Serena is an MCP (Model Context Protocol) server that provides semantic code tools via Language Server Protocol (LSP).

**Configuration:** `.serena/project.yml`

**Prerequisites:** Requires `uv` package manager. Install via: `curl -LsSf https://astral.sh/uv/install.sh | sh`

**Key tools available when Serena is active:**

| Tool | Purpose |
|------|---------|
| `find_symbol` | Find symbols (classes, functions, methods) by name pattern |
| `get_symbols_overview` | Get all symbols in a file with their signatures |
| `find_referencing_symbols` | Find all references to a symbol across the codebase |
| `replace_symbol_body` | Replace entire function/method body |
| `rename_symbol` | Rename a symbol with automatic refactoring |
| `insert_before_symbol` / `insert_after_symbol` | Insert code relative to symbols |

**Running manually:**
```bash
uvx --from git+https://github.com/oraios/serena serena start-mcp-server --project-from-cwd
```

**Supported languages:** Python, TypeScript, JavaScript, Rust, Go, Java, C/C++, and 30+ others via LSP.
