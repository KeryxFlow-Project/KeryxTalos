#!/usr/bin/env python3
"""Simple runner for KeryxFlow - MVP demo."""

import asyncio
import signal
import sys
from datetime import datetime

# Ensure we use the project's data directory
import os
os.makedirs("data", exist_ok=True)
os.environ.setdefault("KERYXFLOW_DB_URL", "sqlite+aiosqlite:///data/keryxflow.db")


async def main():
    """Run KeryxFlow in simple mode."""
    from keryxflow.core.database import init_db
    from keryxflow.exchange.client import ExchangeClient
    from keryxflow.exchange.paper import PaperTradingEngine

    print()
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║                                                               ║")
    print("║   ██╗  ██╗███████╗██████╗ ██╗   ██╗██╗  ██╗                   ║")
    print("║   ██║ ██╔╝██╔════╝██╔══██╗╚██╗ ██╔╝╚██╗██╔╝                   ║")
    print("║   █████╔╝ █████╗  ██████╔╝ ╚████╔╝  ╚███╔╝                    ║")
    print("║   ██╔═██╗ ██╔══╝  ██╔══██╗  ╚██╔╝   ██╔██╗                    ║")
    print("║   ██║  ██╗███████╗██║  ██║   ██║   ██╔╝ ██╗                   ║")
    print("║   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝  FLOW            ║")
    print("║                                                               ║")
    print("║   Your keys, your trades, your code.                         ║")
    print("║                                                               ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    print()
    print("  Mode: PAPER TRADING (simulated)")
    print("  Press Ctrl+C to stop")
    print()
    print("─" * 65)

    # Initialize
    print("\n  [1/3] Initializing database...")
    await init_db()
    print("        ✓ Database ready")

    print("\n  [2/3] Initializing paper trading engine...")
    paper = PaperTradingEngine(initial_balance=10000.0)
    await paper.initialize()
    balance = await paper.get_balance()
    usdt = balance["total"].get("USDT", 0)
    print(f"        ✓ Balance: ${usdt:,.2f} USDT")

    print("\n  [3/3] Connecting to Binance (sandbox)...")
    client = ExchangeClient(sandbox=True)
    connected = await client.connect()

    if not connected:
        print("        ✗ Connection failed!")
        return

    print("        ✓ Connected!")
    print()
    print("─" * 65)
    print()

    # Flag for graceful shutdown
    running = True

    def signal_handler(sig, frame):
        nonlocal running
        print("\n\n  Shutting down gracefully...")
        running = False

    signal.signal(signal.SIGINT, signal_handler)

    symbols = ["BTC/USDT", "ETH/USDT"]

    try:
        print("  LIVE PRICE FEED")
        print("  " + "─" * 40)
        print()

        iteration = 0
        while running:
            iteration += 1
            now = datetime.now().strftime("%H:%M:%S")

            for symbol in symbols:
                try:
                    ticker = await client.get_ticker(symbol)
                    price = ticker["last"]
                    volume = ticker["volume"]

                    # Update paper engine
                    paper.update_price(symbol, price)

                    # Format symbol for display
                    base = symbol.split("/")[0]

                    # Simple price display
                    print(f"  [{now}] {base:>4}: ${price:>12,.2f}  │  Vol: {volume:>12,.4f}")

                except Exception as e:
                    print(f"  [{now}] {symbol}: Error - {e}")

            # Show balance every 10 iterations
            if iteration % 10 == 0:
                balance = await paper.get_balance()
                print()
                print("  " + "─" * 40)
                print("  PORTFOLIO:")
                for curr, amt in balance["total"].items():
                    if amt > 0:
                        if curr == "USDT":
                            print(f"    {curr}: ${amt:,.2f}")
                        else:
                            price = paper.get_price(f"{curr}/USDT") or 0
                            value = amt * price
                            print(f"    {curr}: {amt:.8f} (≈${value:,.2f})")
                print("  " + "─" * 40)
                print()

            await asyncio.sleep(5)  # Update every 5 seconds

    except asyncio.CancelledError:
        pass
    finally:
        await client.disconnect()
        print()
        print("  ✓ Disconnected from Binance")
        print()
        print("  Stack sats. ₿")
        print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
