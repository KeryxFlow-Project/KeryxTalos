"""CLI runner for backtesting."""

import argparse
import asyncio
from datetime import UTC, datetime
from pathlib import Path

from keryxflow.backtester.data import DataLoader
from keryxflow.backtester.engine import BacktestEngine
from keryxflow.backtester.report import BacktestReporter, BacktestResult
from keryxflow.core.logging import get_logger
from keryxflow.core.models import RiskProfile
from keryxflow.exchange.client import ExchangeClient

logger = get_logger(__name__)


async def run_backtest(
    symbols: list[str],
    start: datetime,
    end: datetime,
    initial_balance: float = 10000.0,
    risk_profile: RiskProfile = RiskProfile.BALANCED,
    timeframe: str = "1h",
    data_source: str | None = None,
    slippage: float = 0.001,
    commission: float = 0.001,
) -> BacktestResult:
    """
    Run a complete backtest.

    Args:
        symbols: List of trading pairs
        start: Start datetime
        end: End datetime
        initial_balance: Starting balance
        risk_profile: Risk profile to use
        timeframe: Candle timeframe
        data_source: Path to CSV file (if None, uses exchange)
        slippage: Slippage percentage
        commission: Commission percentage

    Returns:
        BacktestResult with metrics
    """
    # Load data
    if data_source and Path(data_source).exists():
        # Load from CSV
        loader = DataLoader()
        data = {}
        for symbol in symbols:
            # Assume CSV is named like BTC_USDT.csv
            csv_name = symbol.replace("/", "_") + ".csv"
            csv_path = Path(data_source) / csv_name
            if csv_path.exists():
                data[symbol] = loader.load_from_csv(csv_path)
            else:
                logger.warning("csv_not_found", symbol=symbol, path=str(csv_path))
    else:
        # Load from exchange
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

    # Create and run backtest engine
    engine = BacktestEngine(
        initial_balance=initial_balance,
        risk_profile=risk_profile,
        slippage=slippage,
        commission=commission,
    )

    result = await engine.run(data, start=start, end=end)

    return result


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


def main() -> None:
    """CLI entry point for backtesting."""
    parser = argparse.ArgumentParser(
        description="KeryxFlow Backtesting Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Backtest BTC/USDT for 2024
  %(prog)s --symbol BTC/USDT --start 2024-01-01 --end 2024-06-30

  # Backtest with custom settings
  %(prog)s --symbol BTC/USDT ETH/USDT --start 2024-01-01 --end 2024-06-30 \\
           --balance 50000 --profile aggressive --timeframe 4h

  # Backtest from CSV files
  %(prog)s --symbol BTC/USDT --start 2024-01-01 --end 2024-12-31 \\
           --data ./historical_data/
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
        help="Risk profile (default: balanced)",
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
        help="Output directory for CSV reports",
    )

    parser.add_argument(
        "--chart",
        action="store_true",
        help="Show ASCII equity chart",
    )

    parser.add_argument(
        "--trades",
        type=int,
        default=0,
        help="Show last N trades (default: 0 = none)",
    )

    args = parser.parse_args()

    # Parse arguments
    start = parse_date(args.start)
    end = parse_date(args.end)
    risk_profile = parse_risk_profile(args.profile)

    print("\nKeryxFlow Backtest")
    print(f"Symbols: {', '.join(args.symbol)}")
    print(f"Period: {args.start} to {args.end}")
    print(f"Timeframe: {args.timeframe}")
    print(f"Risk Profile: {args.profile}")
    print(f"Initial Balance: ${args.balance:,.2f}")
    print("\nLoading data and running backtest...")

    # Run backtest
    try:
        result = asyncio.run(
            run_backtest(
                symbols=args.symbol,
                start=start,
                end=end,
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
        return

    # Print summary
    print(BacktestReporter.print_summary(result))

    # Show chart if requested
    if args.chart:
        print("\nEQUITY CURVE")
        print(BacktestReporter.plot_equity_ascii(result))

    # Show trades if requested
    if args.trades > 0:
        print(BacktestReporter.format_trade_list(result, limit=args.trades))

    # Save outputs if requested
    if args.output:
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)

        trades_path = output_dir / "trades.csv"
        equity_path = output_dir / "equity.csv"

        BacktestReporter.save_trades_csv(result, trades_path)
        BacktestReporter.save_equity_csv(result, equity_path)

        print(f"\nSaved trades to: {trades_path}")
        print(f"Saved equity curve to: {equity_path}")


if __name__ == "__main__":
    main()
