"""Integration tests for trailing stop in TradingEngine."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from keryxflow.aegis.trailing import TrailingStopManager
from keryxflow.core.events import Event, EventBus, EventType


@pytest.fixture
def event_bus() -> EventBus:
    """Fresh event bus."""
    return EventBus()


@pytest.fixture
def trailing_manager() -> TrailingStopManager:
    """Fresh trailing stop manager."""
    return TrailingStopManager()


@pytest.fixture
def mock_paper_engine() -> AsyncMock:
    """Mock paper trading engine."""
    engine = AsyncMock()
    engine.get_balance = AsyncMock(
        return_value={
            "total": {"USDT": 10000.0},
            "free": {"USDT": 9000.0},
        }
    )
    engine.get_positions = AsyncMock(return_value=[])
    engine.close_position = AsyncMock(
        return_value={
            "symbol": "BTC/USDT",
            "side": "buy",
            "quantity": 0.1,
            "entry_price": 50000.0,
            "exit_price": 50960.0,
            "pnl": 96.0,
            "pnl_percentage": 1.92,
        }
    )
    engine.close_all_positions = AsyncMock(return_value=[])
    return engine


@pytest.fixture
def mock_exchange() -> AsyncMock:
    """Mock exchange client."""
    exchange = AsyncMock()
    exchange.get_ohlcv = AsyncMock(return_value=[])
    return exchange


@pytest.fixture
def mock_risk_manager() -> MagicMock:
    """Mock risk manager."""
    risk = MagicMock()
    risk.update_balance = MagicMock()
    risk.set_open_positions = MagicMock()
    risk.is_circuit_breaker_active = False
    return risk


class TestEngineTrailingStopIntegration:
    """Integration tests for trailing stop in TradingEngine price loop."""

    @pytest.mark.asyncio
    async def test_trailing_stop_closes_position_on_trigger(
        self,
        event_bus: EventBus,
        mock_paper_engine: AsyncMock,
        mock_exchange: AsyncMock,
        mock_risk_manager: MagicMock,
    ) -> None:
        """Full flow: price update → trailing stop triggers → position closed."""
        from keryxflow.core.engine import TradingEngine

        with patch("keryxflow.core.engine.get_trailing_stop_manager") as mock_get_tsm:
            tsm = TrailingStopManager()
            mock_get_tsm.return_value = tsm

            engine = TradingEngine(
                exchange_client=mock_exchange,
                paper_engine=mock_paper_engine,
                event_bus=event_bus,
                risk_manager=mock_risk_manager,
            )

            await engine.start()

            # Simulate POSITION_OPENED event
            await event_bus.publish_sync(
                Event(
                    type=EventType.POSITION_OPENED,
                    data={
                        "symbol": "BTC/USDT",
                        "side": "buy",
                        "entry_price": 50000.0,
                    },
                )
            )

            assert tsm.is_tracking("BTC/USDT")

            # Simulate price rising to activate trailing (>1% up from 50000)
            await event_bus.publish_sync(
                Event(
                    type=EventType.PRICE_UPDATE,
                    data={"symbol": "BTC/USDT", "price": 52000.0},
                )
            )

            # Check trailing stop is active
            assert tsm.get_stop_price("BTC/USDT") is not None
            stop = tsm.get_stop_price("BTC/USDT")
            assert stop == pytest.approx(52000.0 * 0.98)

            # Simulate price dropping to trigger stop (50960.0 = 52000 * 0.98)
            await event_bus.publish_sync(
                Event(
                    type=EventType.PRICE_UPDATE,
                    data={"symbol": "BTC/USDT", "price": 50960.0},
                )
            )

            # Position should have been closed
            mock_paper_engine.close_position.assert_called_once_with("BTC/USDT", 50960.0)

            # Tracking should have stopped
            assert not tsm.is_tracking("BTC/USDT")

            await engine.stop()

    @pytest.mark.asyncio
    async def test_position_closed_event_stops_tracking(
        self,
        event_bus: EventBus,
        mock_paper_engine: AsyncMock,
        mock_exchange: AsyncMock,
        mock_risk_manager: MagicMock,
    ) -> None:
        """POSITION_CLOSED event should stop trailing stop tracking."""
        from keryxflow.core.engine import TradingEngine

        with patch("keryxflow.core.engine.get_trailing_stop_manager") as mock_get_tsm:
            tsm = TrailingStopManager()
            mock_get_tsm.return_value = tsm

            engine = TradingEngine(
                exchange_client=mock_exchange,
                paper_engine=mock_paper_engine,
                event_bus=event_bus,
                risk_manager=mock_risk_manager,
            )

            await engine.start()

            # Start tracking
            await event_bus.publish_sync(
                Event(
                    type=EventType.POSITION_OPENED,
                    data={"symbol": "BTC/USDT", "side": "buy", "entry_price": 50000.0},
                )
            )
            assert tsm.is_tracking("BTC/USDT")

            # Close position externally
            await event_bus.publish_sync(
                Event(
                    type=EventType.POSITION_CLOSED,
                    data={"symbol": "BTC/USDT"},
                )
            )
            assert not tsm.is_tracking("BTC/USDT")

            await engine.stop()

    @pytest.mark.asyncio
    async def test_panic_clears_all_trailing_stops(
        self,
        event_bus: EventBus,
        mock_paper_engine: AsyncMock,
        mock_exchange: AsyncMock,
        mock_risk_manager: MagicMock,
    ) -> None:
        """PANIC event should clear all trailing stops."""
        from keryxflow.core.engine import TradingEngine

        with patch("keryxflow.core.engine.get_trailing_stop_manager") as mock_get_tsm:
            tsm = TrailingStopManager()
            mock_get_tsm.return_value = tsm

            engine = TradingEngine(
                exchange_client=mock_exchange,
                paper_engine=mock_paper_engine,
                event_bus=event_bus,
                risk_manager=mock_risk_manager,
            )

            await engine.start()

            # Start tracking multiple symbols
            await event_bus.publish_sync(
                Event(
                    type=EventType.POSITION_OPENED,
                    data={"symbol": "BTC/USDT", "side": "buy", "entry_price": 50000.0},
                )
            )
            await event_bus.publish_sync(
                Event(
                    type=EventType.POSITION_OPENED,
                    data={"symbol": "ETH/USDT", "side": "sell", "entry_price": 3000.0},
                )
            )

            assert len(tsm.get_all_states()) == 2

            # Trigger panic
            await event_bus.publish_sync(
                Event(
                    type=EventType.PANIC_TRIGGERED,
                    data={},
                )
            )

            assert len(tsm.get_all_states()) == 0

            await engine.stop()

    @pytest.mark.asyncio
    async def test_no_trailing_when_paused(
        self,
        event_bus: EventBus,
        mock_paper_engine: AsyncMock,
        mock_exchange: AsyncMock,
        mock_risk_manager: MagicMock,
    ) -> None:
        """Price updates should be ignored when engine is paused."""
        from keryxflow.core.engine import TradingEngine

        with patch("keryxflow.core.engine.get_trailing_stop_manager") as mock_get_tsm:
            tsm = TrailingStopManager()
            mock_get_tsm.return_value = tsm

            engine = TradingEngine(
                exchange_client=mock_exchange,
                paper_engine=mock_paper_engine,
                event_bus=event_bus,
                risk_manager=mock_risk_manager,
            )

            await engine.start()

            # Start tracking
            await event_bus.publish_sync(
                Event(
                    type=EventType.POSITION_OPENED,
                    data={"symbol": "BTC/USDT", "side": "buy", "entry_price": 50000.0},
                )
            )

            # Pause engine
            await event_bus.publish_sync(
                Event(
                    type=EventType.SYSTEM_PAUSED,
                    data={},
                )
            )

            # Price update should be ignored
            await event_bus.publish_sync(
                Event(
                    type=EventType.PRICE_UPDATE,
                    data={"symbol": "BTC/USDT", "price": 52000.0},
                )
            )

            # Trailing stop should NOT be activated since price update was skipped
            assert tsm.get_stop_price("BTC/USDT") is None

            await engine.stop()
