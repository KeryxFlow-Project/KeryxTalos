"""Trading engine that orchestrates the full trading loop."""

from collections import defaultdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pandas as pd

from keryxflow.aegis.risk import (
    ApprovalResult,
    OrderRequest,
    RiskManager,
    get_risk_manager,
)
from keryxflow.config import get_settings
from keryxflow.core.events import Event, EventBus, EventType, get_event_bus
from keryxflow.core.logging import get_logger
from keryxflow.core.models import RiskProfile
from keryxflow.core.safeguards import LiveTradingSafeguards
from keryxflow.exchange.client import ExchangeClient
from keryxflow.exchange.paper import PaperTradingEngine
from keryxflow.oracle.mtf_signals import get_mtf_signal_generator
from keryxflow.oracle.signals import (
    SignalGenerator,
    SignalType,
    TradingSignal,
    get_signal_generator,
)

if TYPE_CHECKING:
    from keryxflow.notifications.manager import NotificationManager

logger = get_logger(__name__)


class OHLCVBuffer:
    """Buffer to accumulate price updates into OHLCV candles."""

    def __init__(self, max_candles: int = 100):
        """Initialize the buffer."""
        self.max_candles = max_candles
        self._candles: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._current_candle: dict[str, dict[str, Any]] = {}
        self._last_candle_time: dict[str, datetime] = {}
        self._candle_interval = 60  # 1 minute candles

    def add_price(self, symbol: str, price: float, volume: float = 0.0) -> bool:
        """
        Add a price update to the buffer.

        Returns True if a new candle was completed.
        """
        now = datetime.now(UTC)
        candle_time = now.replace(second=0, microsecond=0)

        # Check if we need to start a new candle
        if symbol not in self._current_candle or self._last_candle_time.get(symbol) != candle_time:
            # Save previous candle if exists
            if symbol in self._current_candle and self._current_candle[symbol]:
                self._candles[symbol].append(self._current_candle[symbol])
                # Keep only max_candles
                if len(self._candles[symbol]) > self.max_candles:
                    self._candles[symbol] = self._candles[symbol][-self.max_candles :]

            # Start new candle
            self._current_candle[symbol] = {
                "timestamp": candle_time,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume,
            }
            self._last_candle_time[symbol] = candle_time
            return len(self._candles[symbol]) > 0  # New candle completed

        # Update current candle
        candle = self._current_candle[symbol]
        candle["high"] = max(candle["high"], price)
        candle["low"] = min(candle["low"], price)
        candle["close"] = price
        candle["volume"] += volume

        return False

    def get_ohlcv(self, symbol: str) -> pd.DataFrame | None:
        """Get OHLCV DataFrame for a symbol."""
        candles = self._candles.get(symbol, [])

        # Include current candle
        all_candles = candles.copy()
        if symbol in self._current_candle:
            all_candles.append(self._current_candle[symbol])

        if not all_candles:
            return None

        df = pd.DataFrame(all_candles)
        df = df.rename(
            columns={
                "timestamp": "datetime",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "volume",
            }
        )
        return df

    def candle_count(self, symbol: str) -> int:
        """Get number of completed candles for a symbol."""
        return len(self._candles.get(symbol, []))

    def add_candle(
        self,
        symbol: str,
        timestamp: int | float,
        open_price: float,
        high: float,
        low: float,
        close: float,
        volume: float,
    ) -> None:
        """Add a historical candle directly to the buffer."""
        # Convert timestamp (ms) to datetime
        if isinstance(timestamp, int | float):
            candle_time = datetime.fromtimestamp(timestamp / 1000, tz=UTC)
        else:
            candle_time = timestamp

        candle = {
            "timestamp": candle_time,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }

        self._candles[symbol].append(candle)

        # Keep only max_candles
        if len(self._candles[symbol]) > self.max_candles:
            self._candles[symbol] = self._candles[symbol][-self.max_candles :]


class TradingEngine:
    """
    Orchestrates the full trading loop.

    Flow:
    1. Price updates come in
    2. OHLCV buffer accumulates candles
    3. At intervals, Oracle analyzes and generates signals
    4. Signals go to Aegis for approval
    5. Approved signals become orders
    6. Orders execute via PaperEngine
    """

    def __init__(
        self,
        exchange_client: ExchangeClient,
        paper_engine: PaperTradingEngine,
        event_bus: EventBus | None = None,
        signal_generator: SignalGenerator | None = None,
        risk_manager: RiskManager | None = None,
        notification_manager: "NotificationManager | None" = None,
    ):
        """Initialize the trading engine."""
        self.settings = get_settings()
        self.exchange = exchange_client
        self.paper = paper_engine
        self.event_bus = event_bus or get_event_bus()
        self.risk = risk_manager or get_risk_manager(
            risk_profile=RiskProfile.CONSERVATIVE,
            initial_balance=10000.0,
        )
        self.notifications = notification_manager

        # Safeguards for live trading
        self._safeguards = LiveTradingSafeguards(self.settings)

        # Multi-Timeframe Analysis support
        self._mtf_enabled = self.settings.oracle.mtf.enabled
        if self._mtf_enabled:
            from keryxflow.core.mtf_buffer import create_mtf_buffer_from_settings

            self._mtf_buffer = create_mtf_buffer_from_settings()
            self.signals = signal_generator or get_mtf_signal_generator()
            self._ohlcv_buffer = None  # Not used in MTF mode
        else:
            self._mtf_buffer = None
            self.signals = signal_generator or get_signal_generator()
            self._ohlcv_buffer = OHLCVBuffer(max_candles=100)

        # State
        self._running = False
        self._last_analysis: dict[str, datetime] = {}
        self._analysis_interval = 10  # Seconds between analyses (reduced for testing)
        self._min_candles = 20  # Minimum candles for analysis
        self._auto_trade = True  # Execute orders automatically
        self._paused = False
        self._is_live_mode = not self.settings.is_paper_mode
        self._last_balance_sync: datetime | None = None
        self._balance_sync_interval = self.settings.live.sync_interval

    async def start(self) -> None:
        """Start the trading engine."""
        if self._running:
            return

        # Verify safeguards for live mode
        if self._is_live_mode:
            safeguard_result = await self._verify_live_mode_safe()
            if not safeguard_result:
                logger.error("live_mode_safeguards_failed")
                raise RuntimeError("Live trading safeguards failed. Check logs for details.")

        self._running = True

        # Subscribe to events
        self.event_bus.subscribe(EventType.PRICE_UPDATE, self._on_price_update)
        self.event_bus.subscribe(EventType.SYSTEM_PAUSED, self._on_pause)
        self.event_bus.subscribe(EventType.SYSTEM_RESUMED, self._on_resume)
        self.event_bus.subscribe(EventType.PANIC_TRIGGERED, self._on_panic)

        # Setup notification manager
        if self.notifications:
            self.notifications.subscribe_to_events()

        # Get balance from appropriate source
        if self._is_live_mode:
            balance = await self._sync_balance_from_exchange()
            usdt_balance = balance.get("USDT", 0.0)
        else:
            balance = await self.paper.get_balance()
            usdt_balance = balance["total"].get("USDT", 10000.0)

        self.risk.update_balance(usdt_balance)

        # Update open positions count
        positions = await self.paper.get_positions()
        self.risk.set_open_positions(len(positions))

        # Pre-load historical OHLCV data for faster signal generation
        await self._preload_ohlcv()

        # Run initial analysis for all symbols
        await self._initial_analysis()

        mode = "live" if self._is_live_mode else "paper"
        logger.info("trading_engine_started", mode=mode)

        # Send startup notification
        if self.notifications:
            await self.notifications.notify_system_start(
                mode=mode,
                symbols=self.settings.system.symbols,
            )

    async def _preload_ohlcv(self) -> None:
        """Pre-load historical OHLCV data for all symbols."""

        symbols = self.settings.system.symbols
        candles_to_load = 60  # Need at least 50 for technical analysis

        if self._mtf_enabled:
            await self._preload_mtf_ohlcv(symbols, candles_to_load)
        else:
            await self._preload_single_tf_ohlcv(symbols, candles_to_load)

    async def _preload_single_tf_ohlcv(self, symbols: list[str], candles_to_load: int) -> None:
        """Pre-load single timeframe OHLCV data."""
        import asyncio

        import ccxt

        for symbol in symbols:
            try:
                logger.info("preloading_ohlcv", symbol=symbol, candles=candles_to_load)

                def fetch_ohlcv_sync(sym=symbol):
                    client = ccxt.binance({"enableRateLimit": True})
                    return client.fetch_ohlcv(sym, "1m", limit=candles_to_load)

                ohlcv = await asyncio.to_thread(fetch_ohlcv_sync)

                if ohlcv:
                    for candle in ohlcv:
                        timestamp, open_p, high, low, close, volume = candle
                        self._ohlcv_buffer.add_candle(
                            symbol=symbol,
                            timestamp=timestamp,
                            open_price=open_p,
                            high=high,
                            low=low,
                            close=close,
                            volume=volume or 0.0,
                        )

                    logger.info(
                        "ohlcv_preloaded",
                        symbol=symbol,
                        candles=self._ohlcv_buffer.candle_count(symbol),
                    )
            except Exception as e:
                logger.warning("ohlcv_preload_failed", symbol=symbol, error=str(e))

    async def _preload_mtf_ohlcv(self, symbols: list[str], candles_to_load: int) -> None:
        """Pre-load multi-timeframe OHLCV data."""
        import asyncio

        import ccxt

        timeframes = self.settings.oracle.mtf.timeframes

        for symbol in symbols:
            for tf in timeframes:
                try:
                    logger.info(
                        "preloading_mtf_ohlcv",
                        symbol=symbol,
                        timeframe=tf,
                        candles=candles_to_load,
                    )

                    def fetch_ohlcv_sync(sym=symbol, timeframe=tf):
                        client = ccxt.binance({"enableRateLimit": True})
                        return client.fetch_ohlcv(sym, timeframe, limit=candles_to_load)

                    ohlcv = await asyncio.to_thread(fetch_ohlcv_sync)

                    if ohlcv:
                        for candle in ohlcv:
                            timestamp, open_p, high, low, close, volume = candle
                            self._mtf_buffer.add_candle(
                                symbol=symbol,
                                timeframe=tf,
                                timestamp=timestamp,
                                open_price=open_p,
                                high=high,
                                low=low,
                                close=close,
                                volume=volume or 0.0,
                            )

                        logger.info(
                            "mtf_ohlcv_preloaded",
                            symbol=symbol,
                            timeframe=tf,
                            candles=self._mtf_buffer.candle_count(symbol, tf),
                        )
                except Exception as e:
                    logger.warning(
                        "mtf_ohlcv_preload_failed",
                        symbol=symbol,
                        timeframe=tf,
                        error=str(e),
                    )

    async def _initial_analysis(self) -> None:
        """Run initial analysis for all symbols after OHLCV preload."""
        symbols = self.settings.system.symbols

        for symbol in symbols:
            try:
                if self._mtf_enabled:
                    # Get primary timeframe data for price
                    primary_tf = self.settings.oracle.mtf.primary_timeframe
                    ohlcv = self._mtf_buffer.get_ohlcv(symbol, primary_tf)
                else:
                    ohlcv = self._ohlcv_buffer.get_ohlcv(symbol)

                if ohlcv is not None and len(ohlcv) >= self._min_candles:
                    current_price = ohlcv["close"].iloc[-1]
                    logger.info("running_initial_analysis", symbol=symbol, price=current_price)
                    await self._analyze_symbol(symbol, current_price)
            except Exception as e:
                logger.warning("initial_analysis_failed", symbol=symbol, error=str(e))

    async def stop(self) -> None:
        """Stop the trading engine."""
        if not self._running:
            return

        self._running = False

        # Unsubscribe from events
        self.event_bus.unsubscribe(EventType.PRICE_UPDATE, self._on_price_update)
        self.event_bus.unsubscribe(EventType.SYSTEM_PAUSED, self._on_pause)
        self.event_bus.unsubscribe(EventType.SYSTEM_RESUMED, self._on_resume)
        self.event_bus.unsubscribe(EventType.PANIC_TRIGGERED, self._on_panic)

        logger.info("trading_engine_stopped")

    async def _on_price_update(self, event: Event) -> None:
        """Handle price update events."""
        if self._paused:
            return

        symbol = event.data.get("symbol")
        price = event.data.get("price")
        volume = event.data.get("volume", 0.0)

        if not symbol or not price:
            return

        # Add to appropriate buffer
        if self._mtf_enabled:
            # MTF buffer updates all timeframes
            candle_completions = self._mtf_buffer.add_price(symbol, price, volume or 0.0)
            # Check if any timeframe completed a candle
            new_candle = any(candle_completions.values())
        else:
            new_candle = self._ohlcv_buffer.add_price(symbol, price, volume or 0.0)

        # Check if we should analyze
        if self._should_analyze(symbol, new_candle):
            await self._analyze_symbol(symbol, price)

    def _should_analyze(self, symbol: str, new_candle: bool) -> bool:
        """Check if we should run analysis for a symbol."""
        # Need minimum candles
        if self._mtf_enabled:
            # Check primary timeframe
            primary_tf = self.settings.oracle.mtf.primary_timeframe
            candle_count = self._mtf_buffer.candle_count(symbol, primary_tf)
        else:
            candle_count = self._ohlcv_buffer.candle_count(symbol)

        if candle_count < self._min_candles:
            logger.debug(
                "skip_analysis_low_candles",
                symbol=symbol,
                candles=candle_count,
                min=self._min_candles,
            )
            return False

        # Check time since last analysis
        now = datetime.now(UTC)
        last = self._last_analysis.get(symbol)

        if last is None:
            logger.debug("should_analyze_first_time", symbol=symbol)
            return True

        elapsed = (now - last).total_seconds()
        return elapsed >= self._analysis_interval or new_candle

    async def _analyze_symbol(self, symbol: str, current_price: float) -> None:
        """Run analysis and generate signal for a symbol."""
        self._last_analysis[symbol] = datetime.now(UTC)

        # Get OHLCV data (single TF or MTF dict)
        if self._mtf_enabled:
            ohlcv = self._mtf_buffer.get_all_ohlcv(symbol)
            # Check if we have enough data in primary timeframe
            primary_tf = self.settings.oracle.mtf.primary_timeframe
            primary_df = ohlcv.get(primary_tf)
            if primary_df is None or len(primary_df) < self._min_candles:
                return
        else:
            ohlcv = self._ohlcv_buffer.get_ohlcv(symbol)
            if ohlcv is None or len(ohlcv) < self._min_candles:
                return

        try:
            # Generate signal (without LLM for now - faster)
            signal = await self.signals.generate_signal(
                symbol=symbol,
                ohlcv=ohlcv,
                current_price=current_price,
                include_news=False,  # Disable news for speed
                include_llm=False,  # Disable LLM for speed
            )

            # Publish signal event
            await self.event_bus.publish(
                Event(
                    type=EventType.SIGNAL_GENERATED,
                    data=signal.to_dict(),
                )
            )

            logger.info(
                "signal_generated",
                symbol=symbol,
                type=signal.signal_type.value,
                confidence=f"{signal.confidence:.2f}",
            )

            # Process actionable signals
            if signal.is_actionable and self._auto_trade:
                await self._process_signal(signal)

        except Exception as e:
            logger.error("analysis_failed", symbol=symbol, error=str(e))

    async def _process_signal(self, signal: TradingSignal) -> None:
        """Process an actionable signal through Aegis and execute if approved."""
        # Skip if no entry price
        if not signal.entry_price:
            return

        # Determine order side
        if signal.signal_type == SignalType.LONG:
            side = "buy"
        elif signal.signal_type == SignalType.SHORT:
            side = "sell"
        else:
            return  # Not an entry signal

        # Get current balance for position sizing
        balance = await self.paper.get_balance()
        usdt_balance = balance["free"].get("USDT", 0.0)

        # Calculate position size
        if not signal.stop_loss:
            logger.warning("signal_missing_stop_loss", symbol=signal.symbol)
            return

        quantity = self.risk.calculate_safe_position_size(
            symbol=signal.symbol,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            balance=usdt_balance,
        )

        if quantity <= 0:
            logger.warning("position_size_zero", symbol=signal.symbol)
            return

        # Create order request
        order_request = OrderRequest(
            symbol=signal.symbol,
            side=side,
            quantity=quantity,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
        )

        # Get approval from Aegis
        approval = self.risk.approve_order(order_request, usdt_balance)

        if approval.approved:
            await self._execute_order(order_request, signal, approval)
        else:
            await self._handle_rejection(order_request, signal, approval)

    async def _execute_order(
        self,
        order: OrderRequest,
        _signal: TradingSignal,
        approval: ApprovalResult,
    ) -> None:
        """Execute an approved order."""
        # Publish approval event
        await self.event_bus.publish(
            Event(
                type=EventType.ORDER_APPROVED,
                data={
                    "symbol": order.symbol,
                    "side": order.side,
                    "quantity": order.quantity,
                    "price": order.entry_price,
                    "message": approval.simple_message,
                },
            )
        )

        try:
            # Execute via appropriate engine
            if self._is_live_mode:
                result = await self._execute_live_order(order)
            else:
                result = await self.paper.execute_order(
                    symbol=order.symbol,
                    side=order.side,
                    quantity=order.quantity,
                    price=order.entry_price,
                )

            if result:
                fill_price = result.get("price", order.entry_price)

                # Publish fill event
                await self.event_bus.publish(
                    Event(
                        type=EventType.ORDER_FILLED,
                        data={
                            "symbol": order.symbol,
                            "side": order.side,
                            "quantity": order.quantity,
                            "price": fill_price,
                            "order_id": result.get("id"),
                            "is_live": self._is_live_mode,
                        },
                    )
                )

                # Update risk manager state
                if self._is_live_mode:
                    await self._sync_balance_from_exchange()
                else:
                    positions = await self.paper.get_positions()
                    self.risk.set_open_positions(len(positions))
                    balance = await self.paper.get_balance()
                    self.risk.update_balance(balance["total"].get("USDT", 0.0))

                logger.info(
                    "order_executed",
                    symbol=order.symbol,
                    side=order.side,
                    quantity=order.quantity,
                    is_live=self._is_live_mode,
                )

        except Exception as e:
            logger.error("order_execution_failed", symbol=order.symbol, error=str(e))

            # Notify about execution error in live mode
            if self._is_live_mode and self.notifications:
                await self.notifications.notify_system_error(
                    error=str(e),
                    component="OrderExecution",
                )

    async def _execute_live_order(self, order: OrderRequest) -> dict[str, Any] | None:
        """Execute an order on the live exchange.

        Args:
            order: The order request to execute

        Returns:
            Order result dict or None if failed
        """
        try:
            # Apply slippage protection for market orders
            # Use market order for simplicity - limit orders would need monitoring
            result = await self.exchange.create_market_order(
                symbol=order.symbol,
                side=order.side,
                amount=order.quantity,
            )

            if result:
                logger.info(
                    "live_order_executed",
                    order_id=result.get("id"),
                    symbol=order.symbol,
                    side=order.side,
                    amount=order.quantity,
                    price=result.get("average") or result.get("price"),
                )

            return result

        except Exception as e:
            logger.error(
                "live_order_failed",
                symbol=order.symbol,
                side=order.side,
                error=str(e),
            )
            raise

    async def _handle_rejection(
        self,
        order: OrderRequest,
        _signal: TradingSignal,
        approval: ApprovalResult,
    ) -> None:
        """Handle a rejected order."""
        await self.event_bus.publish(
            Event(
                type=EventType.ORDER_REJECTED,
                data={
                    "symbol": order.symbol,
                    "side": order.side,
                    "quantity": order.quantity,
                    "price": order.entry_price,
                    "reason": approval.reason.value if approval.reason else "unknown",
                    "message": approval.simple_message,
                },
            )
        )

        logger.info(
            "order_rejected",
            symbol=order.symbol,
            reason=approval.reason.value if approval.reason else "unknown",
        )

    async def _on_pause(self, _event: Event) -> None:
        """Handle pause event."""
        self._paused = True
        logger.info("trading_paused")

    async def _on_resume(self, _event: Event) -> None:
        """Handle resume event."""
        self._paused = False
        logger.info("trading_resumed")

    async def _on_panic(self, _event: Event) -> None:
        """Handle panic event - close all positions."""
        self._paused = True
        logger.warning("panic_triggered")

        try:
            await self.paper.close_all_positions()

            # Update state
            self.risk.set_open_positions(0)
            balance = await self.paper.get_balance()
            self.risk.update_balance(balance["total"].get("USDT", 0.0))

            await self.event_bus.publish(
                Event(
                    type=EventType.POSITION_CLOSED,
                    data={"message": "All positions closed (PANIC)"},
                )
            )

        except Exception as e:
            logger.error("panic_close_failed", error=str(e))

    async def _verify_live_mode_safe(self) -> bool:
        """Verify that live trading mode is safe to enable.

        Returns:
            True if all safeguards pass, False otherwise
        """
        try:
            # Get current exchange balance
            balance = await self.exchange.get_balance()
            usdt_balance = balance.get("free", {}).get("USDT", 0.0)

            # Get paper trade count (would come from database in real implementation)
            # For now, we'll use a placeholder - this should be fetched from DB
            paper_trade_count = 0  # TODO: Fetch from database

            # Check circuit breaker status
            circuit_breaker_active = self.risk.is_circuit_breaker_active

            # Run safeguard checks
            result = await self._safeguards.verify_ready_for_live(
                current_balance=usdt_balance,
                paper_trade_count=paper_trade_count,
                circuit_breaker_active=circuit_breaker_active,
            )

            if not result.passed:
                logger.warning(
                    "live_safeguards_failed",
                    errors=[c.message for c in result.errors],
                    warnings=[c.message for c in result.warnings],
                )

                # Notify about safeguard failure
                if self.notifications:
                    await self.notifications.notify_system_error(
                        error=result.summary(),
                        component="LiveTradingSafeguards",
                    )

            return result.passed

        except Exception as e:
            logger.error("safeguard_check_failed", error=str(e))
            return False

    async def _sync_balance_from_exchange(self) -> dict[str, float]:
        """Sync balance from the exchange.

        Returns:
            Dict with currency balances
        """
        try:
            balance = await self.exchange.get_balance()
            self._last_balance_sync = datetime.now(UTC)

            # Extract free balances
            free_balance = balance.get("free", {})

            logger.debug(
                "balance_synced",
                usdt=free_balance.get("USDT", 0.0),
            )

            return free_balance

        except Exception as e:
            logger.error("balance_sync_failed", error=str(e))
            return {}

    async def _maybe_sync_balance(self) -> None:
        """Sync balance from exchange if enough time has passed."""
        if not self._is_live_mode:
            return

        now = datetime.now(UTC)
        if self._last_balance_sync is None:
            await self._sync_balance_from_exchange()
            return

        elapsed = (now - self._last_balance_sync).total_seconds()
        if elapsed >= self._balance_sync_interval:
            balance = await self._sync_balance_from_exchange()
            usdt_balance = balance.get("USDT", 0.0)
            self.risk.update_balance(usdt_balance)

    def get_status(self) -> dict[str, Any]:
        """Get current engine status."""
        if self._mtf_enabled:
            symbols_tracking = list(self._mtf_buffer._buffers.keys())
        else:
            symbols_tracking = list(self._ohlcv_buffer._candles.keys())

        status = {
            "running": self._running,
            "paused": self._paused,
            "auto_trade": self._auto_trade,
            "mode": "live" if self._is_live_mode else "paper",
            "analysis_interval": self._analysis_interval,
            "min_candles": self._min_candles,
            "symbols_tracking": symbols_tracking,
            "risk_status": self.risk.get_status(),
            "last_balance_sync": self._last_balance_sync.isoformat()
            if self._last_balance_sync
            else None,
            "mtf_enabled": self._mtf_enabled,
        }

        if self._mtf_enabled:
            status["mtf_timeframes"] = self.settings.oracle.mtf.timeframes
            status["mtf_primary_timeframe"] = self.settings.oracle.mtf.primary_timeframe
            status["mtf_filter_timeframe"] = self.settings.oracle.mtf.filter_timeframe

        return status


# Global instance
_engine: TradingEngine | None = None


def get_trading_engine(
    exchange_client: ExchangeClient | None = None,
    paper_engine: PaperTradingEngine | None = None,
) -> TradingEngine:
    """Get the global trading engine instance."""
    global _engine
    if _engine is None:
        if exchange_client is None or paper_engine is None:
            raise ValueError("Must provide exchange_client and paper_engine on first call")
        _engine = TradingEngine(exchange_client, paper_engine)
    return _engine
