"""Backtesting engine for strategy simulation."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

import pandas as pd

from keryxflow.aegis.quant import QuantEngine, get_quant_engine
from keryxflow.aegis.risk import OrderRequest, RiskManager, get_risk_manager
from keryxflow.config import get_settings
from keryxflow.core.logging import get_logger
from keryxflow.core.models import RiskProfile
from keryxflow.oracle.mtf_signals import MTFSignalGenerator
from keryxflow.oracle.signals import SignalGenerator, SignalType, TradingSignal

if TYPE_CHECKING:
    from keryxflow.backtester.report import BacktestResult

logger = get_logger(__name__)


@dataclass
class BacktestTrade:
    """A trade executed during backtesting."""

    symbol: str
    side: str  # "buy" or "sell"
    quantity: float
    entry_price: float
    entry_time: datetime
    exit_price: float | None = None
    exit_time: datetime | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    pnl: float = 0.0
    pnl_percentage: float = 0.0
    exit_reason: str | None = None  # "stop_loss", "take_profit", "signal", "end"

    @property
    def is_closed(self) -> bool:
        """Check if trade is closed."""
        return self.exit_price is not None

    @property
    def is_winner(self) -> bool:
        """Check if trade is a winner."""
        return self.pnl > 0


@dataclass
class BacktestPosition:
    """An open position during backtesting."""

    symbol: str
    side: str
    quantity: float
    entry_price: float
    entry_time: datetime
    stop_loss: float | None = None
    take_profit: float | None = None
    current_price: float = 0.0

    @property
    def unrealized_pnl(self) -> float:
        """Calculate unrealized PnL."""
        if self.side == "buy":
            return (self.current_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - self.current_price) * self.quantity

    @property
    def unrealized_pnl_percentage(self) -> float:
        """Calculate unrealized PnL percentage."""
        if self.entry_price == 0:
            return 0.0
        if self.side == "buy":
            return (self.current_price - self.entry_price) / self.entry_price * 100
        else:
            return (self.entry_price - self.current_price) / self.entry_price * 100


@dataclass
class BacktestEngine:
    """Backtesting engine that simulates trading with historical data."""

    initial_balance: float = 10000.0
    risk_profile: RiskProfile = RiskProfile.BALANCED
    slippage: float = 0.001  # 0.1%
    commission: float = 0.001  # 0.1% per trade
    min_candles: int = 50  # Minimum candles for analysis
    mtf_enabled: bool = False  # Multi-timeframe analysis
    primary_timeframe: str | None = None  # Primary TF for MTF mode

    # Components (initialized in __post_init__)
    signal_gen: SignalGenerator = field(init=False)
    risk_manager: RiskManager = field(init=False)
    quant: QuantEngine = field(init=False)

    # State
    balance: float = field(init=False)
    positions: dict[str, BacktestPosition] = field(default_factory=dict)
    trades: list[BacktestTrade] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    _current_time: datetime = field(init=False, default=None)

    def __post_init__(self):
        """Initialize components after dataclass init."""
        self.balance = self.initial_balance
        self.settings = get_settings()

        # Create appropriate signal generator
        if self.mtf_enabled:
            self.signal_gen = MTFSignalGenerator(publish_events=False)
            # Use settings for primary TF if not specified
            if self.primary_timeframe is None:
                self.primary_timeframe = self.settings.oracle.mtf.primary_timeframe
        else:
            self.signal_gen = SignalGenerator(publish_events=False)

        self.risk_manager = get_risk_manager(
            risk_profile=self.risk_profile,
            initial_balance=self.initial_balance,
        )
        self.quant = get_quant_engine()

    async def run(
        self,
        data: dict[str, pd.DataFrame] | dict[str, dict[str, pd.DataFrame]],
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> "BacktestResult":
        """
        Run backtest on historical data.

        Args:
            data: Either:
                - Single TF: Dict of {symbol: OHLCV DataFrame}
                - MTF mode: Dict of {symbol: {timeframe: OHLCV DataFrame}}
            start: Start datetime (optional, uses data start if None)
            end: End datetime (optional, uses data end if None)

        Returns:
            BacktestResult with performance metrics
        """
        # Handle empty data early
        if not data:
            raise ValueError("No data in specified range")

        # Determine if MTF data
        is_mtf_data = False
        first_value = next(iter(data.values()))
        if isinstance(first_value, dict):
            is_mtf_data = True
            if not self.mtf_enabled:
                logger.warning("mtf_data_provided_but_mtf_disabled")

        # Reset state
        self.balance = self.initial_balance
        self.positions = {}
        self.trades = []
        self.equity_curve = [self.initial_balance]

        # Get primary data for timestamps
        primary_data = self._get_primary_timeframe_data(data) if is_mtf_data else data

        # Get all timestamps across all symbols
        all_timestamps = set()
        for df in primary_data.values():
            all_timestamps.update(df["datetime"].tolist())

        timestamps = sorted(all_timestamps)

        # Filter by start/end
        if start:
            timestamps = [t for t in timestamps if t >= start]
        if end:
            timestamps = [t for t in timestamps if t <= end]

        if not timestamps:
            raise ValueError("No data in specified range")

        logger.info(
            "backtest_starting",
            symbols=list(data.keys()),
            start=timestamps[0].isoformat(),
            end=timestamps[-1].isoformat(),
            candles=len(timestamps),
            mtf_enabled=self.mtf_enabled,
        )

        # Process each timestamp
        for timestamp in timestamps:
            self._current_time = timestamp

            for symbol in data:
                if is_mtf_data:
                    # Get MTF data up to current timestamp
                    mtf_history = self._get_mtf_history(data[symbol], timestamp)
                    primary_df = mtf_history.get(self.primary_timeframe)

                    if primary_df is None or len(primary_df) < self.min_candles:
                        continue

                    current_candle = primary_df.iloc[-1]
                    await self._process_candle_mtf(symbol, current_candle, mtf_history)
                else:
                    # Single TF mode
                    df = data[symbol]
                    mask = df["datetime"] <= timestamp
                    history = df[mask]

                    if len(history) < self.min_candles:
                        continue

                    current_candle = history.iloc[-1]
                    await self._process_candle(symbol, current_candle, history)

            # Update equity curve
            total_equity = self._calculate_equity()
            self.equity_curve.append(total_equity)

            # Check for forced liquidation (margin call simulation)
            # Liquidate all positions if equity drops below 1% of initial
            liquidation_threshold = self.initial_balance * 0.01
            if total_equity <= liquidation_threshold and self.positions:
                logger.warning(
                    "forced_liquidation",
                    equity=total_equity,
                    threshold=liquidation_threshold,
                )
                for symbol in list(self.positions.keys()):
                    pos = self.positions[symbol]
                    self._close_position(symbol, pos.current_price, "liquidation")
                # Update equity after liquidation
                total_equity = self._calculate_equity()
                self.equity_curve[-1] = total_equity

            # Update risk manager balance
            self.risk_manager.update_balance(total_equity)

        # Close any remaining positions at end
        for symbol in list(self.positions.keys()):
            last_df = data[symbol].get(self.primary_timeframe) if is_mtf_data else data[symbol]
            if last_df is not None:
                last_price = last_df.iloc[-1]["close"]
                self._close_position(symbol, last_price, "end")

        # Calculate final metrics
        return self._calculate_result()

    def _get_primary_timeframe_data(
        self, mtf_data: dict[str, dict[str, pd.DataFrame]]
    ) -> dict[str, pd.DataFrame]:
        """Extract primary timeframe data from MTF data structure."""
        result = {}
        for symbol, tf_data in mtf_data.items():
            if self.primary_timeframe in tf_data:
                result[symbol] = tf_data[self.primary_timeframe]
            elif tf_data:
                # Fallback to first available
                result[symbol] = next(iter(tf_data.values()))
        return result

    def _get_mtf_history(
        self, symbol_data: dict[str, pd.DataFrame], timestamp: datetime
    ) -> dict[str, pd.DataFrame]:
        """Get history up to timestamp for all timeframes."""
        result = {}
        for tf, df in symbol_data.items():
            mask = df["datetime"] <= timestamp
            history = df[mask]
            if len(history) > 0:
                result[tf] = history
        return result

    async def _process_candle_mtf(
        self,
        symbol: str,
        candle: pd.Series,
        mtf_history: dict[str, pd.DataFrame],
    ) -> None:
        """Process a single candle with MTF data."""
        current_price = candle["close"]
        high = candle["high"]
        low = candle["low"]

        # Update position price if exists
        if symbol in self.positions:
            self.positions[symbol].current_price = current_price

            # Check stops
            self._check_stops(symbol, high, low)

            # If position was closed by stop, return
            if symbol not in self.positions:
                return

        # Generate signal with MTF data
        try:
            signal = await self.signal_gen.generate_signal(
                symbol=symbol,
                ohlcv=mtf_history,  # Pass dict for MTF
                current_price=current_price,
                include_news=False,
                include_llm=False,
            )
        except Exception as e:
            logger.warning("signal_generation_failed", symbol=symbol, error=str(e))
            return

        # Process signal (same as single TF)
        await self._process_signal(symbol, signal, current_price)

    async def _process_candle(
        self,
        symbol: str,
        candle: pd.Series,
        history: pd.DataFrame,
    ) -> None:
        """Process a single candle."""
        current_price = candle["close"]
        high = candle["high"]
        low = candle["low"]

        # Update position price if exists
        if symbol in self.positions:
            self.positions[symbol].current_price = current_price

            # Check stops
            self._check_stops(symbol, high, low)

            # If position was closed by stop, return
            if symbol not in self.positions:
                return

        # Generate signal (without LLM/news for speed)
        try:
            signal = await self.signal_gen.generate_signal(
                symbol=symbol,
                ohlcv=history,
                current_price=current_price,
                include_news=False,
                include_llm=False,
            )
        except Exception as e:
            logger.warning("signal_generation_failed", symbol=symbol, error=str(e))
            return

        # Process signal
        await self._process_signal(symbol, signal, current_price)

    async def _process_signal(
        self, symbol: str, signal: TradingSignal, current_price: float
    ) -> None:
        """Process a trading signal."""
        # Process actionable signals
        if not signal.is_actionable:
            return

        # Determine side
        if signal.signal_type == SignalType.LONG:
            side = "buy"
        elif signal.signal_type == SignalType.SHORT:
            side = "sell"
        elif signal.signal_type in (SignalType.CLOSE_LONG, SignalType.CLOSE_SHORT):
            # Close existing position
            if symbol in self.positions:
                self._close_position(symbol, current_price, "signal")
            return
        else:
            return

        # Skip if already in position
        if symbol in self.positions:
            return

        # Skip if no stop loss
        if not signal.stop_loss:
            return

        # Calculate position size
        quantity = self.risk_manager.calculate_safe_position_size(
            symbol=symbol,
            entry_price=signal.entry_price or current_price,
            stop_loss=signal.stop_loss,
            balance=self.balance,
        )

        if quantity <= 0:
            return

        # Create order request
        order = OrderRequest(
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=signal.entry_price or current_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
        )

        # Get approval from risk manager
        approval = self.risk_manager.approve_order(order, self.balance)

        if not approval.approved:
            logger.debug(
                "order_rejected",
                symbol=symbol,
                reason=approval.reason.value if approval.reason else "unknown",
            )
            return

        # Execute order
        self._execute_order(order)

    def _check_stops(self, symbol: str, high: float, low: float) -> None:
        """Check if stops are hit."""
        if symbol not in self.positions:
            return

        position = self.positions[symbol]

        # Check stop loss
        if position.stop_loss and (
            (position.side == "buy" and low <= position.stop_loss)
            or (position.side == "sell" and high >= position.stop_loss)
        ):
            self._close_position(symbol, position.stop_loss, "stop_loss")
            return

        # Check take profit
        if position.take_profit and (
            (position.side == "buy" and high >= position.take_profit)
            or (position.side == "sell" and low <= position.take_profit)
        ):
            self._close_position(symbol, position.take_profit, "take_profit")
            return

    def _execute_order(self, order: OrderRequest) -> None:
        """Execute an order (open position)."""
        # Apply slippage
        if order.side == "buy":
            fill_price = order.entry_price * (1 + self.slippage)
        else:
            fill_price = order.entry_price * (1 - self.slippage)

        # Calculate cost with commission
        cost = order.quantity * fill_price
        commission = cost * self.commission

        # Deduct from balance
        self.balance -= cost + commission

        # Create position
        position = BacktestPosition(
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            entry_price=fill_price,
            entry_time=self._current_time,
            stop_loss=order.stop_loss,
            take_profit=order.take_profit,
            current_price=fill_price,
        )

        self.positions[order.symbol] = position

        # Update risk manager position count
        self.risk_manager.set_open_positions(len(self.positions))

        logger.debug(
            "position_opened",
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=fill_price,
        )

    def _close_position(self, symbol: str, exit_price: float, reason: str) -> None:
        """Close a position."""
        if symbol not in self.positions:
            return

        position = self.positions[symbol]

        # Apply slippage on exit
        if position.side == "buy":
            fill_price = exit_price * (1 - self.slippage)
        else:
            fill_price = exit_price * (1 + self.slippage)

        # Calculate PnL
        if position.side == "buy":
            pnl = (fill_price - position.entry_price) * position.quantity
        else:
            pnl = (position.entry_price - fill_price) * position.quantity

        # Deduct commission
        commission = position.quantity * fill_price * self.commission
        pnl -= commission

        # Calculate percentage
        entry_value = position.entry_price * position.quantity
        pnl_percentage = (pnl / entry_value) * 100 if entry_value > 0 else 0

        # Add to balance
        exit_value = position.quantity * fill_price
        self.balance += exit_value

        # Create trade record
        trade = BacktestTrade(
            symbol=symbol,
            side=position.side,
            quantity=position.quantity,
            entry_price=position.entry_price,
            entry_time=position.entry_time,
            exit_price=fill_price,
            exit_time=self._current_time,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            pnl=pnl,
            pnl_percentage=pnl_percentage,
            exit_reason=reason,
        )

        self.trades.append(trade)

        # Remove position
        del self.positions[symbol]

        # Update risk manager
        self.risk_manager.set_open_positions(len(self.positions))
        self.risk_manager.update_daily_pnl(pnl)

        logger.debug(
            "position_closed",
            symbol=symbol,
            pnl=pnl,
            reason=reason,
        )

    def _calculate_equity(self) -> float:
        """Calculate total equity (balance + unrealized PnL)."""
        unrealized = sum(pos.unrealized_pnl for pos in self.positions.values())
        return self.balance + unrealized

    def _calculate_result(self) -> "BacktestResult":
        """Calculate backtest result with metrics."""
        from keryxflow.backtester.report import BacktestResult

        final_balance = self._calculate_equity()
        total_return = (final_balance - self.initial_balance) / self.initial_balance

        # Trade statistics
        total_trades = len(self.trades)
        winning_trades = sum(1 for t in self.trades if t.is_winner)
        losing_trades = total_trades - winning_trades
        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        # Average win/loss
        wins = [t.pnl for t in self.trades if t.is_winner]
        losses = [abs(t.pnl) for t in self.trades if not t.is_winner]
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0

        # Expectancy
        expectancy = self.quant.calculate_expectancy(win_rate, avg_win, avg_loss)

        # Profit factor
        gross_profit = sum(wins)
        gross_loss = sum(losses)
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        # Drawdown
        current_dd, max_dd, max_dd_duration = self.quant.calculate_drawdown(self.equity_curve)

        # Sharpe ratio (using daily returns approximation)
        returns = []
        for i in range(1, len(self.equity_curve)):
            ret = (self.equity_curve[i] - self.equity_curve[i - 1]) / self.equity_curve[i - 1]
            returns.append(ret)

        sharpe = self.quant.calculate_sharpe_ratio(returns) if returns else 0

        return BacktestResult(
            initial_balance=self.initial_balance,
            final_balance=final_balance,
            total_return=total_return,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            expectancy=expectancy,
            profit_factor=profit_factor,
            max_drawdown=max_dd,
            max_drawdown_duration=max_dd_duration,
            sharpe_ratio=sharpe,
            trades=self.trades,
            equity_curve=self.equity_curve,
        )
