#!/usr/bin/env python3
"""Quick test script for Binance connectivity."""

import asyncio

from keryxflow.exchange.client import ExchangeClient


async def main():
    """Test Binance connection and fetch some data."""
    print("=" * 50)
    print("KeryxFlow - Binance Connection Test")
    print("=" * 50)

    client = ExchangeClient(sandbox=True)

    print("\n[1] Connecting to Binance (sandbox mode)...")
    connected = await client.connect()

    if not connected:
        print("   ❌ Connection failed!")
        return

    print("   ✓ Connected!")

    try:
        # Fetch BTC/USDT ticker
        print("\n[2] Fetching BTC/USDT ticker...")
        ticker = await client.get_ticker("BTC/USDT")
        print(f"   Symbol: {ticker['symbol']}")
        print(f"   Last:   ${ticker['last']:,.2f}")
        print(f"   Bid:    ${ticker['bid']:,.2f}")
        print(f"   Ask:    ${ticker['ask']:,.2f}")
        print(f"   Volume: {ticker['volume']:,.4f} BTC")

        # Fetch OHLCV data
        print("\n[3] Fetching last 5 hourly candles...")
        ohlcv = await client.get_ohlcv("BTC/USDT", "1h", limit=5)
        print("   Timestamp           | Open       | High       | Low        | Close      | Volume")
        print("   " + "-" * 85)
        for candle in ohlcv:
            ts, o, h, low, c, vol = candle
            from datetime import datetime

            dt = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M")
            print(
                f"   {dt} | ${o:>9,.2f} | ${h:>9,.2f} | ${low:>9,.2f} | ${c:>9,.2f} | {vol:>10,.2f}"
            )

        print("\n[4] All tests passed! ✓")
        print("=" * 50)

    except Exception as e:
        print(f"\n   ❌ Error: {e}")

    finally:
        await client.disconnect()
        print("\nDisconnected.")


if __name__ == "__main__":
    asyncio.run(main())
