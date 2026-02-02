# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

---

## [0.6.0] - 2026-02-01

### Added

#### Integration Loop - Trading Engine (`keryxflow/core/engine.py`)
- **`TradingEngine`** - Central orchestrator connecting all modules
  - Price Update → OHLCV Buffer → Oracle → Aegis → Paper Engine flow
  - Event subscription for PRICE_UPDATE, SYSTEM_PAUSED, SYSTEM_RESUMED, PANIC_TRIGGERED
  - Automatic signal generation at configurable intervals (default: 60s)
  - Order creation with position sizing from RiskManager
  - Order approval through Aegis before execution
  - Event publishing: ORDER_APPROVED, ORDER_REJECTED, ORDER_FILLED, POSITION_CLOSED

- **`OHLCVBuffer`** - Real-time candle aggregation
  - Accumulates price updates into 1-minute OHLCV candles
  - Configurable max candles buffer (default: 100)
  - Multi-symbol support
  - Returns pandas DataFrame for technical analysis

- **Splash screen** with KERYX ASCII banner on startup
  - Auto-dismiss after 2.5 seconds (or press any key)
  - Bitcoin orange theme (#F7931A) for brand consistency

- **Help modal banner** with KERYX ASCII art
  - Accessible via `?` key
  - Bitcoin orange themed

#### Widget Integrations
- **`PositionsWidget`** now connected to `PaperTradingEngine`
  - Real-time position fetching
  - Live PnL updates with price changes
- **`AegisWidget`** now connected to `RiskManager`
  - Real-time risk status display
  - Daily PnL, drawdown, and position count
- **`LogsWidget`** receives events from full trading loop
  - ORDER_APPROVED, ORDER_REJECTED, ORDER_FILLED events logged

#### Tests
- `tests/test_core/test_engine.py` - 17 tests for trading engine
  - OHLCVBuffer: candle creation, updates, DataFrame output
  - TradingEngine: initialization, start/stop, status
  - Analysis flow: min candles requirement, analysis trigger
  - Event handling: pause, resume, panic, price updates

### Changed
- `keryxflow/hermes/app.py` - TUI now creates and starts TradingEngine
  - Connects widgets to real data sources (RiskManager, PaperEngine)
  - Subscribes to ORDER_APPROVED, ORDER_REJECTED events
- `main.py` refactored to initialize components then launch TUI
- Help modal widened to accommodate banner (60 chars)

### Technical Details
- pytest-mock added to dev dependencies for mocking in tests
- `get_ohlcv()` now includes current (incomplete) candle
- Event handlers receive Event objects consistently
- 227 tests passing (17 new + 210 existing)

---

## [0.5.0] - 2026-02-01

### Added

#### Hermes Module - Terminal User Interface (`keryxflow/hermes/`)
- `app.py` - Main TUI application with Textual framework
  - Multi-panel layout (chart, positions, oracle, aegis, stats, logs)
  - Real-time updates via event bus subscription
  - Keyboard shortcuts: Q (quit), P (panic), Space (pause), ? (help), L (logs), S (symbols)
  - Responsive layout adapting to terminal size

- `theme.tcss` - CSS styles for the TUI
  - Cyberpunk-inspired dark theme
  - Color classes for status indicators (armed, tripped, price-up, price-down)
  - Consistent styling across all widgets

- `onboarding.py` - First-run wizard
  - Experience level selection (beginner, intermediate, advanced)
  - Risk profile selection (conservative, balanced, aggressive)
  - Quick setup wizard for paper trading mode
  - User profile dataclass for storing preferences

#### Hermes Widgets (`keryxflow/hermes/widgets/`)
- `chart.py` - ASCII price chart widget
  - Real-time price visualization with ASCII characters
  - Price labels and axis
  - Technical indicator display (RSI bar, MACD arrow, trend emoji)
  - Progress bar rendering

- `positions.py` - Open positions display
  - DataTable showing symbol, quantity, entry, current price
  - PnL and PnL% with color coding (green/red)
  - Total PnL calculation

- `oracle.py` - Market context and signals display
  - Market bias indicator (bullish/bearish/neutral)
  - Current signal with entry price
  - Confidence bar visualization
  - Context and signal summary methods

- `aegis.py` - Risk management status widget
  - Circuit breaker status (ARMED/TRIPPED)
  - Daily PnL display
  - Risk usage bar with color thresholds
  - Position count vs maximum

- `stats.py` - Trading statistics widget
  - Win rate with progress bar
  - Average win/loss amounts
  - Expectancy calculation per trade
  - Trade recording with automatic stats update

- `logs.py` - Activity log widget
  - RichLog for formatted output
  - Level-based icons (info, success, warning, error, trade, signal)
  - Timestamp formatting
  - Maximum entries limit (100)

- `help.py` - Help modal with glossary integration
  - Term lookup from core glossary
  - Search functionality
  - Glossary browser by category
  - Quick help widget for contextual hints
  - Keyboard shortcuts reference

#### Tests
- `tests/test_hermes/test_widgets.py` - 47 tests for widget logic
  - ChartWidget: price tracking, progress bars, chart rendering
  - LogsWidget: entries, formatting, icons
  - StatsWidget: expectancy, win rate bar, properties
  - AegisWidget: trip state, can_trade logic, risk bar
  - OracleWidget: context/signal storage, summaries
  - PositionsWidget: add/remove/total PnL

- `tests/test_hermes/test_help.py` - 14 tests for help/glossary
  - Modal initialization
  - Glossary integration
  - Category validation
  - Search functionality

- `tests/test_hermes/test_onboarding.py` - 9 tests for onboarding
  - UserProfile dataclass
  - Wizard step progression
  - Selection actions

- Total: 210 tests passing (70 new + 140 existing)

### Technical Details
- Textual ^0.50 for TUI framework
- CSS-based styling with TCSS files
- Event bus integration for real-time updates
- Modular widget architecture
- Glossary with 25+ trading terms (simple + technical explanations)
- Experience-based verbosity levels

---

## [0.4.0] - 2026-02-01

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

## [0.3.0] - 2026-02-01

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
| 0.6.0 | 2026-02-01 | Integration loop (TradingEngine orchestrator) |
| 0.5.0 | 2026-02-01 | Hermes TUI (Textual interface) |
| 0.4.0 | 2026-02-01 | Oracle intelligence layer (technical + LLM) |
| 0.3.0 | 2026-02-01 | Aegis risk management layer |
| 0.2.0 | 2026-02-01 | Exchange layer + runnable MVP |
| 0.1.0 | 2026-02-01 | Project foundation - Phase 0 complete |

---

## Upcoming

### [0.7.0] - Planned
- Backtesting engine
- Historical data replay
- Strategy performance metrics

### [1.0.0] - Planned
- Live trading mode
- Production ready
- Full documentation
