"""Trading engine that orchestrates the full trading loop."""

import asyncio
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
from keryxflow.aegis.trailing import get_trailing_stop_manager
from keryxflow.config import get_settings
from keryxflow.core.events import Event, EventBus, EventType, get_event_bus
from keryxflow.core.logging import get_logger
from keryxflow.core.models import RiskProfile, TradeOutcome
from keryxflow.core.repository import get_trade_repository
from keryxflow.core.safeguards import LiveTradingSafeguards
from keryxflow.exchange.client import ExchangeClient
from keryxflow.exchange.paper import PaperTradingEngine
from keryxflow.memory.manager import MemoryManager, get_memory_manager
from keryxflow.oracle.mtf_signals import get_mtf_signal_generator
from keryxflow.oracle.signals import (
    SignalGenerator,
    SignalType,
    TradingSignal,
    get_signal_generator,
)

if TYPE_CHECKING:
    from keryxflow.agent.cognitive import CognitiveAgent
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
        memory_manager: MemoryManager | None = None,
        cognitive_agent: "CognitiveAgent | None" = None,
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
        self.memory = memory_manager or get_memory_manager()

        # Track episode IDs by trade/order for later update
        self._episode_by_order: dict[str, int] = {}

        # Safeguards for live trading
        self._safeguards = LiveTradingSafeguards(self.settings)

        # Agent mode support
        self._agent_mode = self.settings.agent.enabled
        self._cognitive_agent = cognitive_agent
        if self._agent_mode and self._cognitive_agent is None:
            from keryxflow.agent.cognitive import get_cognitive_agent

            self._cognitive_agent = get_cognitive_agent()

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

        # Trailing stop manager
        self._trailing_enabled = self.settings.risk.trailing_stop_enabled
        self._trailing_manager = get_trailing_stop_manager() if self._trailing_enabled else None

        # API server (managed lifecycle)
        self._api_server: Any = None
        self._api_task: asyncio.Task | None = None

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
        self._last_agent_cycle: datetime | None = None
        self._preload_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the trading engine."""
        if self._running:
            return

        # Verify safeguards for live mode
        if self._is_live_mode:
            logger.info("verifying_live_mode_safeguards")
            try:
                safeguard_result = await self._verify_live_mode_safe()
                if not safeguard_result:
                    logger.warning("live_mode_safeguards_failed_continuing_anyway")
                    # Continue anyway for now - user is testing
            except Exception as e:
                logger.warning("live_safeguard_check_error", error=str(e))
                # Continue anyway - don't block startup

        self._running = True

        # Subscribe to events
        self.event_bus.subscribe(EventType.PRICE_UPDATE, self._on_price_update)
        self.event_bus.subscribe(EventType.SYSTEM_PAUSED, self._on_pause)
        self.event_bus.subscribe(EventType.SYSTEM_RESUMED, self._on_resume)
        self.event_bus.subscribe(EventType.PANIC_TRIGGERED, self._on_panic)

        # Subscribe to position events for trailing stop
        if self._trailing_enabled:
            self.event_bus.subscribe(EventType.POSITION_OPENED, self._on_position_opened)
            self.event_bus.subscribe(EventType.POSITION_CLOSED, self._on_position_closed)

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

        # Pre-load historical OHLCV data in background (non-blocking)
        # This allows TUI to start immediately while data loads
        self._preload_task = asyncio.create_task(self._background_preload())

        mode = "live" if self._is_live_mode else "paper"
        logger.info("trading_engine_started", mode=mode)

        # Start API server if enabled
        if self.settings.api.enabled:
            try:
                from keryxflow.api.server import start_api_server

                self._api_server, self._api_task = await start_api_server(
                    host=self.settings.api.host,
                    port=self.settings.api.port,
                )
            except Exception as e:
                logger.error("api_server_start_failed", error=str(e))
                # Don't crash the engine — trading continues without API
                self._api_server = None
                self._api_task = None

        # Send startup notification
        if self.notifications:
            await self.notifications.notify_system_start(
                mode=mode,
                symbols=self.settings.system.symbols,
            )

    async def _background_preload(self) -> None:
        """Background task for preloading OHLCV data and running initial analysis.

        This runs in the background so TUI can start immediately.
        """
        try:
            logger.info("background_preload_started")
            await self._preload_ohlcv()
            await self._initial_analysis()
            logger.info("background_preload_completed")
        except Exception as e:
            logger.error("background_preload_failed", error=str(e))

    async def _preload_ohlcv(self) -> None:
        """Pre-load historical OHLCV data for all symbols."""

        symbols = self.settings.system.symbols
        candles_to_load = 60  # Need at least 50 for technical analysis

        if self._mtf_enabled:
            await self._preload_mtf_ohlcv(symbols, candles_to_load)
        else:
            await self._preload_single_tf_ohlcv(symbols, candles_to_load)

    async def _preload_single_tf_ohlcv(self, symbols: list[str], candles_to_load: int) -> None:
        """Pre-load single timeframe OHLCV data (parallel with concurrency limit)."""
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests

        async def load_symbol(symbol: str) -> None:
            async with semaphore:
                try:
                    logger.info("preloading_ohlcv", symbol=symbol, candles=candles_to_load)

                    # Use the main exchange client instead of creating temporary ones
                    ohlcv = await self.exchange.get_ohlcv(
                        symbol=symbol,
                        timeframe="1m",
                        limit=candles_to_load,
                    )

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

        # Load all symbols in parallel
        await asyncio.gather(*[load_symbol(s) for s in symbols])

    async def _preload_mtf_ohlcv(self, symbols: list[str], candles_to_load: int) -> None:
        """Pre-load multi-timeframe OHLCV data (parallel with concurrency limit)."""
        timeframes = self.settings.oracle.mtf.timeframes
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests

        async def load_symbol_tf(symbol: str, tf: str) -> None:
            async with semaphore:
                try:
                    logger.info(
                        "preloading_mtf_ohlcv",
                        symbol=symbol,
                        timeframe=tf,
                        candles=candles_to_load,
                    )

                    # Use the main exchange client instead of creating temporary ones
                    ohlcv = await self.exchange.get_ohlcv(
                        symbol=symbol,
                        timeframe=tf,
                        limit=candles_to_load,
                    )

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

        # Load all symbol/timeframe combinations in parallel
        tasks = [load_symbol_tf(s, tf) for s in symbols for tf in timeframes]
        await asyncio.gather(*tasks)

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

        # Cancel background preload task if running
        if self._preload_task and not self._preload_task.done():
            self._preload_task.cancel()

        # Stop API server if running
        if self._api_server is not None:
            try:
                from keryxflow.api.server import stop_api_server

                await stop_api_server()
            except Exception as e:
                logger.error("api_server_stop_failed", error=str(e))
            self._api_server = None
            self._api_task = None

        # Unsubscribe from events
        self.event_bus.unsubscribe(EventType.PRICE_UPDATE, self._on_price_update)
        self.event_bus.unsubscribe(EventType.SYSTEM_PAUSED, self._on_pause)
        self.event_bus.unsubscribe(EventType.SYSTEM_RESUMED, self._on_resume)
        self.event_bus.unsubscribe(EventType.PANIC_TRIGGERED, self._on_panic)

        if self._trailing_enabled:
            self.event_bus.unsubscribe(EventType.POSITION_OPENED, self._on_position_opened)
            self.event_bus.unsubscribe(EventType.POSITION_CLOSED, self._on_position_closed)

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

        # Check trailing stop before anything else (fastest reaction)
        if self._trailing_enabled and self._trailing_manager is not None:
            self._trailing_manager.update_price(symbol, price)
            if self._trailing_manager.should_trigger_stop(symbol, price):
                await self._close_trailing_stop(symbol, price)
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

        # If agent mode is enabled, run agent cycle instead
        if self._agent_mode and self._cognitive_agent is not None:
            await self._run_agent_cycle([symbol])
            return

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

    async def _run_agent_cycle(self, symbols: list[str]) -> None:
        """Run a cognitive agent cycle for the given symbols.

        Args:
            symbols: Symbols to analyze in this cycle
        """
        if self._cognitive_agent is None:
            return

        # Check cycle interval
        now = datetime.now(UTC)
        if self._last_agent_cycle is not None:
            elapsed = (now - self._last_agent_cycle).total_seconds()
            if elapsed < self.settings.agent.cycle_interval:
                return

        self._last_agent_cycle = now

        try:
            # Initialize agent if needed
            if not self._cognitive_agent._initialized:
                await self._cognitive_agent.initialize()

            # Run the cycle
            result = await self._cognitive_agent.run_cycle(symbols)

            logger.info(
                "agent_cycle_completed",
                status=result.status.value,
                decision=result.decision.decision_type.value if result.decision else None,
                duration_ms=result.duration_ms,
            )

            # If agent errored too many times, disable agent mode temporarily
            if (
                self._cognitive_agent._stats.consecutive_errors
                >= self.settings.agent.max_consecutive_errors
            ):
                logger.warning(
                    "agent_mode_disabled_due_to_errors",
                    consecutive_errors=self._cognitive_agent._stats.consecutive_errors,
                )
                # Don't disable permanently, let it retry on next interval

        except Exception as e:
            logger.error("agent_cycle_failed", error=str(e))

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
        signal: TradingSignal,
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
                result = await self.paper.execute_market_order(
                    symbol=order.symbol,
                    side=order.side,
                    amount=order.quantity,
                    price=order.entry_price,
                )

            if result:
                fill_price = result.get("price", order.entry_price)
                order_id = result.get("id", f"{order.symbol}_{datetime.now(UTC).timestamp()}")

                # Publish fill event
                await self.event_bus.publish(
                    Event(
                        type=EventType.ORDER_FILLED,
                        data={
                            "symbol": order.symbol,
                            "side": order.side,
                            "quantity": order.quantity,
                            "price": fill_price,
                            "order_id": order_id,
                            "is_live": self._is_live_mode,
                        },
                    )
                )

                # Record trade episode in memory
                await self._record_trade_episode(order, signal, fill_price, order_id)

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

    async def _record_trade_episode(
        self,
        order: OrderRequest,
        signal: TradingSignal,
        fill_price: float,
        order_id: str,
    ) -> None:
        """Record a new trade episode in memory."""
        try:
            # Build technical context from signal
            technical_context = {
                "confidence": signal.confidence,
                "strength": signal.strength.value if signal.strength else None,
                "entry_price": signal.entry_price,
                "stop_loss": signal.stop_loss,
                "take_profit": signal.take_profit,
            }

            # Build market context
            market_context = {
                "signal_type": signal.signal_type.value,
                "reasoning": signal.reasoning,
            }

            # Get memory context for decision
            memory_context = await self.memory.build_context_for_decision(
                symbol=order.symbol,
                technical_context=technical_context,
            )

            # Generate trade_id (use hash of order_id as int)
            trade_id = hash(order_id) % (10**9)

            # Record the episode
            episode_id = await self.memory.record_trade_entry(
                trade_id=trade_id,
                symbol=order.symbol,
                entry_price=fill_price,
                entry_reasoning=signal.reasoning or f"{signal.signal_type.value} signal",
                entry_confidence=signal.confidence,
                technical_context=technical_context,
                market_context=market_context,
                memory_context=memory_context,
                tags=[order.side, signal.signal_type.value],
            )

            if episode_id:
                self._episode_by_order[order_id] = episode_id
                logger.debug(
                    "trade_episode_recorded",
                    episode_id=episode_id,
                    order_id=order_id,
                    symbol=order.symbol,
                )

        except Exception as e:
            logger.warning("failed_to_record_episode", error=str(e))

    async def record_trade_exit(
        self,
        order_id: str,
        exit_price: float,
        exit_reasoning: str,
        pnl: float,
        pnl_percentage: float,
    ) -> None:
        """Record a trade exit in memory."""
        episode_id = self._episode_by_order.get(order_id)
        if not episode_id:
            return

        try:
            # Determine outcome
            if pnl_percentage > 0:
                outcome = TradeOutcome.WIN
            elif pnl_percentage < -1.5:  # Assume stop loss hit
                outcome = TradeOutcome.STOPPED_OUT
            else:
                outcome = TradeOutcome.LOSS

            await self.memory.record_trade_exit(
                episode_id=episode_id,
                exit_price=exit_price,
                exit_reasoning=exit_reasoning,
                outcome=outcome,
                pnl=pnl,
                pnl_percentage=pnl_percentage,
            )

            # Clean up tracking
            del self._episode_by_order[order_id]

            logger.debug(
                "trade_exit_recorded",
                episode_id=episode_id,
                outcome=outcome.value,
                pnl_percentage=pnl_percentage,
            )

        except Exception as e:
            logger.warning("failed_to_record_exit", error=str(e))

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

    async def _on_position_opened(self, event: Event) -> None:
        """Handle position opened event — start trailing stop tracking."""
        if not self._trailing_enabled or self._trailing_manager is None:
            return

        symbol = event.data.get("symbol")
        side = event.data.get("side")
        entry_price = event.data.get("entry_price") or event.data.get("price")

        if not symbol or not side or not entry_price:
            logger.warning("trailing_stop_missing_position_data", data=event.data)
            return

        self._trailing_manager.start_tracking(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            trail_pct=self.settings.risk.trailing_stop_pct,
            activation_pct=self.settings.risk.trailing_activation_pct,
        )

    async def _on_position_closed(self, event: Event) -> None:
        """Handle position closed event — stop trailing stop tracking."""
        if not self._trailing_enabled or self._trailing_manager is None:
            return

        symbol = event.data.get("symbol")
        if symbol:
            self._trailing_manager.stop_tracking(symbol)

    async def _close_trailing_stop(self, symbol: str, price: float) -> None:
        """Close a position due to trailing stop trigger."""
        logger.warning(
            "trailing_stop_triggered",
            symbol=symbol,
            price=price,
            stop_price=self._trailing_manager.get_stop_price(symbol)
            if self._trailing_manager
            else None,
        )

        # Stop tracking immediately to prevent duplicate triggers
        if self._trailing_manager is not None:
            self._trailing_manager.stop_tracking(symbol)

        try:
            result = await self.paper.close_position(symbol, price)

            if result:
                pnl = result.get("pnl", 0.0)
                pnl_pct = result.get("pnl_percentage", 0.0)

                await self.event_bus.publish(
                    Event(
                        type=EventType.POSITION_CLOSED,
                        data={
                            "symbol": symbol,
                            "exit_price": price,
                            "pnl": pnl,
                            "pnl_percentage": pnl_pct,
                            "reason": "trailing_stop",
                        },
                    )
                )

                # Update risk manager state
                positions = await self.paper.get_positions()
                self.risk.set_open_positions(len(positions))
                balance = await self.paper.get_balance()
                self.risk.update_balance(balance["total"].get("USDT", 0.0))

                # Record trade exit in memory
                order_id = f"{symbol}_{result.get('entry_price', price)}"
                await self.record_trade_exit(
                    order_id=order_id,
                    exit_price=price,
                    exit_reasoning="Trailing stop triggered",
                    pnl=pnl,
                    pnl_percentage=pnl_pct,
                )

                logger.info(
                    "trailing_stop_position_closed",
                    symbol=symbol,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                )

        except Exception as e:
            logger.error("trailing_stop_close_failed", symbol=symbol, error=str(e))

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
            # Stop all trailing stops before closing
            if self._trailing_enabled and self._trailing_manager is not None:
                self._trailing_manager.stop_tracking_all()

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
            # Get current exchange balance using the main client
            balance = await self.exchange.get_balance()
            usdt_balance = balance.get("free", {}).get("USDT", 0.0)

            # Get paper trade count from database
            paper_trade_count = await get_trade_repository().count_paper_trades()

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
            # Use the main exchange client
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
            "agent_mode": self._agent_mode,
        }

        if self._mtf_enabled:
            status["mtf_timeframes"] = self.settings.oracle.mtf.timeframes
            status["mtf_primary_timeframe"] = self.settings.oracle.mtf.primary_timeframe
            status["mtf_filter_timeframe"] = self.settings.oracle.mtf.filter_timeframe

        if self._agent_mode and self._cognitive_agent is not None:
            status["agent_stats"] = self._cognitive_agent.get_stats()
            status["agent_cycle_interval"] = self.settings.agent.cycle_interval
            status["last_agent_cycle"] = (
                self._last_agent_cycle.isoformat() if self._last_agent_cycle else None
            )

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
