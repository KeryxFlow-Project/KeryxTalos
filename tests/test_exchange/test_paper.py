"""Tests for paper trading engine."""

import pytest

from keryxflow.exchange.paper import PaperTradingEngine


@pytest.fixture
async def paper_engine(init_db):
    """Create a fresh paper trading engine for testing."""
    engine = PaperTradingEngine(initial_balance=10000.0, slippage_pct=0.001)
    await engine.initialize()
    return engine


class TestPaperTradingEngine:
    """Tests for PaperTradingEngine."""

    async def test_initialization(self, paper_engine):
        """Test engine initializes with correct balance."""
        balance = await paper_engine.get_balance("USDT")
        assert balance["total"]["USDT"] == 10000.0
        assert balance["free"]["USDT"] == 10000.0
        assert balance["used"]["USDT"] == 0.0

    async def test_update_and_get_price(self, paper_engine):
        """Test price updates."""
        paper_engine.update_price("BTC/USDT", 50000.0)
        assert paper_engine.get_price("BTC/USDT") == 50000.0
        assert paper_engine.get_price("ETH/USDT") is None

    async def test_market_buy_order(self, paper_engine):
        """Test executing a market buy order."""
        paper_engine.update_price("BTC/USDT", 50000.0)

        result = await paper_engine.execute_market_order(
            symbol="BTC/USDT",
            side="buy",
            amount=0.1,
        )

        assert result["symbol"] == "BTC/USDT"
        assert result["side"] == "buy"
        assert result["amount"] == 0.1
        assert result["status"] == "closed"
        # Price should include slippage (0.1% higher for buy)
        assert result["price"] > 50000.0

        # Check balances
        balance = await paper_engine.get_balance()
        assert balance["total"]["BTC"] == 0.1
        assert balance["total"]["USDT"] < 10000.0  # Spent some USDT

    async def test_market_sell_order(self, paper_engine):
        """Test executing a market sell order."""
        paper_engine.update_price("BTC/USDT", 50000.0)

        # First buy some BTC
        await paper_engine.execute_market_order("BTC/USDT", "buy", 0.1)

        # Then sell it
        result = await paper_engine.execute_market_order(
            symbol="BTC/USDT",
            side="sell",
            amount=0.1,
        )

        assert result["side"] == "sell"
        assert result["status"] == "closed"
        # Price should include slippage (0.1% lower for sell)
        assert result["price"] < 50000.0

        # Check BTC balance is zero
        balance = await paper_engine.get_balance()
        assert balance["total"]["BTC"] == 0.0

    async def test_insufficient_balance_buy(self, paper_engine):
        """Test buy order with insufficient balance."""
        paper_engine.update_price("BTC/USDT", 50000.0)

        with pytest.raises(ValueError, match="Insufficient USDT balance"):
            await paper_engine.execute_market_order(
                symbol="BTC/USDT",
                side="buy",
                amount=1.0,  # Would cost 50000+ USDT
            )

    async def test_insufficient_balance_sell(self, paper_engine):
        """Test sell order with insufficient balance."""
        paper_engine.update_price("BTC/USDT", 50000.0)

        with pytest.raises(ValueError, match="Insufficient BTC balance"):
            await paper_engine.execute_market_order(
                symbol="BTC/USDT",
                side="sell",
                amount=0.1,  # Don't have any BTC
            )

    async def test_open_position(self, paper_engine):
        """Test opening a position."""
        paper_engine.update_price("BTC/USDT", 50000.0)

        position = await paper_engine.open_position(
            symbol="BTC/USDT",
            side="buy",
            amount=0.1,
            entry_price=50000.0,
            stop_loss=48000.0,
            take_profit=55000.0,
        )

        assert position.symbol == "BTC/USDT"
        assert position.quantity == 0.1
        assert position.stop_loss == 48000.0
        assert position.take_profit == 55000.0

    async def test_close_position_profit(self, paper_engine):
        """Test closing a position with profit."""
        paper_engine.update_price("BTC/USDT", 50000.0)

        await paper_engine.open_position(
            symbol="BTC/USDT",
            side="buy",
            amount=0.1,
            entry_price=50000.0,
        )

        # Price goes up
        paper_engine.update_price("BTC/USDT", 55000.0)

        result = await paper_engine.close_position("BTC/USDT")

        assert result is not None
        assert result["pnl"] > 0  # Should have profit
        assert result["exit_price"] > result["entry_price"]

    async def test_close_position_loss(self, paper_engine):
        """Test closing a position with loss."""
        paper_engine.update_price("BTC/USDT", 50000.0)

        await paper_engine.open_position(
            symbol="BTC/USDT",
            side="buy",
            amount=0.1,
            entry_price=50000.0,
        )

        # Price goes down
        paper_engine.update_price("BTC/USDT", 45000.0)

        result = await paper_engine.close_position("BTC/USDT")

        assert result is not None
        assert result["pnl"] < 0  # Should have loss

    async def test_get_positions(self, paper_engine):
        """Test getting all positions."""
        paper_engine.update_price("BTC/USDT", 50000.0)
        paper_engine.update_price("ETH/USDT", 3000.0)

        await paper_engine.open_position("BTC/USDT", "buy", 0.1, 50000.0)
        await paper_engine.open_position("ETH/USDT", "buy", 1.0, 3000.0)

        positions = await paper_engine.get_positions()
        assert len(positions) == 2

    async def test_close_all_positions(self, paper_engine):
        """Test panic mode - close all positions."""
        paper_engine.update_price("BTC/USDT", 50000.0)
        paper_engine.update_price("ETH/USDT", 3000.0)

        await paper_engine.open_position("BTC/USDT", "buy", 0.1, 50000.0)
        await paper_engine.open_position("ETH/USDT", "buy", 1.0, 3000.0)

        results = await paper_engine.close_all_positions()

        assert len(results) == 2

        positions = await paper_engine.get_positions()
        assert len(positions) == 0

    async def test_update_position_prices(self, paper_engine):
        """Test updating position prices and PnL."""
        paper_engine.update_price("BTC/USDT", 50000.0)

        await paper_engine.open_position("BTC/USDT", "buy", 0.1, 50000.0)

        # Update price
        paper_engine.update_price("BTC/USDT", 52000.0)
        await paper_engine.update_position_prices()

        position = await paper_engine.get_position("BTC/USDT")
        assert position is not None
        assert position.current_price == 52000.0
        assert position.unrealized_pnl > 0

    async def test_slippage_applied(self, paper_engine):
        """Test that slippage is applied correctly."""
        paper_engine.update_price("BTC/USDT", 50000.0)

        # Buy order - price should be higher
        buy_result = await paper_engine.execute_market_order("BTC/USDT", "buy", 0.1)
        expected_buy_price = 50000.0 * 1.001  # 0.1% slippage
        assert abs(buy_result["price"] - expected_buy_price) < 0.01

        # Sell order - price should be lower
        sell_result = await paper_engine.execute_market_order("BTC/USDT", "sell", 0.1)
        expected_sell_price = 50000.0 * 0.999  # 0.1% slippage
        assert abs(sell_result["price"] - expected_sell_price) < 0.01
