#!/usr/bin/env python3
"""Test script for paper trading simulation."""

import asyncio
import os

# Set test database
os.environ["KERYXFLOW_DB_URL"] = "sqlite+aiosqlite:///data/test_paper.db"

from keryxflow.core.database import init_db  # noqa: E402
from keryxflow.exchange.client import ExchangeClient  # noqa: E402
from keryxflow.exchange.paper import PaperTradingEngine  # noqa: E402


async def main():
    """Simulate a paper trading session."""
    print("=" * 60)
    print("KeryxFlow - Paper Trading Simulation")
    print("=" * 60)

    # Initialize database
    print("\n[1] Initializing database...")
    await init_db()
    print("   ✓ Database ready")

    # Initialize paper trading engine
    print("\n[2] Initializing paper trading engine...")
    paper = PaperTradingEngine(initial_balance=10000.0, slippage_pct=0.001)
    await paper.initialize()

    balance = await paper.get_balance()
    print(f"   ✓ Starting balance: ${balance['total'].get('USDT', 0):,.2f} USDT")

    # Connect to Binance for real prices
    print("\n[3] Connecting to Binance for live prices...")
    client = ExchangeClient(sandbox=True)
    connected = await client.connect()

    if not connected:
        print("   ❌ Connection failed!")
        return

    print("   ✓ Connected!")

    try:
        # Get current BTC price
        ticker = await client.get_ticker("BTC/USDT")
        btc_price = ticker["last"]
        print(f"\n[4] Current BTC price: ${btc_price:,.2f}")

        # Update paper engine with real price
        paper.update_price("BTC/USDT", btc_price)

        # Simulate buying 0.05 BTC
        print("\n[5] Executing paper trade: BUY 0.05 BTC...")
        buy_result = await paper.execute_market_order(
            symbol="BTC/USDT",
            side="buy",
            amount=0.05,
        )
        print(f"   ✓ Bought 0.05 BTC at ${buy_result['price']:,.2f}")
        print(f"   ✓ Cost: ${buy_result['cost']:,.2f} USDT")

        # Check balance after buy
        balance = await paper.get_balance()
        print("\n[6] Balance after BUY:")
        print(f"   USDT: ${balance['total'].get('USDT', 0):,.2f}")
        print(f"   BTC:  {balance['total'].get('BTC', 0):.8f}")

        # Open a position with stop-loss and take-profit
        print("\n[7] Opening tracked position with SL/TP...")
        position = await paper.open_position(
            symbol="ETH/USDT",
            side="buy",
            amount=1.0,
            entry_price=3000.0,  # Simulated price
            stop_loss=2850.0,    # -5%
            take_profit=3300.0,  # +10%
        )
        paper.update_price("ETH/USDT", 3000.0)
        print(f"   ✓ Position opened: {position.symbol}")
        print(f"   Entry: ${position.entry_price:,.2f}")
        print(f"   Stop-Loss: ${position.stop_loss:,.2f}")
        print(f"   Take-Profit: ${position.take_profit:,.2f}")

        # Simulate price movement
        print("\n[8] Simulating price increase to $3,150...")
        paper.update_price("ETH/USDT", 3150.0)
        await paper.update_position_prices()

        pos = await paper.get_position("ETH/USDT")
        if pos:
            print(f"   Current price: ${pos.current_price:,.2f}")
            print(f"   Unrealized PnL: ${pos.unrealized_pnl:+,.2f} ({pos.unrealized_pnl_percentage:+.2f}%)")

        # List all positions
        print("\n[9] All open positions:")
        positions = await paper.get_positions()
        for p in positions:
            print(f"   - {p.symbol}: {p.quantity} @ ${p.entry_price:,.2f} | PnL: ${p.unrealized_pnl:+,.2f}")

        # Close ETH position
        print("\n[10] Closing ETH position...")
        close_result = await paper.close_position("ETH/USDT")
        if close_result:
            print(f"   ✓ Position closed at ${close_result['exit_price']:,.2f}")
            print(f"   ✓ Realized PnL: ${close_result['pnl']:+,.2f} ({close_result['pnl_percentage']:+.2f}%)")

        # Final balance
        balance = await paper.get_balance()
        print("\n[11] Final balance:")
        for currency, amount in balance["total"].items():
            if amount > 0:
                print(f"   {currency}: {amount:,.8f}" if currency != "USDT" else f"   {currency}: ${amount:,.2f}")

        print("\n" + "=" * 60)
        print("Paper trading simulation complete! ✓")
        print("=" * 60)

    except Exception as e:
        print(f"\n   ❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await client.disconnect()
        print("\nDisconnected from Binance.")


if __name__ == "__main__":
    asyncio.run(main())
