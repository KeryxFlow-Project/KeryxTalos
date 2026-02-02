# KeryxFlow Development Guide

This guide covers setting up a development environment and contributing to KeryxFlow.

## Prerequisites

- **Python 3.12+** (required for pandas-ta)
- **Poetry** for dependency management
- **Git** for version control

### Installing Poetry

```bash
# macOS / Linux
curl -sSL https://install.python-poetry.org | python3 -

# Windows (PowerShell)
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
```

---

## Setup

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
# Binance (required for live data)
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret

# Anthropic (required for LLM features)
ANTHROPIC_API_KEY=your_key
```

### Verify Installation

```bash
# Run the application
poetry run keryxflow

# Run tests
poetry run pytest

# Check code quality
poetry run ruff check .
```

---

## Project Structure

```
keryxflow/
├── keryxflow/           # Main package
│   ├── core/            # Foundation (events, database, logging)
│   ├── hermes/          # Terminal UI
│   ├── oracle/          # Intelligence (TA, LLM)
│   ├── aegis/           # Risk management
│   ├── exchange/        # Binance integration
│   ├── backtester/      # Historical testing
│   ├── optimizer/       # Parameter optimization
│   └── notifications/   # Alerts (Telegram, Discord)
├── tests/               # Tests (mirrors keryxflow structure)
├── docs/                # Documentation
├── scripts/             # Utility scripts
├── settings.toml        # Configuration
└── pyproject.toml       # Dependencies
```

---

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

Branch naming conventions:
- `feature/` - New features
- `fix/` - Bug fixes
- `refactor/` - Code improvements
- `docs/` - Documentation
- `test/` - Test additions

### 2. Make Changes

Follow the coding standards below.

### 3. Run Tests

```bash
# All tests
poetry run pytest

# Specific module
poetry run pytest tests/test_aegis/

# With coverage
poetry run pytest --cov=keryxflow --cov-report=term-missing

# Single test
poetry run pytest tests/test_aegis/test_quant.py::test_position_size
```

### 4. Check Code Quality

```bash
# Lint
poetry run ruff check .

# Auto-fix issues
poetry run ruff check --fix .

# Format
poetry run ruff format .
```

### 5. Commit

```bash
git add .
git commit -m "feat(oracle): add RSI divergence detection"
```

Commit message format:
```
<type>(<scope>): <description>

[optional body]
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

Scopes: `core`, `hermes`, `oracle`, `aegis`, `exchange`, `backtester`, `optimizer`

### 6. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

---

## Coding Standards

### Type Hints (Required)

All functions must have complete type annotations:

```python
# Good
def calculate_position_size(
    balance: float,
    risk_pct: float,
    entry: float,
    stop_loss: float,
) -> float:
    ...

# Bad
def calculate_position_size(balance, risk_pct, entry, stop_loss):
    ...
```

### Async by Default

All I/O operations must be async:

```python
# Good
async def fetch_price(symbol: str) -> float:
    ticker = await self.exchange.fetch_ticker(symbol)
    return ticker["last"]

# Bad
def fetch_price(symbol: str) -> float:
    return requests.get(...)  # Blocks event loop
```

### Event-Driven Communication

Modules communicate via events, not direct calls:

```python
# Good
await event_bus.publish(Event(
    type=EventType.SIGNAL_GENERATED,
    data={"symbol": "BTC/USDT", "signal_type": "long"}
))

# Bad
aegis.approve_order(order)  # Direct coupling
```

### Configuration Over Hardcoding

```python
# Good
risk_per_trade = settings.risk.risk_per_trade

# Bad
risk_per_trade = 0.01  # Magic number
```

### Docstrings

Use Google-style docstrings for public functions:

```python
def calculate_position_size(
    balance: float,
    risk_pct: float,
    entry: float,
    stop_loss: float,
) -> float:
    """Calculate position size based on risk percentage.

    Args:
        balance: Account balance in quote currency.
        risk_pct: Risk percentage per trade (0.01 = 1%).
        entry: Entry price.
        stop_loss: Stop loss price.

    Returns:
        Position size in base currency.

    Raises:
        ValueError: If stop_loss equals entry price.
    """
```

---

## Testing Guidelines

### Test Structure

Tests mirror the source structure:

```
tests/
├── conftest.py              # Shared fixtures
├── test_core/
│   ├── test_engine.py
│   └── test_events.py
├── test_aegis/
│   ├── test_quant.py
│   └── test_risk.py
└── test_oracle/
    └── test_signals.py
```

### Test Naming

Use descriptive names that explain behavior:

```python
def test_position_size_returns_zero_when_stop_equals_entry():
    ...

def test_circuit_breaker_triggers_on_max_drawdown():
    ...
```

### Fixtures

Use pytest fixtures for common setup:

```python
# conftest.py
@pytest.fixture
def settings():
    return Settings(
        risk=RiskSettings(risk_per_trade=0.01),
    )

@pytest.fixture
def risk_manager(settings):
    return RiskManager(settings.risk)
```

### Async Tests

Use `pytest-asyncio` for async tests:

```python
import pytest

@pytest.mark.asyncio
async def test_fetch_price():
    client = ExchangeClient(sandbox=True)
    await client.connect()
    price = await client.fetch_ticker("BTC/USDT")
    assert price["last"] > 0
```

### Coverage Requirements

- **Overall**: 80%+ recommended
- **Aegis module**: 100% required (risk management is critical)
- **New code**: Must include tests

---

## Debugging

### Logging

Use structured logging:

```python
from keryxflow.core.logging import get_logger

logger = get_logger(__name__)

logger.info("signal_generated", symbol="BTC/USDT", type="long")
logger.warning("order_rejected", reason="Position too large")
logger.error("connection_failed", error=str(e))
```

### Debug Mode

Set log level to DEBUG:

```bash
export KERYXFLOW_LOG_LEVEL=DEBUG
poetry run keryxflow
```

Or in `settings.toml`:

```toml
[system]
log_level = "DEBUG"
```

### Interactive Debugging

```python
import pdb; pdb.set_trace()  # Python debugger
```

Or use VS Code / PyCharm debugger with breakpoints.

---

## Common Tasks

### Adding a New Indicator

1. Add calculation to `keryxflow/oracle/technical.py`:

```python
def _calculate_new_indicator(self, df: pd.DataFrame) -> IndicatorResult:
    # Calculate indicator
    values = ...

    return IndicatorResult(
        name="new_indicator",
        value=values,
        signal=self._interpret_signal(values),
        strength=self._calculate_strength(values),
    )
```

2. Add to `INDICATORS` dict
3. Add tests to `tests/test_oracle/test_technical.py`
4. Update documentation

### Adding a New Event Type

1. Add to `EventType` enum in `keryxflow/core/events.py`:

```python
class EventType(str, Enum):
    # ...existing...
    NEW_EVENT = "new_event"
```

2. Create convenience function:

```python
def new_event(data: dict) -> Event:
    return Event(type=EventType.NEW_EVENT, data=data)
```

3. Subscribe in relevant modules
4. Add tests

### Adding a Configuration Option

1. Add to appropriate settings class in `keryxflow/config.py`:

```python
class NewSettings(BaseSettings):
    new_option: str = "default"
```

2. Add to `settings.toml` with documentation
3. Use in code via `settings.new.new_option`

---

## Architecture Decisions

### Why Event-Driven?

- **Loose coupling**: Modules don't depend on each other
- **Testability**: Easy to mock events
- **Extensibility**: Add features without modifying existing code

### Why Async?

- **Non-blocking**: UI stays responsive during I/O
- **Concurrency**: Handle multiple price feeds simultaneously
- **Modern Python**: Native async/await support

### Why SQLite?

- **Simple**: No server to manage
- **Portable**: Single file database
- **Async**: aiosqlite for non-blocking queries
- **Good enough**: Paper trading doesn't need scale

### Why Textual for TUI?

- **Modern**: CSS-like styling, reactive updates
- **Python native**: No external dependencies
- **Rich**: Beautiful output with minimal code

---

## Troubleshooting

### Poetry Issues

```bash
# Clear cache
poetry cache clear . --all

# Reinstall
rm -rf .venv poetry.lock
poetry install
```

### Import Errors

Ensure you're in the Poetry environment:

```bash
poetry shell
# or
poetry run python ...
```

### Test Database

Tests use isolated in-memory databases via fixtures in `conftest.py`.

### Async Event Loop Errors

Ensure async tests are marked:

```python
@pytest.mark.asyncio
async def test_something():
    ...
```

---

## Getting Help

- **GitHub Issues**: Report bugs or request features
- **Pull Requests**: Discuss implementation details
- **Code Comments**: Document complex logic

---

## Before Submitting

Checklist:

- [ ] Tests pass: `poetry run pytest`
- [ ] Lint passes: `poetry run ruff check .`
- [ ] Format applied: `poetry run ruff format .`
- [ ] Docstrings for public functions
- [ ] Type hints complete
- [ ] CHANGELOG updated (for features/fixes)
- [ ] Documentation updated (if needed)

---

## Quick Reference

```bash
# Run app
poetry run keryxflow

# Run tests
poetry run pytest

# Run specific test
poetry run pytest tests/test_aegis/test_quant.py::test_position_size

# Coverage report
poetry run pytest --cov=keryxflow --cov-report=html

# Lint
poetry run ruff check .

# Format
poetry run ruff format .

# Backtest
poetry run keryxflow-backtest --symbol BTC/USDT --start 2024-01-01 --end 2024-06-30

# Optimize
poetry run keryxflow-optimize --symbol BTC/USDT --start 2024-01-01 --end 2024-06-30 --grid quick
```
