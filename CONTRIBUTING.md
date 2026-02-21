# Contributing to KeryxFlow

Thanks for considering contributing to KeryxFlow. This document covers how to contribute. For development setup, coding standards, testing, and architecture details, see the [Development Guide](docs/development.md).

## Philosophy

- **Bitcoin accumulation** is the end goal. Everything else is a means.
- **Math over emotions**. Risk management is non-negotiable.
- **Transparency over trust**. Open source isn't optional, it's the point.
- **Clean code**. If it's not readable, it's not maintainable.

## Code of Conduct

- Be respectful and constructive
- Focus on the code, not the person
- Help others learn

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

### Submitting Code

#### 1. Set Up Your Environment

See the [Development Guide](docs/development.md) for full setup instructions.

```bash
git clone https://github.com/YOUR_USERNAME/keryxflow.git
cd keryxflow
poetry install --with dev
cp .env.example .env
```

#### 2. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

Branch naming conventions:
- `feature/` — New features
- `fix/` — Bug fixes
- `refactor/` — Code improvements
- `docs/` — Documentation
- `test/` — Test additions

#### 3. Make Your Changes

Follow the coding standards and patterns documented in the [Development Guide](docs/development.md).

#### 4. Verify Your Changes

```bash
poetry run pytest                       # All tests pass
poetry run ruff check .                 # No lint errors
poetry run ruff format .                # Code formatted
```

#### 5. Commit

```
<type>(<scope>): <description>
```

**Types:** `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

**Scopes:** `core`, `hermes`, `oracle`, `aegis`, `exchange`, `backtester`, `optimizer`, `notifications`, `memory`, `agent`, `api`

Examples:
```
feat(oracle): add RSI divergence detection
fix(aegis): correct position size calculation for futures
refactor(hermes): extract chart widget to separate module
test(exchange): add paper trading order flow tests
```

#### 6. Push and Create PR

```bash
git push -u origin feature/your-feature-name
gh pr create --title "feat(oracle): add RSI divergence detection"
```

- Ensure CI passes before requesting review
- Link related issues in the PR description

## Financial Safety Rules

KeryxFlow handles real money. Extra care is required for certain modules.

### Aegis Changes (Risk Management)

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

**Never merge code that:**
- Bypasses risk checks or guardrail validation
- Removes or weakens safety limits
- Allows unlimited position sizes
- Disables circuit breakers

## Release Process

### 1. Bump Version

Update the version in **both** files (they must stay in sync):

```bash
# keryxflow/__init__.py
__version__ = "0.X.0"

# pyproject.toml
version = "0.X.0"
```

### 2. Update Changelog

Add a new section to `CHANGELOG.md` with the version and date.

### 3. Commit and Tag

```bash
git add pyproject.toml keryxflow/__init__.py CHANGELOG.md
git commit -m "chore(core): bump version to 0.X.0"
git tag v0.X.0
git push origin main --tags
```

### 4. Build and Publish

```bash
poetry build
twine check dist/*
twine upload dist/*
```

## Questions?

- Open a discussion on GitHub
- Tag maintainers in issues if stuck

---

**Remember: We're building tools for financial sovereignty. Quality matters.**

Stack sats.
