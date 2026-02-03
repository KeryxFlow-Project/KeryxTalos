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

KeryxFlow is an AI-powered cryptocurrency trading engine with a 9-layer architecture:

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
- **Global singletons**: Use `get_event_bus()`, `get_settings()`, `get_risk_manager()`, `get_signal_generator()`, `get_memory_manager()`, `get_trading_toolkit()`, `get_tool_executor()`, `get_cognitive_agent()` for shared instances
- **Type hints required**: All functions need complete type annotations
- **Database**: SQLModel with aiosqlite (async SQLite)
- **Event dispatch**: `publish()` queues async, `publish_sync()` dispatches immediately and waits

## Testing

Tests use pytest-asyncio in auto mode. Important patterns:

- **Global singleton reset**: The `conftest.py` fixture `setup_test_database` resets all global singletons before each test. If you add a new singleton, add its reset to this fixture. Current singletons reset: `config._settings`, `database._engine`, `database._async_session_factory`, `events._event_bus`, `paper._paper_engine`, `episodic._episodic_memory`, `semantic._semantic_memory`, `manager._memory_manager`, `tools._toolkit`, `executor._executor`, `cognitive._agent`, `risk._risk_manager`
- **Async fixtures**: Use `@pytest_asyncio.fixture` for async fixtures, regular `@pytest.fixture` for sync
- **Database isolation**: Each test gets a fresh SQLite database in `tmp_path`

## Commit Format

```
<type>(<scope>): <description>
```
Types: feat, fix, refactor, test, docs, chore

Scopes: core, hermes, oracle, aegis, exchange, backtester, optimizer, notifications, memory, agent

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

## Agent Tools

The Agent module (`keryxflow/agent/`) provides a tool framework for AI-first trading:

- **Tool Framework** (`tools.py`): Base classes and toolkit for managing tools. Use `get_trading_toolkit()` singleton.
- **Perception Tools** (`perception_tools.py`): Read-only market data (7 tools): `get_current_price`, `get_ohlcv`, `get_order_book`, `get_portfolio_state`, `get_balance`, `get_positions`, `get_open_orders`
- **Analysis Tools** (`analysis_tools.py`): Computation and memory access (7 tools): `calculate_indicators`, `calculate_position_size`, `calculate_risk_reward`, `calculate_stop_loss`, `get_trading_rules`, `recall_similar_trades`, `get_market_patterns`
- **Execution Tools** (`execution_tools.py`): Order execution - **GUARDED** (6 tools): `place_order`, `close_position`, `set_stop_loss`, `set_take_profit`, `cancel_order`, `close_all_positions`
- **Safe Executor** (`executor.py`): Wraps tool execution with guardrail validation. Use `get_tool_executor()` singleton.

**Tool Categories:**
| Category | Guarded | Description |
|----------|---------|-------------|
| PERCEPTION | No | Read-only market data |
| ANALYSIS | No | Computation and analysis |
| INTROSPECTION | No | Memory access (rules, patterns, trades) |
| EXECUTION | **Yes** | Order execution - validates guardrails |

**Usage:**
```python
from keryxflow.agent import get_trading_toolkit, get_tool_executor, register_all_tools

# Initialize toolkit with all tools
toolkit = get_trading_toolkit()
register_all_tools(toolkit)

# Get Anthropic-compatible tool schemas
schemas = toolkit.get_anthropic_tools_schema()

# Execute tool directly
result = await toolkit.execute("get_current_price", symbol="BTC/USDT")

# Execute with guardrail validation (recommended for execution tools)
executor = get_tool_executor()
result = await executor.execute_guarded("place_order", symbol="BTC/USDT", side="buy", quantity=0.1)
```

## Cognitive Agent

The Cognitive Agent (`keryxflow/agent/cognitive.py`) provides autonomous AI-first trading:

- **CognitiveAgent** (`cognitive.py`): Autonomous trading agent using Claude's Tool Use API. Use `get_cognitive_agent()` singleton.
- **Cognitive Cycle**: `Perceive → Remember → Analyze → Decide → Validate → Execute → Learn`
- **Agent Mode**: Enable with `KERYXFLOW_AGENT_ENABLED=true`. When enabled, CognitiveAgent replaces SignalGenerator in TradingEngine.
- **Fallback**: If Claude API fails, agent falls back to technical signals (configurable).

**Key Classes:**
- `CognitiveAgent` - Main agent class with `run_cycle()` and `run_loop()` methods
- `CycleResult` - Result of a single agent cycle (status, decision, tool_results)
- `AgentDecision` - Trading decision (HOLD, ENTRY_LONG, ENTRY_SHORT, EXIT, etc.)
- `CycleStatus` - Cycle outcome (SUCCESS, NO_ACTION, FALLBACK, ERROR)

**Configuration** (`config.py` → `AgentSettings`):
```python
KERYXFLOW_AGENT_ENABLED=true          # Enable agent mode
KERYXFLOW_AGENT_MODEL=claude-sonnet-4-20250514  # Claude model
KERYXFLOW_AGENT_CYCLE_INTERVAL=60     # Seconds between cycles
KERYXFLOW_AGENT_MAX_TOOL_CALLS_PER_CYCLE=20
KERYXFLOW_AGENT_FALLBACK_TO_TECHNICAL=true
```

**Usage:**
```python
from keryxflow.agent import get_cognitive_agent

# Get agent instance
agent = get_cognitive_agent()
await agent.initialize()

# Run a single cycle
result = await agent.run_cycle(["BTC/USDT", "ETH/USDT"])

# Or run continuously
await agent.run_loop(max_cycles=100)

# Get statistics
stats = agent.get_stats()
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
