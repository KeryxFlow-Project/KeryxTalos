# Strategy Development Guide

A comprehensive guide to building, testing, and deploying trading strategies with KeryxFlow.

## Table of Contents

- [Strategy Architecture Overview](#strategy-architecture-overview)
- [Step-by-Step Strategy Tutorial](#step-by-step-strategy-tutorial)
- [Example 1: SMA Crossover (Beginner)](#example-1-sma-crossover-beginner)
- [Example 2: RSI + Bollinger Bands (Intermediate)](#example-2-rsi--bollinger-bands-intermediate)
- [Example 3: Multi-Timeframe Momentum (Advanced)](#example-3-multi-timeframe-momentum-advanced)
- [Backtesting Guide](#backtesting-guide)
- [Optimizer Guide](#optimizer-guide)
- [StrategyManager Registration & AI Regime Selection](#strategymanager-registration--ai-regime-selection)
- [Best Practices](#best-practices)

---

## Strategy Architecture Overview

### How Strategies Flow Through the System

KeryxFlow strategies operate within a layered architecture. A strategy defines **what** indicators to watch and **when** to trade. The system handles execution, risk management, and learning automatically.

```
Strategy Selection → Signal Generation → Risk Approval → Order Execution → Memory Recording
     (StrategyManager)    (SignalGenerator)     (Aegis/RiskManager)  (PaperEngine)      (MemoryManager)
```

All modules communicate via the async event bus:

```python
await event_bus.publish(Event(type=EventType.SIGNAL_GENERATED, data=signal.to_dict()))
```

Key event types in the signal flow:
- `PRICE_UPDATE` — New candle data arrives
- `SIGNAL_GENERATED` — Oracle produces a trading signal
- `ORDER_APPROVED` / `ORDER_REJECTED` — Aegis risk verdict
- `ORDER_FILLED` — Exchange confirms execution
- `POSITION_OPENED` / `POSITION_CLOSED` — Lifecycle events

### Core Strategy Components

**`StrategyConfig`** (`keryxflow/agent/strategy.py`) — Defines a strategy:

```python
@dataclass
class StrategyConfig:
    id: str                                          # Unique identifier
    name: str                                        # Human-readable name
    strategy_type: StrategyType                      # TREND_FOLLOWING, MEAN_REVERSION, etc.
    description: str                                 # What the strategy does
    regime_suitability: dict[MarketRegime, float]    # Score 0-1 per regime
    parameters: dict[str, Any]                       # Configurable params
```

**`StrategyType`** — Classification of strategy approach:

| Type | Description |
|------|-------------|
| `TREND_FOLLOWING` | Follow established price trends |
| `MEAN_REVERSION` | Trade reversals at extremes |
| `BREAKOUT` | Trade price breakouts from ranges |
| `MOMENTUM` | Trade momentum shifts (MACD, etc.) |
| `SCALPING` | Short-term rapid trades |
| `SWING` | Multi-day position trades |

**`MarketRegime`** — Classification of current market conditions:

| Regime | Detection Criteria |
|--------|-------------------|
| `TRENDING_UP` | Price change > +5% over window |
| `TRENDING_DOWN` | Price change < -5% over window |
| `RANGING` | SMA(10) and SMA(30) converging (< 1% difference) |
| `HIGH_VOLATILITY` | Price range > 10% of starting price |
| `LOW_VOLATILITY` | Price range < 3% of starting price |
| `BREAKOUT` | Recent 5-bar volatility > 2x older 15-bar volatility |
| `UNKNOWN` | Insufficient data or no clear regime |

### Built-in Strategies

KeryxFlow ships with four default strategies registered in `StrategyManager.DEFAULT_STRATEGIES`:

| ID | Type | Best Regimes | Key Parameters |
|----|------|-------------|----------------|
| `trend_following_basic` | TREND_FOLLOWING | TRENDING_UP/DOWN (0.9) | fast_ema=9, slow_ema=21 |
| `mean_reversion_rsi` | MEAN_REVERSION | RANGING (0.9), LOW_VOL (0.8) | rsi_period=14, oversold=30, overbought=70 |
| `breakout_bollinger` | BREAKOUT | BREAKOUT (0.95), HIGH_VOL (0.7) | bb_period=20, bb_std=2.0 |
| `momentum_macd` | MOMENTUM | TRENDING_UP/DOWN (0.8), BREAKOUT (0.7) | fast=12, slow=26, signal=9 |

### Signal Generation Pipeline

The `SignalGenerator` (`keryxflow/oracle/signals.py`) produces trading signals:

1. **Technical Analysis** — `TechnicalAnalyzer.analyze(ohlcv)` computes RSI, MACD, Bollinger Bands, EMA, OBV, ATR
2. **News Analysis** (optional) — Fetches and scores recent crypto news
3. **LLM Analysis** (optional) — Claude validates/vetos the technical signal
4. **Signal Combination** — Weighted average (60% technical, 40% LLM) produces final confidence
5. **Target Calculation** — Stop loss at 1.5x ATR, take profit at 3x ATR (2:1 R:R)

The resulting `TradingSignal` contains:
- `signal_type`: LONG, SHORT, CLOSE_LONG, CLOSE_SHORT, or NO_ACTION
- `strength`: STRONG (>0.7), MODERATE (>0.5), WEAK (>0.3), or NONE
- `entry_price`, `stop_loss`, `take_profit`, `risk_reward`

---

## Step-by-Step Strategy Tutorial

### Step 1: Define Your Strategy

Create a `StrategyConfig` with an ID, type, and regime suitability scores:

```python
from keryxflow.agent.strategy import (
    MarketRegime,
    StrategyConfig,
    StrategyType,
)

my_strategy = StrategyConfig(
    id="my_custom_strategy",
    name="My Custom Strategy",
    strategy_type=StrategyType.TREND_FOLLOWING,
    description="Buy when fast EMA crosses above slow EMA in uptrends",
    regime_suitability={
        MarketRegime.TRENDING_UP: 0.9,
        MarketRegime.TRENDING_DOWN: 0.8,
        MarketRegime.RANGING: 0.2,
        MarketRegime.HIGH_VOLATILITY: 0.5,
        MarketRegime.LOW_VOLATILITY: 0.6,
        MarketRegime.BREAKOUT: 0.7,
    },
    parameters={
        "fast_ema": 9,
        "slow_ema": 21,
        "confirmation_candles": 2,
    },
)
```

**Regime suitability** scores (0.0 to 1.0) tell the `StrategyManager` when your strategy performs best. Higher scores mean the strategy is more likely to be selected in that regime.

### Step 2: Register With the StrategyManager

```python
from keryxflow.agent.strategy import get_strategy_manager

manager = get_strategy_manager()
manager.register_strategy(my_strategy)
```

The `get_strategy_manager()` singleton ensures all components share the same strategy catalog. Registration makes your strategy available for automatic selection.

### Step 3: Configure Oracle Parameters

Strategy parameters map to `OracleSettings` in `keryxflow/config.py`. Configure via environment variables or `settings.toml`:

```toml
# settings.toml
[oracle]
indicators = ["rsi", "macd", "bbands", "obv", "atr", "ema"]
rsi_period = 14
rsi_overbought = 70
rsi_oversold = 30
macd_fast = 12
macd_slow = 26
macd_signal = 9
bbands_period = 20
bbands_std = 2.0
ema_periods = [9, 21, 50, 200]
```

Or via environment variables:

```bash
KERYXFLOW_ORACLE_RSI_PERIOD=14
KERYXFLOW_ORACLE_MACD_FAST=12
KERYXFLOW_ORACLE_BBANDS_STD=2.0
```

### Step 4: Strategy Selection in Action

The `StrategyManager.select_strategy()` method:

1. Calls `detect_market_regime(prices)` using SMA(10)/SMA(30) convergence and volatility
2. Scores each active strategy: `base_score = regime_suitability[current_regime]`
3. Adjusts for performance: +0.1 if win_rate > 60%, -0.1 if < 40%, +0.05 if avg_pnl > 0
4. Returns a `StrategySelection` with the highest-scoring strategy

```python
selection = await manager.select_strategy(
    symbol="BTC/USDT",
    prices=recent_close_prices,  # list[float] of at least 20 prices
)

print(selection.strategy.name)       # "Basic Trend Following"
print(selection.detected_regime)     # MarketRegime.TRENDING_UP
print(selection.confidence)          # 0.9
print(selection.alternative_strategies)  # ["momentum_macd", "breakout_bollinger"]
```

### Step 5: Backtest and Optimize

Once defined, test your strategy with the backtester and optimizer (detailed in sections below).

---

## Example 1: SMA Crossover (Beginner)

A simple trend-following strategy using EMA crossovers — the same approach as the built-in `trend_following_basic`.

### Concept

- **Buy** when the fast EMA (9) crosses above the slow EMA (21)
- **Sell** when the fast EMA crosses below the slow EMA
- Best in trending markets, poor in ranging/choppy conditions

### Strategy Definition

```python
from keryxflow.agent.strategy import (
    MarketRegime,
    StrategyConfig,
    StrategyType,
    get_strategy_manager,
)

sma_crossover = StrategyConfig(
    id="sma_crossover_beginner",
    name="SMA Crossover (Beginner)",
    strategy_type=StrategyType.TREND_FOLLOWING,
    description="Trade EMA 9/21 crossovers with ATR-based stops",
    regime_suitability={
        MarketRegime.TRENDING_UP: 0.9,
        MarketRegime.TRENDING_DOWN: 0.9,
        MarketRegime.RANGING: 0.2,       # Avoid ranging markets
        MarketRegime.HIGH_VOLATILITY: 0.5,
        MarketRegime.LOW_VOLATILITY: 0.6,
        MarketRegime.BREAKOUT: 0.7,
    },
    parameters={
        "fast_ema": 9,
        "slow_ema": 21,
        "confirmation_candles": 2,       # Wait 2 candles after cross
    },
)

manager = get_strategy_manager()
manager.register_strategy(sma_crossover)
```

### How It Works in the Signal Pipeline

The `TechnicalAnalyzer._calculate_ema()` method computes EMAs for configured periods (default: 9, 21, 50, 200). It then checks:

1. **EMA Alignment** — Are shorter EMAs above longer EMAs (bullish) or below (bearish)?
2. **Price Position** — Is price above or below each EMA?
3. **Signal Strength** — Perfect alignment = STRONG, partial = MODERATE, mixed = WEAK

The `SignalGenerator` converts this to a `TradingSignal` with:
- **Stop loss**: Entry price × (1 - ATR% × 1.5)
- **Take profit**: Entry price × (1 + ATR% × 3) — giving a 2:1 risk/reward ratio

### Configuration

```toml
# settings.toml - tune for this strategy
[oracle]
ema_periods = [9, 21]  # Only the periods we need
indicators = ["ema", "atr"]  # Minimal indicator set
```

### Backtesting

```bash
poetry run keryxflow-backtest --symbol BTC/USDT --start 2024-01-01 --end 2024-06-30
```

### When to Use

- Strong trending markets (crypto bull/bear runs)
- Higher timeframes (1h, 4h, 1d) to filter noise
- Avoid during low-volume sideways periods

---

## Example 2: RSI + Bollinger Bands (Intermediate)

A mean-reversion strategy combining RSI oversold/overbought levels with Bollinger Band extremes for confirmation.

### Concept

- **Buy** when RSI < 30 (oversold) AND price is near the lower Bollinger Band
- **Sell** when RSI > 70 (overbought) AND price is near the upper Bollinger Band
- Best in ranging or low-volatility markets

### Strategy Definition

```python
from keryxflow.agent.strategy import (
    MarketRegime,
    StrategyConfig,
    StrategyType,
    get_strategy_manager,
)

rsi_bbands = StrategyConfig(
    id="rsi_bbands_reversion",
    name="RSI + Bollinger Mean Reversion",
    strategy_type=StrategyType.MEAN_REVERSION,
    description="Trade reversals when RSI extremes align with Bollinger Band touches",
    regime_suitability={
        MarketRegime.TRENDING_UP: 0.3,     # Mean reversion fails in trends
        MarketRegime.TRENDING_DOWN: 0.3,
        MarketRegime.RANGING: 0.9,          # Ideal for ranging markets
        MarketRegime.HIGH_VOLATILITY: 0.4,  # Too volatile for reversion
        MarketRegime.LOW_VOLATILITY: 0.8,   # Works well in calm markets
        MarketRegime.BREAKOUT: 0.2,         # Breakouts kill mean reversion
    },
    parameters={
        "rsi_period": 14,
        "rsi_oversold": 30,
        "rsi_overbought": 70,
        "bbands_period": 20,
        "bbands_std": 2.0,
    },
)

manager = get_strategy_manager()
manager.register_strategy(rsi_bbands)
```

### How It Works in the Signal Pipeline

The `TechnicalAnalyzer` computes both indicators independently:

**RSI** (`_calculate_rsi`):
- RSI < 30 → BULLISH signal (STRONG if < 20)
- RSI > 70 → BEARISH signal (STRONG if > 80)

**Bollinger Bands** (`_calculate_bbands`):
- Price position = (price - lower) / (upper - lower)
- Position < 0.05 → BULLISH STRONG (near lower band)
- Position > 0.95 → BEARISH STRONG (near upper band)

The `_aggregate_signals` method weight-averages all indicator signals. When both RSI and BBands agree (e.g., both BULLISH STRONG), the combined confidence is high, producing a STRONG buy signal.

### Configuration

```toml
# settings.toml
[oracle]
indicators = ["rsi", "bbands", "atr"]
rsi_period = 14
rsi_overbought = 70
rsi_oversold = 30
bbands_period = 20
bbands_std = 2.0
```

### Optimization Parameters

This strategy benefits from tuning RSI and Bollinger Band thresholds:

```python
from keryxflow.optimizer.grid import ParameterGrid, ParameterRange

grid = ParameterGrid([
    ParameterRange("rsi_period", [7, 14, 21], "oracle"),
    ParameterRange("rsi_oversold", [25, 30, 35], "oracle"),
    ParameterRange("bbands_std", [1.5, 2.0, 2.5], "oracle"),
])
# 27 combinations
```

### When to Use

- Sideways/ranging markets (consolidation phases)
- Lower volatility periods
- Avoid during strong trends or breakout events

---

## Example 3: Multi-Timeframe Momentum (Advanced)

An advanced strategy using MACD momentum across multiple timeframes. The higher timeframe confirms the trend direction, and the lower timeframe times entries.

### Concept

- **Higher timeframe (4h)**: Determines trend direction via MACD
- **Primary timeframe (1h)**: Times entries on MACD signal crossovers
- **Entry**: Only take trades in the direction confirmed by the higher timeframe
- Combines the `momentum_macd` strategy logic with multi-timeframe filtering

### Strategy Definition

```python
from keryxflow.agent.strategy import (
    MarketRegime,
    StrategyConfig,
    StrategyType,
    get_strategy_manager,
)

mtf_momentum = StrategyConfig(
    id="mtf_momentum_macd",
    name="Multi-Timeframe MACD Momentum",
    strategy_type=StrategyType.MOMENTUM,
    description="MACD momentum on 1h confirmed by 4h trend direction",
    regime_suitability={
        MarketRegime.TRENDING_UP: 0.9,
        MarketRegime.TRENDING_DOWN: 0.9,
        MarketRegime.RANGING: 0.2,
        MarketRegime.HIGH_VOLATILITY: 0.6,
        MarketRegime.LOW_VOLATILITY: 0.4,
        MarketRegime.BREAKOUT: 0.8,
    },
    parameters={
        "fast_period": 12,
        "slow_period": 26,
        "signal_period": 9,
        "primary_timeframe": "1h",
        "filter_timeframe": "4h",
    },
)

manager = get_strategy_manager()
manager.register_strategy(mtf_momentum)
```

### Multi-Timeframe Data Loading

The `DataLoader` (`keryxflow/backtester/data.py`) supports loading and resampling multiple timeframes:

```python
from keryxflow.backtester.data import DataLoader
from keryxflow.exchange.client import ExchangeClient

loader = DataLoader(exchange_client=ExchangeClient())

# Load data for multiple timeframes at once
# Fetches at the smallest TF and resamples to larger TFs
mtf_data = await loader.load_multi_timeframe(
    symbol="BTC/USDT",
    start=datetime(2024, 1, 1, tzinfo=UTC),
    end=datetime(2024, 6, 30, tzinfo=UTC),
    timeframes=["15m", "1h", "4h"],
)

# Result: {"15m": DataFrame, "1h": DataFrame, "4h": DataFrame}
```

You can also resample manually:

```python
# Load base data
df_15m = await loader.load_from_exchange("BTC/USDT", start, end, "15m")

# Resample to higher timeframes
df_1h = loader.resample(df_15m, "1h")
df_4h = loader.resample(df_15m, "4h")
```

Or load from CSV:

```python
mtf_data = loader.load_multi_timeframe_from_csv(
    path="data/btc_15m.csv",
    timeframes=["15m", "1h", "4h"],
    base_timeframe="15m",
)
```

### Configuration

```toml
# settings.toml
[oracle]
indicators = ["macd", "ema", "atr"]
macd_fast = 12
macd_slow = 26
macd_signal = 9

[oracle.mtf]
enabled = true
timeframes = ["15m", "1h", "4h"]
primary_timeframe = "1h"
filter_timeframe = "4h"
min_filter_confidence = 0.5
```

### Backtesting with MTF

The `BacktestEngine` supports multi-timeframe mode:

```python
from keryxflow.backtester.engine import BacktestEngine

engine = BacktestEngine(
    initial_balance=10000.0,
    mtf_enabled=True,
    primary_timeframe="1h",
)

# Pass MTF data as {symbol: {timeframe: DataFrame}}
result = await engine.run(
    data={"BTC/USDT": mtf_data},
)
```

Or via CLI:

```bash
poetry run keryxflow-backtest \
    --symbol BTC/USDT \
    --start 2024-01-01 \
    --end 2024-06-30 \
    --mtf
```

### How MTF Signals Work

The `MTFSignalGenerator` (`keryxflow/oracle/mtf_signals.py`):

1. Analyzes the filter timeframe (4h) to determine the dominant trend
2. Analyzes the primary timeframe (1h) for entry signals
3. Only allows entries that align with the higher-timeframe trend
4. The resulting `TradingSignal` includes `filter_trend`, `timeframe_alignment`, and `mtf_data` fields

### When to Use

- Strong directional markets
- When single-timeframe signals produce too many false entries
- For higher-conviction, lower-frequency trades

---

## Backtesting Guide

### Overview

The backtester simulates trading with historical data, applying the full signal pipeline (technical analysis → risk management → execution) with realistic slippage and commissions.

### DataLoader

Load historical data from exchanges or CSV files:

```python
from datetime import UTC, datetime
from keryxflow.backtester.data import DataLoader
from keryxflow.exchange.client import ExchangeClient

loader = DataLoader(exchange_client=ExchangeClient())

# From exchange (auto-paginates, fetches in 1000-candle batches)
df = await loader.load_from_exchange(
    symbol="BTC/USDT",
    start=datetime(2024, 1, 1, tzinfo=UTC),
    end=datetime(2024, 6, 30, tzinfo=UTC),
    timeframe="1h",
)

# From CSV (expected columns: datetime, open, high, low, close, volume)
df = loader.load_from_csv("data/btc_1h.csv")

# Validate data
is_valid = loader.validate_data(df)  # Checks columns, nulls, types
```

### BacktestEngine

Configure and run a backtest:

```python
from keryxflow.backtester.engine import BacktestEngine

engine = BacktestEngine(
    initial_balance=10000.0,  # Starting capital
    slippage=0.001,           # 0.1% slippage per trade
    commission=0.001,         # 0.1% commission per trade
    min_candles=50,           # Minimum history for analysis
)

result = await engine.run(
    data={"BTC/USDT": df},    # {symbol: DataFrame}
)
```

**Simulation loop for each candle:**

1. Update position prices and check stop loss / take profit
2. Generate signal via `SignalGenerator` (without LLM/news for speed)
3. Calculate position size via `RiskManager.calculate_safe_position_size()`
4. Validate via `RiskManager.approve_order()`
5. Execute with slippage: buy at price × (1 + slippage), sell at price × (1 - slippage)
6. Deduct commission: cost × commission rate

### BacktestResult

The result includes comprehensive metrics:

```python
from keryxflow.backtester.report import BacktestReporter

# Print formatted summary
print(BacktestReporter.print_summary(result))

# Key metrics:
result.total_return      # Decimal (0.15 = 15%)
result.win_rate          # Decimal (0.55 = 55%)
result.expectancy        # Expected $ per trade
result.profit_factor     # Gross profit / gross loss
result.sharpe_ratio      # Risk-adjusted return
result.max_drawdown      # Decimal (0.12 = 12%)
result.max_drawdown_duration  # In periods
result.total_trades      # Number of trades taken
result.trades            # list[BacktestTrade] — full trade log
result.equity_curve      # list[float] — equity over time
```

### Reporting and Export

```python
# ASCII equity chart
print(BacktestReporter.plot_equity_ascii(result, width=60, height=15))

# Trade list
print(BacktestReporter.format_trade_list(result, limit=10))

# Export to CSV
BacktestReporter.save_trades_csv(result, "output/trades.csv")
BacktestReporter.save_equity_csv(result, "output/equity.csv")
```

### CLI Usage

```bash
# Basic backtest
poetry run keryxflow-backtest \
    --symbol BTC/USDT \
    --start 2024-01-01 \
    --end 2024-06-30

# With options
poetry run keryxflow-backtest \
    --symbol BTC/USDT \
    --start 2024-01-01 \
    --end 2024-06-30 \
    --timeframe 1h \
    --balance 50000
```

---

## Optimizer Guide

### Overview

The optimizer runs grid search over parameter combinations, backtesting each one and ranking results by a chosen metric.

### ParameterGrid

Define ranges of values to test:

```python
from keryxflow.optimizer.grid import ParameterGrid, ParameterRange

grid = ParameterGrid([
    ParameterRange("rsi_period", [7, 14, 21], "oracle"),
    ParameterRange("bbands_std", [1.5, 2.0, 2.5], "oracle"),
    ParameterRange("risk_per_trade", [0.005, 0.01, 0.02], "risk"),
])

print(len(grid))  # 27 combinations (3 × 3 × 3)

# Iterate combinations
for params in grid.combinations():
    print(params)
    # {"oracle": {"rsi_period": 7, "bbands_std": 1.5}, "risk": {"risk_per_trade": 0.005}}
```

### Pre-built Grids

| Grid | Combinations | Parameters |
|------|-------------|------------|
| `ParameterGrid.default_oracle_grid()` | 81 | rsi_period, macd_fast, macd_slow, bbands_std |
| `ParameterGrid.default_risk_grid()` | 27 | risk_per_trade, min_risk_reward, atr_multiplier |
| `ParameterGrid.quick_grid()` | 27 | rsi_period, risk_per_trade, min_risk_reward |

### OptimizationEngine

Run the optimization:

```python
from keryxflow.optimizer.engine import OptimizationEngine, OptimizationConfig

config = OptimizationConfig(
    initial_balance=10000.0,
    slippage=0.001,
    commission=0.001,
)

engine = OptimizationEngine(config)

results = await engine.optimize(
    data={"BTC/USDT": ohlcv_df},
    grid=ParameterGrid.quick_grid(),
    metric="sharpe_ratio",           # Sort results by this metric
)

# Results are sorted best-first
best = results[0]
print(best.metrics.sharpe_ratio)     # Best Sharpe ratio
print(best.flat_parameters())        # {"rsi_period": 14, "risk_per_trade": 0.01, ...}
```

**How it works:**

1. Saves current global settings
2. For each parameter combination:
   - Applies parameters to `get_settings()` (oracle and risk sections)
   - Runs a full backtest via `BacktestEngine`
   - Records the `OptimizationResult` with metrics and run time
3. Restores original settings
4. Sorts results by the chosen metric

**Supported sort metrics:** `sharpe_ratio`, `total_return`, `win_rate`, `profit_factor`, `max_drawdown` (lower is better), `max_drawdown_duration` (lower is better)

### Optimization Reports

```python
from keryxflow.optimizer.report import OptimizationReport

report = OptimizationReport(results)

# Full summary with parameter sensitivity analysis
print(report.print_summary(metric="sharpe_ratio", top_n=5))

# Compact table
print(report.print_compact(metric="sharpe_ratio", top_n=10))

# Export
report.save_csv("output/optimization_results.csv")
report.save_best_params("output/best_params.txt", metric="sharpe_ratio")

# Get best parameters programmatically
best_params = report.best_parameters(metric="sharpe_ratio")
```

### CLI Usage

```bash
# Quick optimization (27 combinations)
poetry run keryxflow-optimize \
    --symbol BTC/USDT \
    --start 2024-01-01 \
    --end 2024-06-30 \
    --grid quick

# Full oracle grid (81 combinations)
poetry run keryxflow-optimize \
    --symbol BTC/USDT \
    --start 2024-01-01 \
    --end 2024-06-30
```

### Convenience Function

For quick scripting:

```python
from keryxflow.optimizer.engine import run_optimization
from keryxflow.optimizer.grid import ParameterGrid

results = await run_optimization(
    data={"BTC/USDT": df},
    grid=ParameterGrid.quick_grid(),
    metric="sharpe_ratio",
    initial_balance=10000.0,
)
```

---

## StrategyManager Registration & AI Regime Selection

### Registering Custom Strategies

```python
from keryxflow.agent.strategy import get_strategy_manager

manager = get_strategy_manager()

# Register a new strategy
manager.register_strategy(my_strategy)

# List all registered strategies
strategies = manager.list_strategies()  # list[dict]

# Get a specific strategy
strategy = manager.get_strategy("my_custom_strategy")  # StrategyConfig | None

# Check current state
current = manager.get_current_strategy()    # StrategyConfig | None
regime = manager.get_current_regime()        # MarketRegime
stats = manager.get_stats()                  # dict with selection statistics
```

### Performance Tracking

After each trade, record the result to improve future strategy selection:

```python
await manager.record_trade_result(
    strategy_id="sma_crossover_beginner",
    pnl_percentage=2.5,  # +2.5%
    won=True,
)
```

The manager tracks `total_trades`, `winning_trades`, and `total_pnl` per strategy. After 10+ trades, these metrics adjust the selection scoring:
- Win rate > 60% → +0.1 boost
- Win rate < 40% → -0.1 penalty
- Positive avg PnL → +0.05 boost

### Parameter Adaptation

Adapt strategy parameters based on optimization results or learning:

```python
success = manager.adapt_strategy_parameters(
    strategy_id="sma_crossover_beginner",
    parameter_updates={"fast_ema": 12, "slow_ema": 26},
)
# Returns True if strategy exists, False otherwise
```

### AI Regime Detection

The `detect_market_regime(prices)` method analyzes the last 50 close prices:

```python
prices = [42000.0, 42100.0, 42300.0, ...]  # At least 20 prices

regime = manager.detect_market_regime(prices)
# Returns: MarketRegime.TRENDING_UP, RANGING, etc.
```

**Detection algorithm:**

1. Compute SMA(10) and SMA(30) from recent prices
2. Calculate price change = (last - first) / first
3. Calculate volatility = (max - min) / first
4. Apply thresholds:
   - |price_change| > 5% → TRENDING_UP or TRENDING_DOWN
   - volatility > 10% → HIGH_VOLATILITY
   - volatility < 3% → LOW_VOLATILITY
   - SMA convergence < 1% → RANGING
   - Recent vol / older vol > 2x → BREAKOUT

### CognitiveAgent Integration

When agent mode is enabled (`KERYXFLOW_AGENT_ENABLED=true`), the `CognitiveAgent` replaces the standard `SignalGenerator` in the trading loop. The agent uses Claude's Tool Use API to autonomously:

1. **Perceive** — Read market data via perception tools
2. **Remember** — Query episodic and semantic memory for context
3. **Analyze** — Calculate indicators and position sizes
4. **Decide** — Make trading decisions (HOLD, ENTRY_LONG, ENTRY_SHORT, EXIT)
5. **Validate** — Check against Aegis guardrails
6. **Execute** — Place orders via guarded execution tools
7. **Learn** — Record outcomes for future improvement

The agent uses `StrategyManager.select_strategy()` as part of its analysis phase to inform its decisions with regime-appropriate strategy parameters.

---

## Best Practices

### Risk Management Integration

Every strategy operates within KeryxFlow's immutable guardrails (`keryxflow/aegis/guardrails.py`). These cannot be bypassed:

| Guardrail | Limit | Purpose |
|-----------|-------|---------|
| `MAX_POSITION_SIZE_PCT` | 10% | No single position exceeds 10% of portfolio |
| `MAX_TOTAL_EXPOSURE_PCT` | 50% | Total open positions ≤ 50% of portfolio |
| `MIN_CASH_RESERVE_PCT` | 20% | Always keep 20% in cash |
| `MAX_LOSS_PER_TRADE_PCT` | 2% | Maximum risk per individual trade |
| `MAX_DAILY_LOSS_PCT` | 5% | Circuit breaker: halt trading if daily loss exceeds 5% |
| `MAX_WEEKLY_LOSS_PCT` | 10% | Halt trading if weekly loss exceeds 10% |
| `MAX_TOTAL_DRAWDOWN_PCT` | 20% | Maximum drawdown from equity peak |
| `CONSECUTIVE_LOSSES_HALT` | 5 | Halt after 5 consecutive losing trades |
| `MAX_TRADES_PER_HOUR` | 10 | Rate limiting |
| `MAX_TRADES_PER_DAY` | 50 | Rate limiting |

### Position Sizing

The `QuantEngine.position_size()` method uses fixed fractional sizing:

```
quantity = (balance × risk_per_trade) / |entry_price - stop_loss|
```

Example: With $10,000 balance, 1% risk, entry at $50,000 and stop at $49,000:

```
quantity = ($10,000 × 0.01) / |$50,000 - $49,000| = $100 / $1,000 = 0.1 BTC
```

This ensures you never risk more than `risk_per_trade` (default 1%) of your account on any single trade.

### Backtesting Pitfalls

**Overfitting**: Optimizing too many parameters on too little data creates strategies that only work on historical data. Mitigations:
- Use out-of-sample testing (optimize on 2024 H1, validate on 2024 H2)
- Prefer fewer parameters (the `quick_grid` with 3 parameters vs. full grid with 4)
- Be skeptical of Sharpe ratios above 3.0 or win rates above 70%

**Look-ahead bias**: Ensure your strategy only uses data available at the time of the decision. The `BacktestEngine` processes candles sequentially, passing only `history[:current_index]` to the signal generator.

**Realistic costs**: Always include slippage and commissions. The backtester defaults to 0.1% each, which is realistic for major crypto pairs on Binance.

**Survivorship bias**: Don't only test on assets that performed well. Test across multiple symbols and time periods.

### Strategy Diversity

Design strategies that cover different market regimes:

```
Trending markets     → Trend following (EMA crossover)
Ranging markets      → Mean reversion (RSI + BBands)
Breakout markets     → Breakout strategies (BBand breakout)
All conditions       → Momentum (MACD) as a versatile fallback
```

The `StrategyManager` automatically selects the best strategy for current conditions based on regime suitability scores.

### Memory System Integration

Use the memory system to continuously improve:

```python
from keryxflow.memory.manager import get_memory_manager

memory = get_memory_manager()

# Build context for a trading decision
context = await memory.build_context_for_decision(
    symbol="BTC/USDT",
    technical_context={"trend": "bullish", "rsi": 45},
)

# Record trade entry
episode_id = await memory.record_trade_entry(
    trade_id="trade_001",
    symbol="BTC/USDT",
    side="buy",
    entry_price=50000.0,
    quantity=0.1,
    reasoning="EMA crossover with bullish MACD confirmation",
)

# Record trade exit
await memory.record_trade_exit(
    episode_id=episode_id,
    exit_price=51500.0,
    outcome="win",
    pnl=150.0,
    lessons_learned="EMA crossover signals are reliable in trending markets",
)
```

### Safety Rules

- Never modify files in `keryxflow/aegis/` without 100% test coverage
- Never bypass risk checks or disable circuit breakers
- Never remove safety limits from the `TradingGuardrails` frozen dataclass
- Always use `get_tool_executor()` for executing trading actions (it validates guardrails)
- Always include stop losses — the backtester skips signals without `stop_loss`
