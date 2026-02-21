# Strategy Development Guide

The complete reference for building, testing, optimizing, and deploying trading strategies with KeryxFlow.

## Strategy Framework

### StrategyConfig

Strategies are defined using `StrategyConfig` (`keryxflow/agent/strategy.py`):

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

### StrategyType

| Type | Description |
|------|-------------|
| `TREND_FOLLOWING` | Follow established price trends |
| `MEAN_REVERSION` | Trade reversals at extremes |
| `BREAKOUT` | Trade price breakouts from ranges |
| `MOMENTUM` | Trade momentum shifts (MACD, etc.) |
| `SCALPING` | Short-term rapid trades |
| `SWING` | Multi-day position trades |

### MarketRegime

The `StrategyManager.detect_market_regime(prices)` method classifies current market conditions:

| Regime | Detection Criteria |
|--------|-------------------|
| `TRENDING_UP` | Price change > +5% over window |
| `TRENDING_DOWN` | Price change < -5% over window |
| `RANGING` | SMA(10) and SMA(30) converging (< 1% difference) |
| `HIGH_VOLATILITY` | Price range > 10% of starting price |
| `LOW_VOLATILITY` | Price range < 3% of starting price |
| `BREAKOUT` | Recent 5-bar volatility > 2x older 15-bar volatility |
| `UNKNOWN` | Insufficient data or no clear regime |

**Detection algorithm:** Computes SMA(10) and SMA(30) from recent prices, calculates price change and volatility, then applies the thresholds above.

---

## Built-in Strategies

KeryxFlow ships with four default strategies in `StrategyManager.DEFAULT_STRATEGIES`:

| ID | Type | Best Regimes | Key Parameters |
|----|------|-------------|----------------|
| `trend_following_basic` | TREND_FOLLOWING | TRENDING_UP/DOWN (0.9) | fast_ema=9, slow_ema=21 |
| `mean_reversion_rsi` | MEAN_REVERSION | RANGING (0.9), LOW_VOL (0.8) | rsi_period=14, oversold=30, overbought=70 |
| `breakout_bollinger` | BREAKOUT | BREAKOUT (0.95), HIGH_VOL (0.7) | bb_period=20, bb_std=2.0, volume_confirmation=True |
| `momentum_macd` | MOMENTUM | TRENDING_UP/DOWN (0.8), BREAKOUT (0.7) | fast=12, slow=26, signal=9 |

---

## Creating Custom Strategies

### Step 1: Define and Register

```python
from keryxflow.agent.strategy import get_strategy_manager

manager = get_strategy_manager()
manager.register_strategy(my_strategy)
```

### Step 2: Configure Oracle Parameters

Strategy parameters map to `OracleSettings` in `keryxflow/config.py`:

```toml
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

### Step 3: Strategy Selection

The `StrategyManager.select_strategy()` method:

1. Calls `detect_market_regime(prices)` on recent close prices
2. Scores each active strategy: `base_score = regime_suitability[current_regime]`
3. Adjusts for performance: +0.1 if win_rate > 60%, -0.1 if < 40%, +0.05 if avg_pnl > 0
4. Returns a `StrategySelection` with the highest-scoring strategy

```python
selection = await manager.select_strategy(
    symbol="BTC/USDT",
    prices=recent_close_prices,  # list[float], at least 20 prices
)

print(selection.strategy.name)          # "Basic Trend Following"
print(selection.detected_regime)        # MarketRegime.TRENDING_UP
print(selection.confidence)             # 0.9
print(selection.alternative_strategies) # ["momentum_macd", "breakout_bollinger"]
```

### Performance Tracking

Record trade results to improve future selection:

```python
await manager.record_trade_result(
    strategy_id="my_custom_strategy",
    pnl_percentage=2.5,
    won=True,
)
```

After 10+ trades, the manager adjusts selection scoring based on win rate and PnL.

### Parameter Adaptation

```python
manager.adapt_strategy_parameters(
    strategy_id="my_custom_strategy",
    parameter_updates={"fast_ema": 12, "slow_ema": 26},
)
```

---

## Strategy Examples

### SMA Crossover (Beginner)

Buy when the fast EMA (9) crosses above the slow EMA (21). Sell on the opposite cross. Best in trending markets.

```python
sma_crossover = StrategyConfig(
    id="sma_crossover_beginner",
    name="SMA Crossover",
    strategy_type=StrategyType.TREND_FOLLOWING,
    description="Trade EMA 9/21 crossovers with ATR-based stops",
    regime_suitability={
        MarketRegime.TRENDING_UP: 0.9,
        MarketRegime.TRENDING_DOWN: 0.9,
        MarketRegime.RANGING: 0.2,
        MarketRegime.HIGH_VOLATILITY: 0.5,
        MarketRegime.LOW_VOLATILITY: 0.6,
        MarketRegime.BREAKOUT: 0.7,
    },
    parameters={"fast_ema": 9, "slow_ema": 21, "confirmation_candles": 2},
)
```

### RSI + Bollinger Bands (Intermediate)

Buy when RSI < 30 AND price near lower Bollinger Band. Sell when RSI > 70 AND price near upper band. Best in ranging markets.

```python
rsi_bbands = StrategyConfig(
    id="rsi_bbands_reversion",
    name="RSI + Bollinger Mean Reversion",
    strategy_type=StrategyType.MEAN_REVERSION,
    description="Trade reversals when RSI extremes align with Bollinger Band touches",
    regime_suitability={
        MarketRegime.TRENDING_UP: 0.3,
        MarketRegime.TRENDING_DOWN: 0.3,
        MarketRegime.RANGING: 0.9,
        MarketRegime.HIGH_VOLATILITY: 0.4,
        MarketRegime.LOW_VOLATILITY: 0.8,
        MarketRegime.BREAKOUT: 0.2,
    },
    parameters={
        "rsi_period": 14, "rsi_oversold": 30, "rsi_overbought": 70,
        "bbands_period": 20, "bbands_std": 2.0,
    },
)
```

### Multi-Timeframe Momentum (Advanced)

MACD momentum on 1h confirmed by 4h trend direction. Only takes trades aligned with the higher-timeframe trend.

```python
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
        "fast_period": 12, "slow_period": 26, "signal_period": 9,
        "primary_timeframe": "1h", "filter_timeframe": "4h",
    },
)
```

Enable MTF in config:

```toml
[oracle.mtf]
enabled = true
timeframes = ["15m", "1h", "4h"]
primary_timeframe = "1h"
filter_timeframe = "4h"
```

---

## Backtesting

### Overview

The backtester (`keryxflow/backtester/`) simulates trading with historical data, applying the full signal pipeline (technical analysis → risk management → execution) with realistic slippage and commissions.

### Loading Data

```python
from datetime import UTC, datetime
from keryxflow.backtester.data import DataLoader
from keryxflow.exchange.client import ExchangeClient

loader = DataLoader(exchange_client=ExchangeClient())

# From exchange (auto-paginates in 1000-candle batches)
df = await loader.load_from_exchange(
    symbol="BTC/USDT",
    start=datetime(2024, 1, 1, tzinfo=UTC),
    end=datetime(2024, 6, 30, tzinfo=UTC),
    timeframe="1h",
)

# From CSV (columns: datetime, open, high, low, close, volume)
df = loader.load_from_csv("data/btc_1h.csv")

# Multi-timeframe
mtf_data = await loader.load_multi_timeframe(
    symbol="BTC/USDT", start=start, end=end,
    timeframes=["15m", "1h", "4h"],
)
```

### Running a Backtest

```python
from keryxflow.backtester.engine import BacktestEngine

engine = BacktestEngine(
    initial_balance=10000.0,
    slippage=0.001,      # 0.1%
    commission=0.001,    # 0.1%
    min_candles=50,
)

result = await engine.run(data={"BTC/USDT": df})
```

**Simulation loop per candle:**
1. Update position prices, check stop loss / take profit
2. Generate signal via `SignalGenerator` (without LLM/news for speed)
3. Calculate position size via `RiskManager.calculate_safe_position_size()`
4. Validate via `RiskManager.approve_order()`
5. Execute with slippage and commission

### Results

```python
result.total_return       # Decimal (0.15 = 15%)
result.win_rate           # Decimal (0.55 = 55%)
result.expectancy         # Expected $ per trade
result.profit_factor      # Gross profit / gross loss
result.sharpe_ratio       # Risk-adjusted return
result.max_drawdown       # Decimal (0.12 = 12%)
result.total_trades       # Number of trades taken
result.equity_curve       # list[float]
result.trades             # list[BacktestTrade]
```

### Reporting

```python
from keryxflow.backtester.report import BacktestReporter

print(BacktestReporter.print_summary(result))
print(BacktestReporter.plot_equity_ascii(result, width=60, height=15))
print(BacktestReporter.format_trade_list(result, limit=10))

BacktestReporter.save_trades_csv(result, "output/trades.csv")
BacktestReporter.save_equity_csv(result, "output/equity.csv")
```

### CLI

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
    --balance 50000 \
    --mtf
```

---

## Walk-Forward Analysis

The `WalkForwardEngine` (`keryxflow/backtester/walk_forward.py`) splits historical data into rolling train/test windows to validate strategy robustness and detect overfitting.

```
|---- In-Sample (70%) ----|-- Out-of-Sample (30%) --|
        Window 1: Optimize → Test
              Window 2: Optimize → Test
                    Window 3: Optimize → Test
```

```bash
poetry run keryxflow-backtest \
    --symbol BTC/USDT \
    --start 2024-01-01 \
    --end 2024-12-31 \
    --walk-forward \
    --in-sample-pct 70 \
    --steps 5
```

**Output:** Per-window optimized parameters and out-of-sample performance, walk-forward efficiency ratio, aggregate out-of-sample equity curve. An efficiency ratio above 0.5 suggests the strategy generalizes well.

---

## Monte Carlo Simulation

The `MonteCarloSimulator` (`keryxflow/backtester/monte_carlo.py`) runs randomized permutations of trade sequences to estimate risk metrics.

```bash
poetry run keryxflow-backtest \
    --symbol BTC/USDT \
    --start 2024-01-01 \
    --end 2024-06-30 \
    --monte-carlo \
    --simulations 1000
```

**How it works:**
1. Run a standard backtest to get the list of trades
2. Randomly shuffle trade order across N simulations
3. Calculate statistics across all simulations (percentiles for drawdown, return, etc.)

**Output:** Median, 5th, and 95th percentile for total return. Worst-case max drawdown. Probability of ruin. Confidence intervals for key metrics.

**Interpreting results:**
- 5th percentile return still positive → strategy is likely robust
- 95th percentile drawdown exceeds risk tolerance → reduce position sizing
- Large gap between median Monte Carlo and original backtest → sequence dependency

### Running Both Together

```bash
poetry run keryxflow-backtest \
    --symbol BTC/USDT \
    --start 2024-01-01 \
    --end 2024-12-31 \
    --walk-forward --steps 5 \
    --monte-carlo --simulations 1000
```

---

## Parameter Optimization

The optimizer (`keryxflow/optimizer/`) runs grid search over parameter combinations, backtesting each one and ranking results by a chosen metric.

### Quick Start

```bash
poetry run keryxflow-optimize \
    --symbol BTC/USDT \
    --start 2024-01-01 \
    --end 2024-06-30 \
    --grid quick
```

### Parameter Grids

Define ranges of values to test:

```python
from keryxflow.optimizer.grid import ParameterGrid, ParameterRange

grid = ParameterGrid([
    ParameterRange("rsi_period", [7, 14, 21], "oracle"),
    ParameterRange("bbands_std", [1.5, 2.0, 2.5], "oracle"),
    ParameterRange("risk_per_trade", [0.005, 0.01, 0.02], "risk"),
])

print(len(grid))  # 27 combinations (3 × 3 × 3)
```

### Preset Grids

| Grid | Combinations | Parameters |
|------|-------------|------------|
| `ParameterGrid.quick_grid()` | 27 | rsi_period, risk_per_trade, min_risk_reward |
| `ParameterGrid.default_oracle_grid()` | 81 | rsi_period, macd_fast, macd_slow, bbands_std |
| `ParameterGrid.default_risk_grid()` | 27 | risk_per_trade, min_risk_reward, atr_multiplier |

### Running Optimization

```python
from keryxflow.optimizer.engine import OptimizationEngine

engine = OptimizationEngine()
results = await engine.optimize(
    data={"BTC/USDT": ohlcv_df},
    grid=ParameterGrid.quick_grid(),
    metric="sharpe_ratio",
)

best = results[0]
print(best.metrics.sharpe_ratio)
print(best.flat_parameters())
```

**How it works:**
1. Saves current global settings
2. For each parameter combination: applies parameters, runs backtest, records result
3. Restores original settings
4. Sorts results by the chosen metric

### Optimization Metrics

| Metric | Description | Use When |
|--------|-------------|----------|
| `sharpe_ratio` | Risk-adjusted return | Default — balanced approach |
| `total_return` | Raw percentage return | Maximizing profits |
| `profit_factor` | Gross profit / gross loss | Consistent profitability |
| `win_rate` | Percentage of winning trades | Higher certainty needed |
| `max_drawdown` | Largest peak-to-trough decline | Lower is better |

### Reports

```python
from keryxflow.optimizer.report import OptimizationReport

report = OptimizationReport(results)
print(report.print_summary(metric="sharpe_ratio", top_n=5))
print(report.print_compact(metric="sharpe_ratio", top_n=10))

report.save_csv("output/optimization_results.csv")
report.save_best_params("output/best_params.txt", metric="sharpe_ratio")
```

### CLI Reference

| Argument | Default | Description |
|----------|---------|-------------|
| `--symbol`, `-s` | required | Trading pair(s) |
| `--start` | required | Start date (YYYY-MM-DD) |
| `--end` | required | End date (YYYY-MM-DD) |
| `--grid`, `-g` | `quick` | Preset grid: `quick`, `oracle`, `risk`, `full` |
| `--param`, `-P` | - | Custom parameter: `name:val1,val2:category` |
| `--metric`, `-m` | `sharpe_ratio` | Metric to optimize |
| `--balance`, `-b` | `10000` | Initial balance |
| `--timeframe`, `-t` | `1h` | Candle timeframe |
| `--output`, `-o` | - | Output directory for CSV results |
| `--top` | `5` | Number of top results to show |
| `--compact` | - | Use compact output format |

**Custom parameters example:**

```bash
poetry run keryxflow-optimize \
    --symbol BTC/USDT \
    --start 2024-01-01 \
    --end 2024-06-30 \
    --param rsi_period:7,10,14,21:oracle \
    --param rsi_overbought:70,75,80:oracle \
    --param risk_per_trade:0.005,0.01,0.015,0.02:risk
```

### Available Parameters

**Oracle (Technical Analysis):**

| Parameter | Description | Typical Range |
|-----------|-------------|---------------|
| `rsi_period` | RSI calculation period | 7-21 |
| `rsi_overbought` | RSI overbought threshold | 65-80 |
| `rsi_oversold` | RSI oversold threshold | 20-35 |
| `macd_fast` | MACD fast EMA period | 8-15 |
| `macd_slow` | MACD slow EMA period | 20-35 |
| `macd_signal` | MACD signal line period | 7-12 |
| `bbands_period` | Bollinger Bands period | 15-25 |
| `bbands_std` | Bollinger Bands std dev | 1.5-2.5 |

**Risk (Position Sizing):**

| Parameter | Description | Typical Range |
|-----------|-------------|---------------|
| `risk_per_trade` | Risk per trade (decimal) | 0.005-0.03 |
| `min_risk_reward` | Minimum risk/reward ratio | 1.0-3.0 |
| `atr_multiplier` | ATR multiplier for stops | 1.0-3.0 |
| `max_daily_drawdown` | Daily drawdown limit | 0.03-0.10 |
| `max_open_positions` | Maximum open positions | 1-5 |

---

## Best Practices

### Avoid Overfitting

- Don't test too many parameters on too little data
- Use out-of-sample testing (optimize on H1, validate on H2)
- Prefer fewer parameters (`quick_grid` with 3 vs. full grid with 4+)
- Be skeptical of Sharpe ratios above 3.0 or win rates above 70%
- Use walk-forward analysis and Monte Carlo to validate

### Realistic Backtesting

- Always include slippage and commissions (default 0.1% each)
- The `BacktestEngine` processes candles sequentially — no look-ahead bias
- Test across multiple symbols and time periods to avoid survivorship bias
- Use at least 6 months of historical data

### Strategy Diversity

Design strategies that cover different market regimes:

```
Trending markets     → Trend following (EMA crossover)
Ranging markets      → Mean reversion (RSI + BBands)
Breakout markets     → Breakout strategies (BBand breakout)
All conditions       → Momentum (MACD) as a versatile fallback
```

The `StrategyManager` automatically selects the best strategy for current conditions.

### Safety Rules

- Never modify files in `keryxflow/aegis/` without 100% test coverage
- Never bypass risk checks or disable circuit breakers
- Always use `get_tool_executor()` for executing trading actions (validates guardrails)
- Always include stop losses — the backtester skips signals without `stop_loss`
