"""CLI runner for parameter optimization."""

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

from keryxflow.backtester.data import DataLoader
from keryxflow.core.logging import get_logger
from keryxflow.core.models import RiskProfile
from keryxflow.exchange.client import ExchangeClient
from keryxflow.optimizer.engine import OptimizationConfig, OptimizationEngine
from keryxflow.optimizer.grid import ParameterGrid, ParameterRange
from keryxflow.optimizer.report import OptimizationReport

logger = get_logger(__name__)


def parse_date(date_str: str) -> datetime:
    """Parse date string to datetime."""
    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)


def parse_risk_profile(profile_str: str) -> RiskProfile:
    """Parse risk profile string."""
    profiles = {
        "conservative": RiskProfile.CONSERVATIVE,
        "balanced": RiskProfile.BALANCED,
        "aggressive": RiskProfile.AGGRESSIVE,
    }
    return profiles.get(profile_str.lower(), RiskProfile.BALANCED)


def parse_grid_type(grid_str: str) -> str:
    """Parse grid type string."""
    valid = {"quick", "oracle", "risk", "full"}
    if grid_str.lower() in valid:
        return grid_str.lower()
    return "quick"


def build_grid(grid_type: str) -> ParameterGrid:
    """Build parameter grid based on type.

    Args:
        grid_type: One of 'quick', 'oracle', 'risk', 'full'

    Returns:
        ParameterGrid configured for the type
    """
    if grid_type == "quick":
        return ParameterGrid.quick_grid()

    elif grid_type == "oracle":
        return ParameterGrid.default_oracle_grid()

    elif grid_type == "risk":
        return ParameterGrid.default_risk_grid()

    elif grid_type == "full":
        # Combine oracle and risk grids
        grid = ParameterGrid()
        for r in ParameterGrid.default_oracle_grid().ranges:
            grid.add(r)
        for r in ParameterGrid.default_risk_grid().ranges:
            grid.add(r)
        return grid

    return ParameterGrid.quick_grid()


def build_custom_grid(params: list[str]) -> ParameterGrid:
    """Build a custom grid from CLI parameters.

    Args:
        params: List of "name:val1,val2,val3:category" strings

    Returns:
        ParameterGrid with specified parameters
    """
    grid = ParameterGrid()

    for param_str in params:
        parts = param_str.split(":")
        if len(parts) < 2:
            print(f"Warning: Invalid parameter format '{param_str}', skipping")
            continue

        name = parts[0]
        values_str = parts[1]
        category = parts[2] if len(parts) > 2 else "oracle"

        # Parse values
        values = []
        for v in values_str.split(","):
            v = v.strip()
            try:
                if "." in v:
                    values.append(float(v))
                else:
                    values.append(int(v))
            except ValueError:
                values.append(v)

        grid.add(ParameterRange(name, values, category))

    return grid


async def run_optimization(
    symbols: list[str],
    start: datetime,
    end: datetime,
    grid: ParameterGrid,
    metric: str = "sharpe_ratio",
    initial_balance: float = 10000.0,
    risk_profile: RiskProfile = RiskProfile.BALANCED,
    timeframe: str = "1h",
    data_source: str | None = None,
    slippage: float = 0.001,
    commission: float = 0.001,
) -> OptimizationReport:
    """Run parameter optimization.

    Args:
        symbols: List of trading pairs
        start: Start datetime
        end: End datetime
        grid: Parameter grid to test
        metric: Metric to optimize for
        initial_balance: Starting balance
        risk_profile: Base risk profile
        timeframe: Candle timeframe
        data_source: Path to CSV directory (optional)
        slippage: Slippage percentage
        commission: Commission percentage

    Returns:
        OptimizationReport with results
    """
    # Load data
    if data_source and Path(data_source).exists():
        loader = DataLoader()
        data = {}
        for symbol in symbols:
            csv_name = symbol.replace("/", "_") + ".csv"
            csv_path = Path(data_source) / csv_name
            if csv_path.exists():
                data[symbol] = loader.load_from_csv(csv_path)
            else:
                logger.warning("csv_not_found", symbol=symbol, path=str(csv_path))
    else:
        exchange = ExchangeClient()
        await exchange.connect()

        try:
            loader = DataLoader(exchange_client=exchange)
            data = {}

            for symbol in symbols:
                df = await loader.load_from_exchange(
                    symbol=symbol,
                    start=start,
                    end=end,
                    timeframe=timeframe,
                )
                data[symbol] = df
        finally:
            await exchange.disconnect()

    if not data:
        raise ValueError("No data loaded for any symbol")

    # Configure optimization
    config = OptimizationConfig(
        initial_balance=initial_balance,
        risk_profile=risk_profile,
        slippage=slippage,
        commission=commission,
    )

    # Progress callback
    def progress(current: int, total: int, params: dict):
        flat = {**params.get("oracle", {}), **params.get("risk", {})}
        param_str = ", ".join(f"{k}={v}" for k, v in flat.items())
        print(f"\r  [{current}/{total}] Testing: {param_str[:50]}...", end="", flush=True)

    # Run optimization
    engine = OptimizationEngine(config)

    print(f"\nRunning {len(grid)} backtests...")

    results = await engine.optimize(
        data=data,
        grid=grid,
        metric=metric,
        start=start,
        end=end,
        progress_callback=progress,
    )

    print()  # Newline after progress

    return OptimizationReport(results)


def main() -> None:
    """CLI entry point for optimization."""
    parser = argparse.ArgumentParser(
        description="KeryxFlow Parameter Optimization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick optimization (27 combinations)
  %(prog)s --symbol BTC/USDT --start 2024-01-01 --end 2024-06-30 --grid quick

  # Full optimization (oracle + risk parameters)
  %(prog)s --symbol BTC/USDT --start 2024-01-01 --end 2024-06-30 --grid full

  # Custom parameters
  %(prog)s --symbol BTC/USDT --start 2024-01-01 --end 2024-06-30 \\
           --param rsi_period:7,14,21:oracle \\
           --param risk_per_trade:0.005,0.01,0.02:risk

  # Save results to CSV
  %(prog)s --symbol BTC/USDT --start 2024-01-01 --end 2024-06-30 \\
           --output ./results

Grid types:
  quick   - 27 combinations (rsi_period, risk_per_trade, min_risk_reward)
  oracle  - 81 combinations (rsi, macd, bbands parameters)
  risk    - 27 combinations (risk_per_trade, min_risk_reward, atr_multiplier)
  full    - 2187 combinations (all oracle + risk parameters)
        """,
    )

    parser.add_argument(
        "--symbol",
        "-s",
        nargs="+",
        required=True,
        help="Trading pairs (e.g., BTC/USDT ETH/USDT)",
    )

    parser.add_argument(
        "--start",
        required=True,
        help="Start date (YYYY-MM-DD)",
    )

    parser.add_argument(
        "--end",
        required=True,
        help="End date (YYYY-MM-DD)",
    )

    parser.add_argument(
        "--grid",
        "-g",
        choices=["quick", "oracle", "risk", "full"],
        default="quick",
        help="Preset grid type (default: quick)",
    )

    parser.add_argument(
        "--param",
        "-P",
        action="append",
        default=[],
        help="Custom parameter: name:val1,val2,val3[:category]",
    )

    parser.add_argument(
        "--metric",
        "-m",
        default="sharpe_ratio",
        choices=["sharpe_ratio", "total_return", "profit_factor", "win_rate"],
        help="Metric to optimize for (default: sharpe_ratio)",
    )

    parser.add_argument(
        "--balance",
        "-b",
        type=float,
        default=10000.0,
        help="Initial balance (default: 10000)",
    )

    parser.add_argument(
        "--profile",
        "-p",
        choices=["conservative", "balanced", "aggressive"],
        default="balanced",
        help="Base risk profile (default: balanced)",
    )

    parser.add_argument(
        "--timeframe",
        "-t",
        default="1h",
        help="Candle timeframe (default: 1h)",
    )

    parser.add_argument(
        "--data",
        "-d",
        help="Path to directory with CSV files (optional)",
    )

    parser.add_argument(
        "--slippage",
        type=float,
        default=0.001,
        help="Slippage percentage (default: 0.001 = 0.1%%)",
    )

    parser.add_argument(
        "--commission",
        type=float,
        default=0.001,
        help="Commission percentage (default: 0.001 = 0.1%%)",
    )

    parser.add_argument(
        "--output",
        "-o",
        help="Output directory for results",
    )

    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="Number of top results to show (default: 5)",
    )

    parser.add_argument(
        "--compact",
        action="store_true",
        help="Use compact output format",
    )

    args = parser.parse_args()

    # Parse arguments
    start = parse_date(args.start)
    end = parse_date(args.end)
    risk_profile = parse_risk_profile(args.profile)

    # Build grid
    grid = build_custom_grid(args.param) if args.param else build_grid(args.grid)

    if len(grid) == 0:
        print("Error: No parameter combinations to test")
        sys.exit(1)

    # Print header
    print("\nKeryxFlow Parameter Optimization")
    print(f"Symbols: {', '.join(args.symbol)}")
    print(f"Period: {args.start} to {args.end}")
    print(f"Timeframe: {args.timeframe}")
    print(f"Grid: {grid}")
    print(f"Optimizing for: {args.metric}")

    # Run optimization
    try:
        report = asyncio.run(
            run_optimization(
                symbols=args.symbol,
                start=start,
                end=end,
                grid=grid,
                metric=args.metric,
                initial_balance=args.balance,
                risk_profile=risk_profile,
                timeframe=args.timeframe,
                data_source=args.data,
                slippage=args.slippage,
                commission=args.commission,
            )
        )
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)

    # Print results
    if args.compact:
        print(report.print_compact(args.metric, args.top))
    else:
        print(report.print_summary(args.metric, args.top))

    # Save outputs
    if args.output:
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save all results
        csv_path = output_dir / "optimization_results.csv"
        report.save_csv(csv_path)
        print(f"\nSaved results to: {csv_path}")

        # Save best parameters
        params_path = output_dir / "best_parameters.txt"
        report.save_best_params(params_path, args.metric)
        print(f"Saved best parameters to: {params_path}")


if __name__ == "__main__":
    main()
