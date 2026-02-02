# Parameter Optimization

This guide covers the parameter optimization module in KeryxFlow, which helps you find the best strategy parameters through systematic backtesting.

## Overview

Parameter optimization runs your strategy across multiple parameter combinations to find the settings that maximize your chosen metric (Sharpe ratio, total return, etc.).

```
Parameter Grid → BacktestEngine (N runs) → Results Comparison → Best Parameters
```

## Quick Start

```bash
# Run quick optimization (27 combinations)
poetry run keryxflow-optimize \
    --symbol BTC/USDT \
    --start 2024-01-01 \
    --end 2024-06-30 \
    --grid quick
```

## CLI Reference

### Required Arguments

| Argument | Description | Example |
|----------|-------------|---------|
| `--symbol`, `-s` | Trading pair(s) | `BTC/USDT ETH/USDT` |
| `--start` | Start date (YYYY-MM-DD) | `2024-01-01` |
| `--end` | End date (YYYY-MM-DD) | `2024-06-30` |

### Optional Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--grid`, `-g` | `quick` | Preset grid: `quick`, `oracle`, `risk`, `full` |
| `--param`, `-P` | - | Custom parameter (repeatable) |
| `--metric`, `-m` | `sharpe_ratio` | Metric to optimize |
| `--balance`, `-b` | `10000` | Initial balance |
| `--profile`, `-p` | `balanced` | Risk profile |
| `--timeframe`, `-t` | `1h` | Candle timeframe |
| `--data`, `-d` | - | Path to CSV data directory |
| `--output`, `-o` | - | Output directory for results |
| `--top` | `5` | Number of top results to show |
| `--compact` | - | Use compact output format |

## Preset Grids

### Quick Grid (27 combinations)
Best for fast testing. Tests core parameters that have the most impact.

```
Parameters:
  - rsi_period: 7, 14, 21
  - risk_per_trade: 0.005, 0.01, 0.02
  - min_risk_reward: 1.0, 1.5, 2.0
```

### Oracle Grid (81 combinations)
Tests technical analysis parameters.

```
Parameters:
  - rsi_period: 7, 14, 21
  - macd_fast: 8, 12, 15
  - macd_slow: 21, 26, 30
  - bbands_std: 1.5, 2.0, 2.5
```

### Risk Grid (27 combinations)
Tests risk management parameters.

```
Parameters:
  - risk_per_trade: 0.005, 0.01, 0.02
  - min_risk_reward: 1.0, 1.5, 2.0
  - atr_multiplier: 1.5, 2.0, 2.5
```

### Full Grid (2187 combinations)
Combines all oracle and risk parameters. Use with caution - takes longer to run.

## Custom Parameters

Use `--param` to define custom parameter ranges:

```bash
# Format: name:val1,val2,val3:category

poetry run keryxflow-optimize \
    --symbol BTC/USDT \
    --start 2024-01-01 \
    --end 2024-06-30 \
    --param rsi_period:7,10,14,21:oracle \
    --param rsi_overbought:70,75,80:oracle \
    --param risk_per_trade:0.005,0.01,0.015,0.02:risk
```

### Available Parameters

#### Oracle (Technical Analysis)

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

#### Risk (Position Sizing)

| Parameter | Description | Typical Range |
|-----------|-------------|---------------|
| `risk_per_trade` | Risk per trade (%) | 0.005-0.03 |
| `min_risk_reward` | Minimum risk/reward ratio | 1.0-3.0 |
| `atr_multiplier` | ATR multiplier for stops | 1.0-3.0 |
| `max_daily_drawdown` | Daily drawdown limit | 0.03-0.10 |
| `max_open_positions` | Maximum open positions | 1-5 |

## Optimization Metrics

Choose which metric to optimize for:

| Metric | Description | Use When |
|--------|-------------|----------|
| `sharpe_ratio` | Risk-adjusted return | Default - balanced approach |
| `total_return` | Raw percentage return | Maximizing profits |
| `profit_factor` | Gross profit / gross loss | Consistent profitability |
| `win_rate` | Percentage of winning trades | Higher certainty needed |

```bash
# Optimize for maximum return
poetry run keryxflow-optimize ... --metric total_return

# Optimize for consistency
poetry run keryxflow-optimize ... --metric profit_factor
```

## Output

### Terminal Report

```
==================================================
         OPTIMIZATION REPORT
==================================================

GRID SUMMARY
--------------------------------------------------
  Parameters:     3
  Combinations:   27
  Total Runtime:  4m 32s

TOP 5 RESULTS (by Sharpe Ratio)
--------------------------------------------------
  #1  Sharpe: 2.14  Return: +34.5%  Win: 65%
      rsi=14, risk=0.01, rr=1.5

  #2  Sharpe: 1.98  Return: +28.2%  Win: 62%
      rsi=14, risk=0.02, rr=1.5
      ...

PARAMETER SENSITIVITY
--------------------------------------------------
  rsi_period:
       7 -> Avg Sharpe: 1.230
      14 -> Avg Sharpe: 1.850 (best)
      21 -> Avg Sharpe: 1.540

BEST PARAMETERS
--------------------------------------------------
  rsi_period: 14
  risk_per_trade: 0.01
  min_risk_reward: 1.5
==================================================
```

### CSV Export

Save results to CSV for further analysis:

```bash
poetry run keryxflow-optimize ... --output ./results
```

This creates:
- `optimization_results.csv` - All results with parameters and metrics
- `best_parameters.txt` - Best parameter set with performance summary

## Python API

Use the optimizer programmatically:

```python
from keryxflow.optimizer import (
    ParameterGrid,
    ParameterRange,
    OptimizationEngine,
    OptimizationReport,
)

# Define parameter grid
grid = ParameterGrid([
    ParameterRange("rsi_period", [7, 14, 21], "oracle"),
    ParameterRange("risk_per_trade", [0.005, 0.01, 0.02], "risk"),
])

# Or use presets
grid = ParameterGrid.quick_grid()

# Run optimization
engine = OptimizationEngine()
results = await engine.optimize(
    data={"BTC/USDT": ohlcv_dataframe},
    grid=grid,
    metric="sharpe_ratio",
)

# Generate report
report = OptimizationReport(results)
print(report.print_summary())

# Get best parameters
best = report.best_parameters()
print(f"Best RSI period: {best['rsi_period']}")
```

### Result Analysis

```python
from keryxflow.optimizer import ResultComparator

comparator = ResultComparator(results)

# Top 10 results
top10 = comparator.top_n(10, "sharpe_ratio")

# Filter by criteria
filtered = comparator.filter_by(
    min_trades=20,
    min_win_rate=0.5,
    max_drawdown=0.15,
)

# Parameter sensitivity analysis
sensitivity = comparator.parameter_sensitivity("rsi_period", "sharpe_ratio")
print(f"Best RSI: {sensitivity.best_value}")
print(f"Variance: {sensitivity.variance}")
```

## Best Practices

### 1. Start Small
Begin with the `quick` grid to get fast feedback before running larger optimizations.

### 2. Use Sufficient Data
Use at least 6 months of historical data for meaningful results.

### 3. Avoid Overfitting
- Don't test too many parameters at once
- Use out-of-sample validation (split your data)
- Be skeptical of extreme results

### 4. Consider Transaction Costs
The backtester includes slippage and commission by default, but real-world costs may vary.

### 5. Check Sensitivity
Look at the parameter sensitivity analysis - if small changes cause large swings in performance, the strategy may be overfit.

## Troubleshooting

### "No data loaded for any symbol"
- Check that the symbol is valid on Binance
- Ensure start date is not too old (Binance has data limits)
- Try using local CSV data with `--data ./path/to/csv/`

### Optimization takes too long
- Use a smaller grid (e.g., `--grid quick`)
- Reduce the date range
- Use fewer custom parameters

### Low Sharpe ratios across all combinations
- The strategy may not be suitable for the market conditions
- Try different timeframes
- Consider adjusting the base strategy, not just parameters

## See Also

- [Backtesting](../README.md#backtesting) - Single backtest runs
- [Risk Settings](configuration.md) - Risk parameter configuration
- [Oracle Settings](configuration.md) - Technical analysis configuration
