# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

---

## [0.4.0] - 2026-02-02

### Added

#### Oracle Module - Intelligence Layer (`keryxflow/oracle/`)
- `technical.py` - Technical analysis engine with pandas-ta
  - RSI (Relative Strength Index) with overbought/oversold detection
  - MACD with crossover signals
  - Bollinger Bands with price position analysis
  - OBV (On-Balance Volume) with trend detection
  - ATR (Average True Range) for volatility measurement
  - EMA (Exponential Moving Average) alignment analysis
  - Aggregated signal strength and confidence scoring
  - Simple and technical explanations for each indicator

- `feeds.py` - News aggregator for market context
  - RSS feed fetching (CoinTelegraph, Decrypt)
  - CryptoPanic API integration
  - Currency detection in headlines
  - Sentiment analysis (bullish/bearish/neutral)
  - Recency-weighted sentiment scoring
  - Cache with configurable TTL
  - LLM-formatted output for Claude

- `brain.py` - LLM Brain using Claude
  - Market context analysis combining technical + news
  - Structured JSON response parsing
  - Bias detection (strongly bullish to strongly bearish)
  - Action recommendations (strong buy to strong sell)
  - Key factor extraction (bullish/bearish/risks)
  - Fallback context when LLM unavailable
  - Simple and technical display formatting

- `signals.py` - Hybrid signal generator
  - Combines technical analysis with LLM validation
  - LLM can veto technical signals based on context
  - ATR-based stop loss and take profit calculation
  - Risk/reward ratio computation
  - Signal deduplication to avoid spam
  - Entry/exit signal classification
  - Confidence-based strength assignment

#### Tests
- `tests/test_oracle/test_technical.py` - 19 tests for technical analysis
- `tests/test_oracle/test_feeds.py` - 21 tests for news feeds
- `tests/test_oracle/test_brain.py` - 13 tests for LLM brain
- `tests/test_oracle/test_signals.py` - 27 tests for signal generation
- Total: 140 tests passing (80 new + 60 existing)

### Technical Details
- pandas-ta for vectorized indicator calculations
- httpx for async HTTP requests
- feedparser for RSS parsing
- langchain-anthropic for Claude integration
- Graceful degradation when API keys not configured
- Configurable indicator parameters via settings

---

## [0.3.0] - 2026-02-02

### Added

#### Aegis Module - Risk Management (`keryxflow/aegis/`)
- `quant.py` - Quantitative calculations engine
  - Position sizing based on risk percentage (fixed fractional)
  - Kelly Criterion for optimal bet sizing
  - ATR-based stop loss calculation (volatility-adaptive)
  - Fixed percentage stop loss
  - Risk/reward ratio analysis with breakeven win rate
  - Drawdown calculation (current and max)
  - Sharpe ratio calculation
  - Trading expectancy calculation

- `risk.py` - Risk Manager for order approval
  - Order validation before execution
  - Enforces position size limits
  - Maximum open positions check
  - Daily drawdown monitoring
  - Minimum risk/reward ratio enforcement
  - Symbol whitelist validation
  - Stop-loss requirement enforcement
  - Human-readable rejection messages (simple + technical)
  - Suggested adjustments for rejected orders

- `circuit.py` - Circuit breaker for automatic trading halt
  - Daily drawdown trigger
  - Total drawdown trigger
  - Consecutive losses trigger
  - Rapid loss trigger (configurable time window)
  - Manual trip and reset
  - Cooldown period before reset
  - Trip event history tracking
  - Status reporting (simple + technical)

#### Tests
- `tests/test_aegis/test_quant.py` - 22 tests for quant engine
- `tests/test_aegis/test_risk.py` - 12 tests for risk manager
- `tests/test_aegis/test_circuit.py` - 13 tests for circuit breaker
- Total: 60 tests passing (47 new + 13 existing)

### Technical Details
- All calculations use numpy for performance
- Risk profiles integration (conservative/balanced/aggressive)
- Event bus integration for circuit breaker alerts
- Timezone-aware datetime handling throughout

---

## [0.2.0] - 2026-02-01

### Added

#### Exchange Module (`keryxflow/exchange/`)
- `client.py` - CCXT async wrapper for Binance connectivity
  - Connection management with automatic retry (tenacity)
  - Rate limiting respect
  - Ticker, OHLCV, order book, and balance fetching
  - Price feed streaming with event bus integration
  - Market and limit order execution
- `paper.py` - Paper trading engine for simulated execution
  - Virtual balance management persisted to SQLite
  - Position tracking with entry/exit and PnL calculation
  - Slippage simulation for realistic fills
  - Panic mode (close all positions instantly)
- `orders.py` - Order management abstraction
  - Unified interface over paper/live trading modes
  - Pending limit order tracking
  - Order status management

#### Main Application
- Rewritten `main.py` with full functionality:
  - ASCII banner and startup sequence
  - Live price feed from Binance (BTC/USDT, ETH/USDT)
  - Portfolio summary display
  - Graceful shutdown with Ctrl+C
  - Now runnable with `poetry run keryxflow`

#### Test Scripts
- `scripts/test_binance.py` - Binance connectivity test
- `scripts/test_paper_trading.py` - Paper trading simulation demo
- `scripts/run.py` - Standalone runner

#### Tests
- `tests/test_exchange/test_paper.py` - 13 comprehensive tests for paper trading
- `tests/conftest.py` - Enhanced with database isolation fixtures

### Changed
- Fixed `datetime.utcnow()` deprecation warnings across all modules
- Updated `core/models.py` to use timezone-aware UTC timestamps

### Technical Details
- Binance sandbox mode for safe testing
- Event-driven price updates
- Async database operations with proper session handling

---

## [0.1.0] - 2026-02-01

### Added

#### Project Structure
- Modular architecture with `keryxflow` package
- Poetry configuration with Python 3.12+ requirement
- Development tools: ruff, pytest, pytest-asyncio, pytest-cov

#### Core Modules (`keryxflow/core/`)
- `config.py` - Pydantic Settings for configuration management
- `logging.py` - Structured logging with structlog (simple + technical levels)
- `glossary.py` - 25+ trading terms with beginner-friendly explanations
- `database.py` - Async SQLite database with SQLModel
- `models.py` - Data models: Trade, Signal, Position, UserProfile, MarketContext, DailyStats
- `events.py` - Async event bus for pub/sub communication between modules

#### Aegis Module (`keryxflow/aegis/`)
- `profiles.py` - Risk profiles (conservative, balanced, aggressive)

#### Main Application
- `main.py` - Async entrypoint with graceful shutdown and signal handling

#### Documentation
- `README.md` - Complete documentation with:
  - Project philosophy and manifesto
  - Beginner-friendly explanations
  - Architecture overview
  - Installation and usage guides
  - FAQ section
- `CONTRIBUTING.md` - Contribution guidelines
- `LICENSE` - MIT License
- `.env.example` - Environment variables template
- `settings.toml` - Default configuration

#### Infrastructure
- `.gitignore` - Python/Poetry ignores
- `tests/conftest.py` - Shared pytest fixtures
- Virtual environment configured in-project (`.venv/`)

### Technical Details
- Python 3.12+ required (pandas-ta dependency)
- Async-first architecture with asyncio
- Event-driven communication between modules
- Structured logging with beginner and technical verbosity levels

---

## Version History

| Version | Date | Description |
|---------|------|-------------|
| 0.4.0 | 2026-02-02 | Oracle intelligence layer (technical + LLM) |
| 0.3.0 | 2026-02-02 | Aegis risk management layer |
| 0.2.0 | 2026-02-01 | Exchange layer + runnable MVP |
| 0.1.0 | 2026-02-01 | Project foundation - Phase 0 complete |

---

## Upcoming

### [0.5.0] - Planned
- Hermes TUI (Textual interface)
- Onboarding wizard
- Help modal with glossary

### [1.0.0] - Planned
- Full integration
- Backtesting engine
- Production ready
