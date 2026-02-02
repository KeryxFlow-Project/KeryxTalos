# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

---

## [0.11.0] - 2026-02-02

### Added

#### Guardrails Layer - Immutable Safety Limits (`keryxflow/aegis/`)

- **`guardrails.py`** - Immutable trading guardrails (frozen dataclass)
  - `TradingGuardrails` - Hardcoded limits that cannot be modified at runtime
  - `GuardrailEnforcer` - Validates orders against all limits
  - `GuardrailCheckResult` - Detailed rejection information
  - `GuardrailViolation` enum for violation types

- **`portfolio.py`** - Portfolio state tracking for aggregate risk
  - `PositionState` - Individual position tracking with risk metrics
  - `PortfolioState` - Aggregate portfolio state
  - `total_risk_at_stop` property - Key metric for Issue #9 fix
  - Position add/close with P&L tracking
  - Daily/weekly/hourly reset methods

- **Guardrail Limits (Immutable)**
  | Limit | Value | Purpose |
  |-------|-------|---------|
  | MAX_POSITION_SIZE_PCT | 10% | Max single position |
  | MAX_TOTAL_EXPOSURE_PCT | 50% | Max total exposure |
  | MIN_CASH_RESERVE_PCT | 20% | Minimum cash reserve |
  | MAX_LOSS_PER_TRADE_PCT | 2% | Max risk per trade |
  | MAX_DAILY_LOSS_PCT | 5% | Max daily loss |
  | MAX_WEEKLY_LOSS_PCT | 10% | Max weekly loss |
  | CONSECUTIVE_LOSSES_HALT | 5 | Halt after N losses |
  | MAX_TRADES_PER_DAY | 50 | Rate limit |
  | MAX_TRADES_PER_HOUR | 10 | Rate limit |

### Changed

- **`risk.py`** - Two-layer validation integrated
  - GuardrailEnforcer runs FIRST (immutable limits)
  - RiskManager runs second (configurable limits)
  - Portfolio state management methods added
  - `get_status()` includes aggregate risk metrics

### Fixed

- **Issue #9**: Position sizing allows excessive drawdown
  - Aggregate risk now tracked via `PortfolioState.total_risk_at_stop`
  - 3 positions at 2% risk each (6% total) are now REJECTED
  - Guardrails check aggregate risk against daily loss limit

#### TUI Stability Improvements
- **Price Fetching** - Fixed event loop conflicts by using sync ccxt in threads
  - Replaced async ccxt calls with `asyncio.to_thread(fetch_sync)`
  - Prices now display correctly in the TUI
- **Oracle Widget** - Fixed signal display stuck on "Analyzing market..."
  - Added direct Oracle updates from TUI price loop
  - Signal generation now uses sync wrapper in thread
- **Trading Engine Initialization** - Fixed startup sequence
  - Engine now starts before TUI to avoid async conflicts
  - OHLCV buffer preloads historical candles on startup
- **Event Bus Compatibility** - Resolved Textual event loop conflicts
  - Removed `call_from_thread` usage that caused crashes
  - Direct widget updates in async workers

---

## [0.10.0] - 2026-02-02

### Added

#### Multi-Timeframe Analysis (`keryxflow/oracle/` and `keryxflow/core/`)
- **`MultiTimeframeBuffer`** - Buffer for managing OHLCV across multiple timeframes
  - `TimeframeConfig` dataclass for configuring individual timeframes
  - `TimeframeBuffer` for single timeframe candle accumulation
  - Price updates propagate to all configured timeframes
  - Resample from base timeframe to higher timeframes
  - Primary and filter timeframe designation

- **`MTFAnalyzer`** - Multi-timeframe analysis coordinator
  - `MultiTimeframeAnalysis` dataclass for aggregated results
  - Analyzes all timeframes and determines filter trend
  - Alignment detection across timeframes
  - Simple and technical summaries
  - Fallback to highest available timeframe for filter

- **`MTFSignalGenerator`** - Signal generator with MTF support
  - Extends base `SignalGenerator` with MTF capabilities
  - Higher timeframe trend filtering (hierarchical filter)
  - Alignment-based confidence adjustment (+20% aligned, -20% divergent)
  - Fallback to single-timeframe when only DataFrame provided
  - Filter rules: BULLISH allows LONG only, BEARISH allows SHORT only

- **`apply_trend_filter()`** - Filter function for signal validation
  - Applies higher timeframe trend to filter signals
  - Configurable minimum confidence threshold
  - NEUTRAL filter allows all signals
  - Low confidence bypasses filter

#### Configuration (`keryxflow/config.py`)
- **`MTFSettings`** - Multi-timeframe configuration
  - `enabled` - Enable/disable MTF analysis (default: false)
  - `timeframes` - List of timeframes to analyze (default: ["15m", "1h", "4h"])
  - `primary_timeframe` - Timeframe for entry signals (default: "1h")
  - `filter_timeframe` - Timeframe for trend filtering (default: "4h")
  - `min_filter_confidence` - Minimum confidence to apply filter (default: 0.5)

#### TradingSignal Extensions (`keryxflow/oracle/signals.py`)
- New MTF fields added to `TradingSignal` dataclass:
  - `primary_timeframe` - Primary TF used for signal
  - `filter_timeframe` - Filter TF used for trend
  - `filter_trend` - Trend direction from filter TF
  - `timeframe_alignment` - Whether timeframes agree
  - `mtf_data` - Full MTF analysis dict

#### TradingEngine Integration (`keryxflow/core/engine.py`)
- Conditional MTF mode based on settings
- `MultiTimeframeBuffer` used when MTF enabled
- `MTFSignalGenerator` used when MTF enabled
- OHLCV preloading for all configured timeframes
- Analysis uses dict of DataFrames in MTF mode

#### Backtester MTF Support (`keryxflow/backtester/`)
- **`DataLoader.load_multi_timeframe()`** - Load multiple timeframes
  - Fetches base timeframe and resamples to targets
  - Efficient single fetch with resampling
  - CSV loading with multi-timeframe resampling

- **`BacktestEngine`** - Extended for MTF
  - `mtf_enabled` parameter
  - `primary_timeframe` parameter
  - Accepts dict of DataFrames per symbol
  - Uses `MTFSignalGenerator` when enabled

- **CLI Arguments** - New backtest options
  - `--mtf` - Enable multi-timeframe analysis
  - `--timeframes` - Specify timeframes (e.g., 15m 1h 4h)
  - `--filter-tf` - Specify filter timeframe

#### Tests
- `tests/test_core/test_mtf_buffer.py` - 25+ tests for MTF buffer
  - TimeframeConfig, TimeframeBuffer, MultiTimeframeBuffer
  - Price updates, candle completion, resampling
  - Multiple symbols, max candles, clear operations

- `tests/test_oracle/test_mtf_analyzer.py` - 20+ tests for MTF analyzer
  - Analysis with single and multiple timeframes
  - Filter trend detection (bullish/bearish/neutral)
  - Alignment checking
  - apply_trend_filter() edge cases

- `tests/test_oracle/test_mtf_signals.py` - 18+ tests for MTF signals
  - Single TF fallback
  - MTF dict handling
  - MTF fields in signal
  - Filter behavior

### Changed
- `TradingEngine` now supports MTF mode via settings
- `BacktestEngine` accepts MTF data structure
- `DataLoader.resample()` uses proper pandas resample strings

### Technical Details
- Hierarchical filter approach: higher TF defines direction, lower TF for timing
- Alignment detection: all non-neutral trends must agree
- Confidence adjustment: +20% for alignment, -20% for divergence
- Filter bypass: low confidence filter allows any signal

### Example Configuration

```toml
# settings.toml
[oracle.mtf]
enabled = true
timeframes = ["15m", "1h", "4h"]
primary_timeframe = "1h"
filter_timeframe = "4h"
min_filter_confidence = 0.5
```

### Example Usage

```bash
# Run backtest with MTF
poetry run keryxflow-backtest --symbol BTC/USDT --start 2024-01-01 --end 2024-06-30 \
    --mtf --timeframes 15m 1h 4h --filter-tf 4h

# Run application with MTF (enable in settings.toml)
poetry run keryxflow
```

---

## [0.9.0] - 2026-02-02

### Added

#### Optimizer Module - Parameter Optimization (`keryxflow/optimizer/`)
- **`ParameterGrid`** - Grid generation for parameter combinations
  - `ParameterRange` dataclass for defining parameter values
  - Category support: 'oracle' (technical) and 'risk' parameters
  - Preset grids: `quick` (27), `oracle` (81), `risk` (27), `full` (2187 combinations)
  - Iterator-based combination generation
  - Flat and categorized output formats

- **`OptimizationEngine`** - Backtest execution across parameter grid
  - Runs BacktestEngine for each parameter combination
  - Progress callback for real-time updates
  - Automatic settings save/restore
  - Configurable optimization metric
  - Results sorted by target metric

- **`ResultComparator`** - Analysis and comparison tools
  - Rank results by any metric (Sharpe, return, win rate, etc.)
  - Top N / Bottom N extraction
  - Filter by criteria (min trades, max drawdown, etc.)
  - Parameter sensitivity analysis
  - Metrics summary statistics
  - Consistency scoring

- **`OptimizationReport`** - Report generation
  - Formatted terminal summary with sensitivity analysis
  - Compact tabular output
  - CSV export of all results
  - Best parameters extraction and export

- **CLI Runner** - Command-line interface
  - `poetry run keryxflow-optimize`
  - Grid presets: --grid quick|oracle|risk|full
  - Custom parameters: --param name:val1,val2,val3:category
  - Metric selection: --metric sharpe_ratio|total_return|profit_factor|win_rate
  - Output directory for CSV exports

#### Optimizable Parameters
| Category | Parameters |
|----------|------------|
| Oracle | rsi_period, macd_fast, macd_slow, bbands_std |
| Risk | risk_per_trade, min_risk_reward, atr_multiplier |

#### Tests
- `tests/test_optimizer/test_grid.py` - 16 tests for ParameterGrid
- `tests/test_optimizer/test_engine.py` - 6 tests for OptimizationEngine
- `tests/test_optimizer/test_comparator.py` - 11 tests for ResultComparator
- `tests/test_optimizer/test_report.py` - 13 tests for OptimizationReport
- Total: 397 tests passing (46 new + 351 existing)

### Changed
- `pyproject.toml` - Added `keryxflow-optimize` script entry

### Technical Details
- Grid search approach (exhaustive parameter testing)
- Reuses existing BacktestEngine for each run
- Settings temporarily modified then restored after optimization
- Sequential execution (parallelization planned for future)

---

## [0.8.0] - 2026-02-01

### Added

#### Live Trading Mode (`keryxflow/core/`)
- **`LiveTradingSafeguards`** - Safety verification before enabling live mode
  - API credentials check
  - Minimum balance verification (100 USDT)
  - Paper trading history requirement (30+ trades)
  - Risk settings validation
  - Circuit breaker status check
  - Environment verification (production mode)

- **TradingEngine Live Integration**
  - Live mode detection via settings
  - Balance sync from exchange (configurable interval)
  - Live order execution via Binance API
  - Error notifications for live trading failures
  - Mode indicator in status

- **`TradeRepository`** - Trade persistence layer
  - Create/close trades with paper/live flag
  - Query trades by date, symbol, status
  - Daily stats tracking
  - Paper trade counting for safeguards

#### Notifications Module (`keryxflow/notifications/`)
- **`TelegramNotifier`** - Telegram Bot API integration
  - Markdown-formatted messages
  - Bot token + chat ID configuration
  - Connection testing

- **`DiscordNotifier`** - Discord Webhook integration
  - Rich embeds with color coding
  - Custom bot username
  - Webhook URL validation

- **`NotificationManager`** - Coordinates multiple notifiers
  - `notify_order_filled()` - Trade execution alerts
  - `notify_circuit_breaker()` - Emergency stop alerts
  - `notify_daily_summary()` - End of day reports
  - `notify_system_start/error()` - System events
  - Automatic event bus subscription

#### Configuration
- **`[live]`** section in settings.toml
  - `require_confirmation` - Require explicit live mode confirmation
  - `min_paper_trades` - Minimum paper trades before live
  - `min_balance` - Minimum USDT balance
  - `max_position_value` - Position size limit
  - `sync_interval` - Balance sync frequency

- **`[notifications]`** section in settings.toml
  - Telegram: enabled, token, chat_id
  - Discord: enabled, webhook
  - Preferences: notify_on_trade, circuit_breaker, daily_summary, errors

#### Tests
- `tests/test_core/test_safeguards.py` - 31 tests for live safeguards
- `tests/test_core/test_repository.py` - 14 tests for trade persistence
- `tests/test_core/test_engine.py` - 9 new tests for live mode
- `tests/test_notifications/` - 37 tests for notification system
- Total: 351 tests passing (23 new + 328 existing)

### Changed
- `TradingEngine` now supports notification manager injection
- `OrderManager` has `sync_balance_from_exchange()` and `get_open_orders()` methods
- `.env.example` includes notification configuration

### Technical Details
- Live orders use market orders for simplicity
- Safeguards block live mode if any error-level check fails
- Notifications are optional (disabled by default)
- Repository uses async context manager for session handling

---

## [0.7.0] - 2026-02-01

### Added

#### Backtesting Module (`keryxflow/backtester/`)
- **`DataLoader`** - Historical data loading
  - Load OHLCV from Binance API via CCXT
  - Load from CSV files for offline testing
  - Data validation (required columns, null checks, numeric types)
  - Resample to different timeframes

- **`BacktestEngine`** - Strategy simulation engine
  - Replay historical data candle by candle
  - Reuses SignalGenerator for signal generation
  - Reuses RiskManager for order approval
  - Simulates slippage and commission (configurable)
  - Stop loss and take profit execution
  - Tracks positions, trades, and equity curve

- **`BacktestResult`** - Performance metrics
  - Total return and net P&L
  - Win rate, avg win, avg loss
  - Expectancy per trade
  - Profit factor (gross profit / gross loss)
  - Max drawdown and duration
  - Sharpe ratio

- **`BacktestReporter`** - Report generation
  - Formatted terminal output
  - ASCII equity curve chart
  - Trade list formatting
  - CSV export (trades and equity curve)

- **CLI Runner** - Command-line interface
  - `poetry run keryxflow-backtest`
  - Arguments: --symbol, --start, --end, --timeframe, --balance, --profile
  - Optional: --chart (ASCII equity), --trades N (show last N trades)
  - Optional: --output (save CSV reports)

#### Tests
- `tests/test_backtester/test_data.py` - 10 tests for DataLoader
  - CSV loading and validation
  - Missing columns detection
  - Resampling functionality

- `tests/test_backtester/test_engine.py` - 23 tests for BacktestEngine
  - Trade and position dataclasses
  - Stop loss and take profit execution
  - Equity calculation
  - Full backtest run

### Technical Details
- Reuses existing components (SignalGenerator, RiskManager, QuantEngine)
- LLM/news disabled by default for speed
- Slippage: 0.1% default, Commission: 0.1% default
- 260 tests passing (33 new + 227 existing)

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
| 0.11.0 | 2026-02-02 | Guardrails layer - immutable safety limits (fixes Issue #9) |
| 0.10.0 | 2026-02-02 | Multi-timeframe analysis |
| 0.9.0 | 2026-02-02 | Parameter optimization (grid search) |
| 0.8.0 | 2026-02-01 | Live trading mode with safeguards and notifications |
| 0.7.0 | 2026-02-01 | Backtesting engine for strategy validation |
| 0.6.0 | 2026-02-01 | Integration loop (TradingEngine orchestrator) |
| 0.5.0 | 2026-02-01 | Hermes TUI (Textual interface) |
| 0.4.0 | 2026-02-01 | Oracle intelligence layer (technical + LLM) |
| 0.3.0 | 2026-02-01 | Aegis risk management layer |
| 0.2.0 | 2026-02-01 | Exchange layer + runnable MVP |
| 0.1.0 | 2026-02-01 | Project foundation - Phase 0 complete |

---

## Upcoming

### [0.12.0] - Planned: Memory System
- Trade episode memory with reasoning and lessons learned
- Trading rules learned from experience
- Market pattern recognition
- Memory context in LLM prompts

### [0.13.0] - Planned: Agent Tools
- Tool framework for Claude (perception, analysis, execution)
- Guarded execution tools (orders pass through guardrails)
- Anthropic Tool Use API integration

### [0.14.0] - Planned: Cognitive Agent
- Claude as primary decision maker (not just validator)
- Cognitive cycle: Perceive → Remember → Analyze → Decide → Execute → Learn
- Agent mode toggle (backwards compatible)
- Fallback to technical signals on API failure

### [0.15.0] - Planned: Learning & Reflection
- Daily/weekly reflection on trading performance
- Automatic rule generation from patterns
- Strategy adaptation based on market conditions

### [1.0.0] - Planned
- Production ready AI-First architecture
- Full documentation
- Performance optimizations

---

## RFC & Architecture

### RFC #11: AI-First Trading Architecture
**Status**: Phase 1 Complete | **Document**: `docs/ai-trading-architecture.md`

Proposes evolution from "AI validates" to "AI operates":
- Current: Technical indicators (60%) + Claude validates (40%)
- Future: Claude decides autonomously within immutable guardrails

**Implementation Plan**: `docs/plans/ai-first-implementation-plan.md`

**Phases**:
1. ✅ Guardrails Layer - **COMPLETE** (v0.11.0) - Issue #9 fixed
2. Memory System (2-3 weeks) - 3-layer memory (Episodic, Semantic, Procedural)
3. Agent Tools (2-3 weeks) - Tools for Claude to query data and execute
4. Cognitive Agent (3-4 weeks) - Claude as primary decision maker
5. Learning & Reflection (2-3 weeks) - Continuous improvement

**Related Issues**: #9 (Position sizing - FIXED), #11 (RFC)
