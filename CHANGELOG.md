# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

---

## [0.16.0] - 2026-02-03

### Added

#### Trading Session Integration (`keryxflow/agent/`)

- **`session.py`** - Trading session management
  - `TradingSession` - Manages autonomous trading sessions
  - `SessionState` - State machine (IDLE, STARTING, RUNNING, PAUSED, STOPPING, STOPPED, ERROR)
  - `SessionStats` - Session statistics (cycles, trades, PnL, tokens, errors)
  - `get_trading_session()` - Singleton accessor
  - Background agent loop with configurable cycle interval
  - Event publishing for session state changes

#### Hermes TUI (`keryxflow/hermes/widgets/`)

- **`agent.py`** - Agent status widget for TUI
  - `AgentWidget` - Displays Cognitive Agent and session status
  - Session state display with color coding
  - Cycles completed with success rate progress bar
  - Trade statistics (count, win rate, PnL)
  - Tool calls and tokens tracking

#### New Event Types (`keryxflow/core/events.py`)

- `AGENT_CYCLE_STARTED` - Agent cycle began
- `AGENT_CYCLE_COMPLETED` - Agent cycle finished
- `AGENT_CYCLE_FAILED` - Agent cycle failed
- `SESSION_STATE_CHANGED` - Session state transition

#### Tests

- `test_session.py` - 26 tests for TradingSession
- `test_widgets.py` - 8 new tests for AgentWidget
- Total: 34 new tests (307 total tests)

### Changed

- Updated `keryxflow/agent/__init__.py` - Exports for session module
- Updated `keryxflow/hermes/widgets/__init__.py` - Exports for AgentWidget
- Updated `tests/conftest.py` - Singleton reset for session module
- Updated `CLAUDE.md` - Documentation for Phase 6

### Technical Details

- **Session Management** - Start, pause, resume, stop trading sessions
- **Background Loop** - Agent runs cycles in background task
- **Graceful Shutdown** - Proper cleanup on session stop
- **TUI Integration** - Real-time status display in Hermes

---

## [0.15.0] - 2026-02-03

### Added

#### Learning & Reflection System (`keryxflow/agent/`)

- **`reflection.py`** - Reflection engine for learning from trades
  - `ReflectionEngine` - Orchestrates all reflection types
  - `PostMortemResult` - Analysis of individual closed trades
  - `DailyReflectionResult` - End-of-day trading review
  - `WeeklyReflectionResult` - Pattern identification and rule updates
  - Integration with Claude for intelligent analysis
  - Fallback to basic analysis when API unavailable

- **`strategy.py`** - Strategy selection and adaptation
  - `StrategyManager` - Manages trading strategy catalog
  - `StrategyConfig` - Strategy configuration with parameters
  - `StrategySelection` - Result of strategy selection
  - `MarketRegime` - Classification (trending, ranging, volatile, etc.)
  - 4 default strategies: trend following, mean reversion, breakout, momentum
  - Automatic regime detection from price data
  - Performance tracking and parameter adaptation

- **`scheduler.py`** - Task scheduler for periodic operations
  - `TaskScheduler` - Manages scheduled tasks
  - `ScheduledTask` - Task definition with frequency and callback
  - `TaskResult` - Execution result tracking
  - Support for ONCE, HOURLY, DAILY, WEEKLY, MONTHLY frequencies
  - Default tasks: daily reflection (23:00 UTC), weekly reflection (Sunday 23:30 UTC)

#### Tests (`tests/test_agent/`)

- `test_reflection.py` - 21 tests for reflection engine
- `test_strategy.py` - 24 tests for strategy manager
- `test_scheduler.py` - 22 tests for task scheduler
- Total: 67 new tests (203 agent module tests total)

### Changed

- Updated `keryxflow/agent/__init__.py` - Exports for new modules
- Updated `tests/conftest.py` - Singleton resets for new modules
- Updated `CLAUDE.md` - Documentation for Phase 5

### Technical Details

- **Autonomous Learning** - Agent learns from past trades through reflections
- **Strategy Adaptation** - Strategies selected based on market regime
- **Scheduled Tasks** - Automated daily and weekly reflections
- **Claude Integration** - Uses Claude API for intelligent analysis with fallback

---

## [0.14.0] - 2026-02-03

### Added

#### Cognitive Agent - AI-First Autonomous Trading (`keryxflow/agent/cognitive.py`)

- **`CognitiveAgent`** - Autonomous trading agent using Claude's Tool Use API
  - Cognitive cycle: `Perceive → Remember → Analyze → Decide → Validate → Execute → Learn`
  - Integration with TradingToolkit for tool execution
  - Integration with Memory System for contextual decisions
  - Fallback to technical signals when Claude API fails
  - Rate limiting and error handling

- **`CycleResult`** - Result of a single agent cycle
  - Status tracking (SUCCESS, NO_ACTION, FALLBACK, ERROR, RATE_LIMITED)
  - Decision with type, symbol, reasoning, and confidence
  - Tool execution results and token usage tracking

- **`AgentDecision`** - Trading decision structure
  - Decision types: HOLD, ENTRY_LONG, ENTRY_SHORT, EXIT, ADJUST_STOP, ADJUST_TARGET
  - Symbol, reasoning, confidence, and metadata

- **`AgentStats`** - Statistics for agent performance
  - Cycle counts (total, successful, fallback, error)
  - Tool call tracking and token usage
  - Decisions by type

#### Configuration (`keryxflow/config.py`)

- **`AgentSettings`** - Agent configuration
  - `enabled` - Enable/disable agent mode (default: false)
  - `model` - Claude model to use (default: claude-sonnet-4-20250514)
  - `cycle_interval` - Seconds between cycles (default: 60)
  - `max_tool_calls_per_cycle` - Max tool calls per cycle (default: 20)
  - `fallback_to_technical` - Fall back to technical signals on failure (default: true)
  - `max_consecutive_errors` - Errors before fallback (default: 3)

#### TradingEngine Integration (`keryxflow/core/engine.py`)

- **`agent_mode`** - Flag to enable agent-driven signal generation
- When `agent_mode=True`, CognitiveAgent replaces SignalGenerator
- When `agent_mode=False`, traditional technical signals (backwards compatible)
- Agent cycle runs at configured interval alongside price updates

#### Tests (`tests/test_agent/test_cognitive.py`)

- 27 new tests for CognitiveAgent
- Tests for CycleStatus, DecisionType, AgentDecision, CycleResult, AgentStats
- Tests for initialization, cycle execution, fallback behavior
- Tests for context building, decision parsing, statistics

### Changed

- Updated `tests/conftest.py` - Added `cognitive._agent` singleton reset
- Updated `CLAUDE.md` - Added Cognitive Agent documentation
- Total tests: 136 agent module tests

### Technical Details

- **AI-First Architecture** - Claude decides, guardrails validate
- **Backwards Compatible** - `agent_mode=False` preserves existing behavior
- **Graceful Degradation** - Falls back to technical signals on API failure
- **Full Tool Use** - Uses all 20 tools through Anthropic Tool Use API

---

## [0.13.0] - 2026-02-02

### Added

#### Agent Tools - AI Tool Framework (`keryxflow/agent/`)

- **`tools.py`** - Agent tool framework
  - `BaseTool` - Abstract base class for all agent tools
  - `ToolParameter` - Parameter definition with type, description, validation
  - `ToolResult` - Standardized result with success status and data
  - `ToolCategory` - Categories: PERCEPTION, ANALYSIS, INTROSPECTION, EXECUTION
  - `TradingToolkit` - Registry and manager for all tools
  - `create_tool` - Decorator for creating tools from functions
  - Anthropic Tool Use API compatible schema generation

- **`perception_tools.py`** - Market data tools (7 tools)
  - `get_current_price` - Get current price for a trading pair
  - `get_ohlcv` - Get OHLCV candlestick data
  - `get_order_book` - Get order book depth
  - `get_portfolio_state` - Get portfolio with positions and risk metrics
  - `get_balance` - Get account balances
  - `get_positions` - Get all open positions
  - `get_open_orders` - Get pending orders

- **`analysis_tools.py`** - Analysis and memory tools (7 tools)
  - `calculate_indicators` - Run technical analysis (RSI, MACD, etc.)
  - `calculate_position_size` - Calculate safe position size
  - `calculate_risk_reward` - Calculate R:R ratio for trade
  - `calculate_stop_loss` - Calculate stop loss (fixed % or ATR)
  - `get_trading_rules` - Get active rules from semantic memory
  - `recall_similar_trades` - Recall similar trades from episodic memory
  - `get_market_patterns` - Get matching patterns from memory

- **`execution_tools.py`** - Order execution tools (6 tools, **GUARDED**)
  - `place_order` - Place market or limit order (validates guardrails)
  - `close_position` - Close an open position
  - `set_stop_loss` - Update stop loss for position
  - `set_take_profit` - Update take profit for position
  - `cancel_order` - Cancel a pending order
  - `close_all_positions` - Emergency close all (requires confirmation)

- **`executor.py`** - Safe tool executor
  - `ToolExecutor` - Wraps tool execution with guardrail validation
  - Pre-execution guardrail checks for execution tools
  - Rate limiting (max executions per minute)
  - Execution statistics and history tracking
  - Event publishing for tool lifecycle

#### Tests (`tests/test_agent/`)

- `test_tools.py` - Tool framework tests (25 tests)
- `test_perception.py` - Perception tools tests (20 tests)
- `test_analysis.py` - Analysis tools tests (24 tests)
- `test_execution.py` - Execution tools tests (24 tests)
- `test_executor.py` - Executor tests (16 tests)
- Total: 109 new tests

### Changed

- Updated `tests/conftest.py` - Added singleton resets for agent module
- Updated `CLAUDE.md` - Added agent tools documentation

### Technical Details

- **20 tools total** - All compatible with Anthropic Tool Use API
- **Guarded execution** - Execution tools validate against guardrails before running
- **Type-safe parameters** - Full validation with JSON Schema compatible definitions
- **Async throughout** - All tools are async/await compatible
- **Memory integration** - Introspection tools access episodic/semantic memory

---

## [0.12.0] - 2026-02-02

### Added

#### Memory System - Trade Episodes, Rules, and Patterns (`keryxflow/memory/`)

- **`episodic.py`** - Episodic memory for trade episodes
  - `EpisodicMemory` - Records and recalls trade episodes
  - `EpisodeContext` - Entry context for new trade episodes
  - `SimilarityMatch` - Similar past trade with relevance score
  - `record_entry()` - Record trade entry with full context
  - `record_exit()` - Record trade exit with outcome
  - `record_lessons()` - Record lessons learned
  - `recall_similar()` - Find similar past trades by technical/sentiment context
  - RSI zone classification for similarity matching

- **`semantic.py`** - Semantic memory for rules and patterns
  - `SemanticMemory` - Manages trading rules and market patterns
  - `TradingRule` - Rules learned from experience or user-defined
  - `MarketPattern` - Identified market patterns with statistics
  - `RuleMatch` / `PatternMatch` - Matching results with relevance
  - `create_rule()` / `create_pattern()` - Create new rules/patterns
  - `get_active_rules()` - Get rules for current context
  - `update_rule_performance()` - Track rule success rate
  - `find_matching_patterns()` - Detect patterns in current context

- **`manager.py`** - Unified memory interface
  - `MemoryManager` - Coordinates episodic and semantic memory
  - `MemoryContext` - Complete memory context for decisions
  - `build_context_for_decision()` - Build context with similar trades, rules, patterns
  - `record_trade_entry()` / `record_trade_exit()` - Full trade lifecycle
  - `to_prompt_context()` - Format memory for LLM prompts
  - Confidence adjustment based on past performance

#### New Data Models (`keryxflow/core/models.py`)

- **`TradeEpisode`** - Complete trade with reasoning and lessons learned
  - Entry/exit context with timestamps
  - Technical and market context (JSON)
  - Outcome classification (WIN, LOSS, STOPPED_OUT, etc.)
  - Lessons learned and reflection fields

- **`TradingRule`** - Trading rules with performance tracking
  - Source (learned, user, backtest, system)
  - Status (active, inactive, testing, deprecated)
  - Success rate and application count
  - Applicability filters (symbols, timeframes, conditions)

- **`MarketPattern`** - Market patterns with statistics
  - Pattern type (price_action, indicator, volume, sentiment)
  - Win rate and average return
  - Validation status based on occurrences

#### Engine Integration (`keryxflow/core/engine.py`)

- `TradingEngine` now includes `MemoryManager`
- Trade episodes recorded automatically on order execution
- Memory context built for each trading decision
- `record_trade_exit()` method for position close tracking

#### Oracle Integration (`keryxflow/oracle/brain.py`)

- `analyze()` now accepts `memory_context` parameter
- Memory context included in LLM prompts
- Similar past trades and rules inform analysis

#### Tests (`tests/test_memory/`)

- `test_episodic.py` - 22 tests for episodic memory
- `test_semantic.py` - 27 tests for semantic memory
- `test_manager.py` - 21 tests for memory manager
- **Total: 70 new tests** (638 total passing)

### Technical Details

- Memory stored in SQLite via SQLModel (same as other models)
- Similarity calculation based on RSI zone, trend, MACD signal
- Pattern matching uses detection criteria with range/equals checks
- Confidence adjustment: +/-30% max based on memory context
- Rules track success rate and average PnL when applied

### Example Usage

```python
from keryxflow.memory import get_memory_manager

memory = get_memory_manager()

# Build context for decision
context = await memory.build_context_for_decision(
    symbol="BTC/USDT",
    technical_context={"rsi": 28, "trend": "bullish"},
    market_sentiment="bullish",
)

# Record trade entry
episode_id = await memory.record_trade_entry(
    trade_id=1,
    symbol="BTC/USDT",
    entry_price=50000.0,
    entry_reasoning="RSI oversold with bullish divergence",
    entry_confidence=0.8,
    memory_context=context,
)

# Record trade exit
await memory.record_trade_exit(
    episode_id=episode_id,
    exit_price=52000.0,
    exit_reasoning="Take profit reached",
    outcome=TradeOutcome.WIN,
    pnl=200.0,
    pnl_percentage=4.0,
)
```

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
| 0.15.0 | 2026-02-03 | Learning & Reflection - strategy, scheduler, reflection engine |
| 0.14.0 | 2026-02-03 | Cognitive Agent - AI-first autonomous trading |
| 0.13.0 | 2026-02-02 | Agent Tools - tool framework for Claude |
| 0.12.0 | 2026-02-02 | Memory System - trade episodes, rules, patterns |
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

### [0.16.0] - Planned: Trading Session Integration
- Full integration of Cognitive Agent with TradingEngine
- Session management (start, pause, resume, stop)
- Agent-driven trading loop with all components connected
- Performance monitoring and statistics

### [1.0.0] - Planned
- Production ready AI-First architecture
- Full documentation
- Performance optimizations

---

## RFC & Architecture

### RFC #11: AI-First Trading Architecture
**Status**: Phase 5 Complete | **Document**: `docs/ai-trading-architecture.md`

Proposes evolution from "AI validates" to "AI operates":
- Previous: Technical indicators (60%) + Claude validates (40%)
- Current: Claude decides autonomously within immutable guardrails

**Implementation Plan**: `docs/plans/ai-first-implementation-plan.md`

**Phases**:
1. ✅ Guardrails Layer - **COMPLETE** (v0.11.0) - Issue #9 fixed
2. ✅ Memory System - **COMPLETE** (v0.12.0) - Episodic, Semantic memory
3. ✅ Agent Tools - **COMPLETE** (v0.13.0) - 20 tools for Claude
4. ✅ Cognitive Agent - **COMPLETE** (v0.14.0) - Claude as decision maker
5. ✅ Learning & Reflection - **COMPLETE** (v0.15.0) - Continuous improvement
6. Trading Session Integration (Next) - Full agent-driven trading

**Related Issues**: #9 (Position sizing - FIXED), #11 (RFC)
