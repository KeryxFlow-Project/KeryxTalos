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
│   ├── core/        # Infrastructure (database, events, logging)
│   ├── hermes/      # Terminal UI
│   ├── oracle/      # Intelligence (technical analysis, LLM)
│   ├── aegis/       # Risk management
│   └── exchange/    # Binance integration
└── tests/           # Mirror structure of keryxflow/
```

### Module Responsibilities

| Module | Purpose | Key Principle |
|--------|---------|---------------|
| `core` | Shared infrastructure | Stability over features |
| `hermes` | User interface | Clarity over decoration |
| `oracle` | Signal generation | Accuracy over speed |
| `aegis` | Risk management | Safety over opportunity |
| `exchange` | API connectivity | Reliability over performance |

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

### What to Test

| Module | Focus |
|--------|-------|
| `aegis` | Math correctness, edge cases, safety limits |
| `oracle` | Indicator accuracy, signal logic |
| `exchange` | Order validation, error handling |
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

### No YOLO

Never merge code that:
- Bypasses risk checks
- Removes safety limits
- Allows unlimited position sizes
- Disables circuit breakers

## Questions?

- Open a discussion on GitHub
- Tag maintainers in issues if stuck

---

**Remember: We're building tools for financial sovereignty. Quality matters.**

Stack sats. ₿
