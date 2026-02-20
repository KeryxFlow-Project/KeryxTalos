# Contributing to KeryxFlow

First off, thanks for considering contributing to KeryxFlow. This project exists because people like you believe in financial sovereignty and open-source software.

## Philosophy

Before contributing, understand what KeryxFlow stands for:

- **Bitcoin accumulation** is the end goal. Everything else is a means.
- **Math over emotions**. Risk management is non-negotiable.
- **Transparency over trust**. Open source isn't optional, it's the point.
- **Clean code**. If it's not readable, it's not maintainable.

## Code of Conduct

- Be respectful and constructive
- Focus on the code, not the person
- No shilling altcoins or "number go up" mentality
- Help others learn

## Getting Started

### Prerequisites

- Python 3.11+
- Poetry
- Git

### Setup Development Environment

```bash
# Fork and clone
git clone https://github.com/YOUR_USERNAME/keryxflow.git
cd keryxflow

# Install dependencies (including dev)
poetry install --with dev

# Create your branch from dev
git checkout dev
git pull origin dev
git checkout -b feature/phase-11-guardrails
```

## Git Workflow

### Branches

| Branch | Purpose | Protection |
|--------|---------|------------|
| `main` | Stable releases | PRs only, reviewed |
| `dev` | Continuous integration | PRs only |
| `feature/phase-N-name` | Roadmap features | - |
| `fix/issue-N-description` | Bug fixes | - |
| `docs/description` | Documentation only | - |

### Flow

```
feature/phase-N-name
         ↓ PR (code review)
        dev
         ↓ PR (after full validation)
        main
```

**Never push directly to `main` or `dev`.**

### Branch Naming Convention

```bash
# Features (roadmap phases)
feature/phase-11-guardrails
feature/phase-12-memory

# Bug fixes (reference issue number)
fix/issue-9-aggregate-risk
fix/issue-23-price-feed

# Documentation only
docs/update-trading-guide
docs/add-api-reference

# Refactoring
refactor/oracle-signal-flow
refactor/extract-portfolio-state
```

### Complete Example

```bash
# 1. Sync with dev
git checkout dev
git pull origin dev

# 2. Create feature branch
git checkout -b feature/phase-11-guardrails

# 3. Develop and commit
git add keryxflow/aegis/guardrails.py
git commit -m "feat(aegis): add immutable trading guardrails"

# 4. Push and create PR
git push -u origin feature/phase-11-guardrails
gh pr create --base dev --title "feat(aegis): implement guardrails layer (Phase 11)"

# 5. After approval and merge to dev, delete local branch
git checkout dev
git pull origin dev
git branch -d feature/phase-11-guardrails
```

### Running Tests

```bash
# All tests
poetry run pytest

# With coverage
poetry run pytest --cov=keryxflow --cov-report=term-missing

# Specific module
poetry run pytest tests/test_aegis/
```

### Code Quality

We use `ruff` for linting and formatting:

```bash
# Check for issues
poetry run ruff check .

# Auto-fix issues
poetry run ruff check --fix .

# Format code
poetry run ruff format .
```

**Run these before committing.** PRs with lint errors will not be merged.

## Project Structure

```
keryxflow/
├── keryxflow/
│   ├── core/            # Infrastructure (database, events, logging, models)
│   ├── hermes/          # Terminal UI (Textual framework)
│   ├── oracle/          # Intelligence (technical analysis, LLM signals)
│   ├── aegis/           # Risk management (guardrails, position sizing)
│   ├── exchange/        # Exchange connectivity (CCXT, paper trading)
│   ├── agent/           # AI tool framework (Cognitive Agent, tool use)
│   ├── memory/          # Trade memory (episodic, semantic, patterns)
│   ├── backtester/      # Strategy backtesting (data loader, engine, reports)
│   ├── optimizer/       # Parameter optimization (grid search, comparator)
│   └── notifications/   # Notification channels (Discord, Telegram webhooks)
└── tests/               # Mirror structure of keryxflow/
```

### Module Responsibilities

| Module | Purpose | Key Principle |
|--------|---------|---------------|
| `core` | Shared infrastructure (events, DB, models) | Stability over features |
| `hermes` | Terminal UI (Textual framework) | Clarity over decoration |
| `oracle` | Signal generation (indicators, LLM) | Accuracy over speed |
| `aegis` | Risk management (guardrails, sizing) | Safety over opportunity |
| `exchange` | Exchange connectivity (CCXT, paper) | Reliability over performance |
| `agent` | AI tool framework (Cognitive Agent) | Autonomy with guardrails |
| `memory` | Trade memory (episodic, semantic) | Learning over forgetting |
| `backtester` | Strategy validation (historical data) | Accuracy over speed |
| `optimizer` | Parameter optimization (grid search) | Thoroughness over shortcuts |
| `notifications` | Alert channels (Discord, Telegram) | Delivery over silence |

## How to Contribute

### Reporting Bugs

Open an issue with:

1. **Description**: What happened vs. what you expected
2. **Steps to reproduce**: Minimal steps to trigger the bug
3. **Environment**: OS, Python version, KeryxFlow version
4. **Logs**: Relevant error messages or stack traces

### Suggesting Features

Open an issue with:

1. **Problem**: What problem does this solve?
2. **Solution**: How do you propose to solve it?
3. **Alternatives**: What other solutions did you consider?
4. **Scope**: Is this a small tweak or a major change?

Features that align with the project philosophy are more likely to be accepted.

### Submitting Code

#### 1. Pick an Issue

- Look for issues labeled `good first issue` or `help wanted`
- Comment on the issue to claim it
- Ask questions if requirements are unclear

#### 2. Write the Code

Follow these principles:

**Keep it simple**
- Solve the problem, nothing more
- No premature optimization
- No speculative features

**Make it readable**
- Clear variable and function names
- Small functions with single responsibility
- Comments explain "why", code explains "what"

**Make it safe**
- Validate inputs at boundaries
- Handle errors explicitly
- No silent failures in trading logic

**Make it testable**
- Write tests for new functionality
- Maintain or improve coverage
- Test edge cases, especially in `aegis`

#### 3. Commit Guidelines

Format:
```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code change that neither fixes nor adds
- `test`: Adding or updating tests
- `docs`: Documentation only
- `chore`: Maintenance tasks

Examples:
```
feat(oracle): add RSI divergence detection

fix(aegis): correct position size calculation for futures

refactor(hermes): extract chart widget to separate module

test(exchange): add paper trading order flow tests
```

#### 4. Submit Pull Request

- **Target the `dev` branch** (not main!)
- Fill out the PR template
- Link related issues
- Ensure CI passes

PR title should follow commit format:
```
feat(oracle): add support for custom indicators
```

Creating a PR:
```bash
gh pr create --base dev --title "feat(oracle): add support for custom indicators"
```

## Architecture Guidelines

### Event-Driven Communication

Modules communicate via events, not direct calls:

```python
# Good
await event_bus.publish(SignalGenerated(symbol="BTC/USDT", direction="long"))

# Bad
aegis.approve_order(order)  # Direct coupling
```

### Event Types

Key event types used in the system (`core/events.py`):

| Category | Events |
|----------|--------|
| Price | `PRICE_UPDATE`, `OHLCV_UPDATE` |
| Signal | `SIGNAL_GENERATED`, `SIGNAL_VALIDATED`, `SIGNAL_REJECTED` |
| Order | `ORDER_REQUESTED`, `ORDER_APPROVED`, `ORDER_REJECTED`, `ORDER_FILLED`, `ORDER_CANCELLED` |
| Position | `POSITION_OPENED`, `POSITION_UPDATED`, `POSITION_CLOSED` |
| Risk | `RISK_ALERT`, `CIRCUIT_BREAKER_TRIGGERED`, `DRAWDOWN_WARNING` |
| System | `SYSTEM_STARTED`, `SYSTEM_STOPPED`, `SYSTEM_PAUSED`, `SYSTEM_RESUMED`, `PANIC_TRIGGERED` |

When adding new event types, add them to the `EventType` enum in `core/events.py`.

### Async by Default

All I/O operations must be async:

```python
# Good
async def fetch_price(symbol: str) -> float:
    return await exchange.get_ticker(symbol)

# Bad
def fetch_price(symbol: str) -> float:
    return requests.get(...)  # Blocks event loop
```

### Configuration Over Hardcoding

```python
# Good
risk_per_trade = settings.risk.risk_per_trade

# Bad
risk_per_trade = 0.01  # Magic number
```

### Type Hints Required

```python
# Good
def calculate_position_size(
    balance: float,
    risk_pct: float,
    entry: float,
    stop_loss: float
) -> float:
    ...

# Bad
def calculate_position_size(balance, risk_pct, entry, stop_loss):
    ...
```

## Testing Guidelines

### Test Structure

```
tests/
├── conftest.py          # Shared fixtures
├── test_aegis/
│   ├── test_quant.py    # Unit tests for quant.py
│   └── test_risk.py     # Unit tests for risk.py
└── test_integration/
    └── test_trading_flow.py
```

### Singleton Reset in Tests

The `conftest.py` fixture `setup_test_database` resets all global singletons before each test to ensure isolation. **If you add a new singleton, you must add its reset to this fixture.** Current singletons that are reset:

- `config._settings`, `database._engine`, `database._async_session_factory`
- `events._event_bus`, `paper._paper_engine`
- `episodic._episodic_memory`, `semantic._semantic_memory`, `manager._memory_manager`
- `tools._toolkit`, `executor._executor`, `cognitive._agent`
- `reflection._reflection_engine`, `scheduler._scheduler`, `session._session`
- `strategy._strategy_manager`, `risk._risk_manager`

Forgetting to reset a singleton will cause test pollution and flaky failures.

### What to Test

| Module | Focus |
|--------|-------|
| `aegis` | Math correctness, edge cases, safety limits |
| `oracle` | Indicator accuracy, signal logic |
| `exchange` | Order validation, error handling |
| `agent` | Tool execution, guardrail enforcement, cycle logic |
| `memory` | Episode recording, rule matching, pattern storage |
| `backtester` | Data loading, PnL calculation, report accuracy |
| `optimizer` | Grid generation, result comparison |
| `notifications` | Message formatting, delivery error handling |
| `hermes` | Widget rendering, keyboard handling |

### Test Naming

```python
def test_position_size_returns_zero_when_stop_equals_entry():
    ...

def test_circuit_breaker_triggers_on_max_drawdown():
    ...
```

## Financial Safety

KeryxFlow handles real money. Extra care is required:

### Aegis Changes

Any changes to `aegis/` require:
- 100% test coverage for the change
- Review by at least one maintainer
- Explicit approval in PR comments

### Order Execution Changes

Any changes to order execution in `exchange/` require:
- Paper trading verification
- Edge case documentation
- Rollback plan

### Guardrail Integrity

The `TradingGuardrails` class in `aegis/guardrails.py` is a frozen dataclass with hardcoded safety limits. These limits are immutable at runtime and must never be weakened:

- `MAX_POSITION_SIZE_PCT = 10%` — Single position cap
- `MAX_TOTAL_EXPOSURE_PCT = 50%` — Total portfolio exposure
- `MAX_DAILY_LOSS_PCT = 5%` — Daily circuit breaker trigger
- `MAX_TOTAL_DRAWDOWN_PCT = 20%` — Maximum drawdown from peak

### No YOLO

Never merge code that:
- Bypasses risk checks or guardrail validation
- Removes or weakens safety limits
- Allows unlimited position sizes
- Disables circuit breakers
- Modifies `TradingGuardrails` to loosen constraints

## Questions?

- Open a discussion on GitHub
- Tag maintainers in issues if stuck

---

**Remember: We're building tools for financial sovereignty. Quality matters.**

Stack sats. ₿
