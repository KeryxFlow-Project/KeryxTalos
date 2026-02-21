# KeryxFlow Development Guide

The definitive guide for developing KeryxFlow. Covers environment setup, project structure, code patterns, testing, and how to add new features.

## Prerequisites

- **Python 3.12+** — Check with `python3 --version`
- **Poetry** — Install with `curl -sSL https://install.python-poetry.org | python3 -`
- **Git** — For version control

## Development Environment Setup

### Clone and Install

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/keryxflow.git
cd keryxflow

# Install all dependencies (including dev)
poetry install --with dev

# Create environment file
cp .env.example .env
```

### Configure API Keys (Optional)

For full functionality, add API keys to `.env`:

```bash
# Exchange credentials (required for live data, not needed for paper trading)
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret

# Anthropic (required for LLM/Agent features)
ANTHROPIC_API_KEY=your_key
```

Without API keys, KeryxFlow runs in **paper trading mode** with **technical-only analysis** (RSI, MACD, Bollinger Bands). This is fine for development.

### Verify Installation

```bash
# Run the application (paper trading mode)
poetry run keryxflow

# Run tests
poetry run pytest

# Check code quality
poetry run ruff check .
```

## Running the Application

### Paper Trading (Default)

```bash
poetry run keryxflow
```

Starts with $10,000 virtual USDT. On first launch, the onboarding wizard configures your risk profile.

### Backtesting

```bash
poetry run keryxflow-backtest \
    --symbol BTC/USDT \
    --start 2024-01-01 \
    --end 2024-06-30 \
    --profile balanced
```

Useful flags: `--timeframe 1h`, `--balance 10000`, `--chart`, `--output ./reports`

### Parameter Optimization

```bash
poetry run keryxflow-optimize \
    --symbol BTC/USDT \
    --start 2024-01-01 \
    --end 2024-06-30 \
    --grid quick
```

### API Server

```bash
# Development server with auto-reload
poetry run uvicorn keryxflow.api:app --reload --port 8080

# Test it
curl http://localhost:8080/api/status
```

### TUI Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Q` | Quit |
| `P` | Panic (emergency close all positions) |
| `Space` | Pause / Resume trading |
| `A` | Toggle AI Agent (start/pause/resume) |
| `L` | Toggle logs panel |
| `S` | Cycle through symbols |
| `?` | Show help |

## Project Structure

```
keryxflow/
├── keryxflow/
│   ├── core/            # Foundation: events, database, logging, models
│   ├── hermes/          # Terminal UI (Textual framework)
│   ├── oracle/          # Intelligence: technical analysis + LLM signals
│   ├── aegis/           # Risk management: guardrails, position sizing, circuit breaker
│   ├── exchange/        # Multi-exchange: Binance, Bybit, Kraken, OKX, paper trading
│   ├── agent/           # AI framework: Cognitive Agent, tools, reflection, strategy
│   ├── memory/          # Trade memory: episodic, semantic, patterns
│   ├── backtester/      # Strategy backtesting: data loader, engine, reports
│   ├── optimizer/       # Parameter optimization: grid search, comparator
│   ├── notifications/   # Alert channels: Discord, Telegram webhooks
│   ├── api/             # REST API & WebSocket (FastAPI)
│   ├── strategies/      # Trading strategy definitions
│   └── web/             # Web interface
├── tests/               # Tests (mirrors keryxflow/ structure)
├── docs/                # Documentation
├── settings.toml        # Application configuration
└── pyproject.toml       # Dependencies and project metadata
```

### Module Responsibilities

| Module | Purpose | Key Principle |
|--------|---------|---------------|
| `core` | Events, database, models, logging | Stability over features |
| `hermes` | Terminal UI (Textual) | Clarity over decoration |
| `oracle` | Signal generation (indicators + LLM) | Accuracy over speed |
| `aegis` | Risk management (guardrails, sizing) | Safety over opportunity |
| `exchange` | Exchange connectivity (CCXT, paper) | Reliability over performance |
| `agent` | AI tool framework (Cognitive Agent) | Autonomy with guardrails |
| `memory` | Trade memory (episodic, semantic) | Learning over forgetting |
| `backtester` | Strategy validation (historical data) | Accuracy over speed |
| `optimizer` | Parameter optimization (grid search) | Thoroughness over shortcuts |
| `notifications` | Alert channels (Discord, Telegram) | Delivery over silence |
| `api` | REST API & WebSocket (FastAPI) | Simplicity over completeness |

### Trading Loop

```
Price Update → OHLCV Buffer → Memory Context → Oracle (Signal) → Aegis (Approval) → Paper Engine (Order) → Memory Record
```

## Code Patterns

### Async by Default

All I/O operations must be async:

```python
# Good
async def fetch_price(symbol: str) -> float:
    ticker = await self.exchange.fetch_ticker(symbol)
    return ticker["last"]

# Bad - blocks event loop
def fetch_price(symbol: str) -> float:
    return requests.get(...)
```

### Event-Driven Communication

Modules communicate via the async event bus, not direct calls:

```python
from keryxflow.core.events import get_event_bus, Event, EventType

# Good
await event_bus.publish(Event(
    type=EventType.SIGNAL_GENERATED,
    data={"symbol": "BTC/USDT", "signal_type": "long"}
))

# Bad - direct coupling
aegis.approve_order(order)
```

Key event types: `PRICE_UPDATE`, `SIGNAL_GENERATED`, `ORDER_APPROVED`, `ORDER_REJECTED`, `ORDER_FILLED`, `POSITION_OPENED`, `POSITION_CLOSED`, `CIRCUIT_BREAKER_TRIGGERED`, `PANIC_TRIGGERED`, `STOP_LOSS_TRAILED`, `STOP_LOSS_BREAKEVEN`

### Global Singletons

Access shared instances via getter functions:

```python
from keryxflow.config import get_settings
from keryxflow.core.events import get_event_bus
from keryxflow.aegis.risk import get_risk_manager
from keryxflow.agent.cognitive import get_cognitive_agent
from keryxflow.memory.manager import get_memory_manager
```

Full list of singletons:

| Module | Getter | Private Variable |
|--------|--------|-----------------|
| `config` | `get_settings()` | `_settings` |
| `core.database` | — | `_engine`, `_async_session_factory` |
| `core.events` | `get_event_bus()` | `_event_bus` |
| `exchange.paper` | `get_paper_engine()` | `_paper_engine` |
| `exchange.demo` | `get_demo_client()` | `_demo_client` |
| `exchange.kraken` | `get_kraken_client()` | `_kraken_client` |
| `exchange.okx` | `get_okx_client()` | `_okx_client` |
| `memory.episodic` | `get_episodic_memory()` | `_episodic_memory` |
| `memory.semantic` | `get_semantic_memory()` | `_semantic_memory` |
| `memory.manager` | `get_memory_manager()` | `_memory_manager` |
| `agent.tools` | `get_trading_toolkit()` | `_toolkit` |
| `agent.executor` | `get_tool_executor()` | `_executor` |
| `agent.cognitive` | `get_cognitive_agent()` | `_agent` |
| `agent.reflection` | `get_reflection_engine()` | `_reflection_engine` |
| `agent.scheduler` | `get_task_scheduler()` | `_scheduler` |
| `agent.session` | `get_trading_session()` | `_session` |
| `agent.strategy` | `get_strategy_manager()` | `_strategy_manager` |
| `agent.strategy_gen` | `get_strategy_generator()` | `_strategy_generator` |
| `aegis.risk` | `get_risk_manager()` | `_risk_manager` |

### Type Hints (Required)

All functions must have complete type annotations:

```python
def calculate_position_size(
    balance: float,
    risk_pct: float,
    entry: float,
    stop_loss: float,
) -> float:
    ...
```

### Configuration Over Hardcoding

```python
# Good
risk_per_trade = settings.risk.risk_per_trade

# Bad
risk_per_trade = 0.01  # Magic number
```

See [Configuration Reference](configuration.md) for all available settings.

### Structured Logging

```python
from keryxflow.core.logging import get_logger

logger = get_logger(__name__)

logger.info("signal_generated", symbol="BTC/USDT", type="long")
logger.warning("order_rejected", reason="Position too large")
logger.error("connection_failed", error=str(e))
```

## Testing

### Running Tests

```bash
# All tests
poetry run pytest

# With coverage
poetry run pytest --cov=keryxflow --cov-report=term-missing

# Specific module
poetry run pytest tests/test_aegis/

# Single test
poetry run pytest tests/test_aegis/test_quant.py::test_position_size_returns_zero_when_stop_equals_entry

# HTML coverage report
poetry run pytest --cov=keryxflow --cov-report=html
```

### Test Structure

Tests mirror the source structure:

```
tests/
├── conftest.py              # Shared fixtures, singleton reset
├── test_aegis/              # Risk management tests
├── test_agent/              # AI agent and tools tests
├── test_api/                # REST API and WebSocket tests
├── test_backtester/         # Backtester engine and reports
├── test_core/               # Engine, events, database tests
├── test_exchange/           # Exchange adapters and paper trading
├── test_hermes/             # TUI widget and app tests
├── test_memory/             # Episodic, semantic, manager tests
├── test_notifications/      # Discord, Telegram tests
├── test_optimizer/          # Grid search and comparator tests
├── test_oracle/             # Technical analysis and signals
└── integration/             # End-to-end integration tests
```

### Singleton Reset in conftest.py

The `setup_test_database` fixture (autouse) resets all global singletons before each test for isolation. **If you add a new singleton, you must add its reset to `tests/conftest.py`.**

Current singletons reset in `conftest.py`:

```python
config_module._settings = None
db_module._engine = None
db_module._async_session_factory = None
events_module._event_bus = None
demo_module._demo_client = None
kraken_module._kraken_client = None
okx_module._okx_client = None
paper_module._paper_engine = None
episodic_module._episodic_memory = None
semantic_module._semantic_memory = None
manager_module._memory_manager = None
tools_module._toolkit = None
executor_module._executor = None
cognitive_module._agent = None
reflection_module._reflection_engine = None
scheduler_module._scheduler = None
session_module._session = None
strategy_module._strategy_manager = None
strategy_gen_module._strategy_generator = None
risk_module._risk_manager = None
```

Forgetting to reset a singleton causes test pollution and flaky failures.

### Async Tests

Use `pytest-asyncio` in auto mode (configured in `pyproject.toml`):

```python
import pytest

@pytest.mark.asyncio
async def test_fetch_price():
    client = ExchangeClient(sandbox=True)
    await client.connect()
    price = await client.fetch_ticker("BTC/USDT")
    assert price["last"] > 0
```

Use `@pytest_asyncio.fixture` for async fixtures, `@pytest.fixture` for sync.

### Test Naming

Use descriptive names that explain behavior:

```python
def test_position_size_returns_zero_when_stop_equals_entry():
    ...

def test_circuit_breaker_triggers_on_max_drawdown():
    ...
```

### Coverage Requirements

- **Overall**: 80%+ recommended
- **Aegis module**: 100% required (risk management is critical)
- **New code**: Must include tests

## Adding New Features

### Adding a New Indicator

1. Add calculation to `keryxflow/oracle/technical.py`
2. Add to the `INDICATORS` dict
3. Add tests to `tests/test_oracle/test_technical.py`

### Adding a New Event Type

1. Add to `EventType` enum in `keryxflow/core/events.py`
2. Subscribe in relevant modules
3. Add tests

### Adding a New Exchange Adapter

1. Create a new client in `keryxflow/exchange/` (e.g., `newexchange.py`)
2. Implement the `ExchangeAdapter` ABC or `OrderExecutor` protocol
3. Add a singleton getter function
4. Add API key fields to `Settings` in `keryxflow/config.py`
5. Register in the exchange factory (`get_exchange_adapter()`)
6. Add reset to `tests/conftest.py` singleton list
7. Add tests in `tests/test_exchange/`

### Adding a New Agent Tool

1. Create the tool function in the appropriate file:
   - `perception_tools.py` for read-only market data
   - `analysis_tools.py` for computation
   - `execution_tools.py` for order execution (guarded)
2. Register it in the toolkit via `register_all_tools()`
3. Add tests in `tests/test_agent/`

### Adding a Configuration Option

1. Add field to the appropriate settings class in `keryxflow/config.py`
2. Use in code via `get_settings().section.field_name`
3. Document in `settings.toml`
4. Update [Configuration Reference](configuration.md)

## Debugging

### Debug Mode

```bash
export KERYXFLOW_LOG_LEVEL=DEBUG
poetry run keryxflow
```

Or in `settings.toml`:

```toml
[system]
log_level = "DEBUG"
```

### Common Issues

**Poetry issues:**
```bash
poetry cache clear . --all
rm -rf .venv poetry.lock
poetry install --with dev
```

**Import errors:** Ensure you're in the Poetry environment:
```bash
poetry shell
# or prefix commands with
poetry run python ...
```

**Async event loop errors:** Ensure async tests use `@pytest.mark.asyncio`.

**Test database:** Tests use isolated SQLite databases via `tmp_path` in `conftest.py`. Each test gets a fresh database.

## Code Quality

Run before committing:

```bash
# Lint
poetry run ruff check .

# Auto-fix lint issues
poetry run ruff check --fix .

# Format
poetry run ruff format .
```

## Quick Reference

```bash
poetry run keryxflow                    # Run paper trading
poetry run keryxflow-backtest ...       # Run backtest
poetry run keryxflow-optimize ...       # Run optimization
poetry run pytest                       # Run all tests
poetry run pytest --cov=keryxflow       # Tests with coverage
poetry run ruff check .                 # Lint
poetry run ruff format .                # Format
```
