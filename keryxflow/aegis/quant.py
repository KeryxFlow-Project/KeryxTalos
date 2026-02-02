"""Quantitative calculations for risk management."""

from dataclasses import dataclass

import numpy as np

from keryxflow.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PositionSizeResult:
    """Result of position size calculation."""

    quantity: float
    risk_amount: float
    stop_distance: float
    position_value: float
    risk_percentage: float

    # For display
    simple_explanation: str
    technical_details: str


@dataclass
class RiskRewardResult:
    """Result of risk/reward calculation."""

    ratio: float
    potential_profit: float
    potential_loss: float
    breakeven_winrate: float

    # For display
    simple_explanation: str
    is_favorable: bool


class QuantEngine:
    """
    Mathematical engine for quantitative risk calculations.

    Provides position sizing, risk/reward analysis, and
    volatility-based stop loss calculations.
    """

    def __init__(self, default_risk_per_trade: float = 0.01):
        """
        Initialize the quant engine.

        Args:
            default_risk_per_trade: Default risk percentage per trade (0.01 = 1%)
        """
        self.default_risk_per_trade = default_risk_per_trade

    def position_size(
        self,
        balance: float,
        entry_price: float,
        stop_loss: float,
        risk_per_trade: float | None = None,
    ) -> PositionSizeResult:
        """
        Calculate optimal position size based on risk.

        Uses fixed fractional position sizing: risk a fixed percentage
        of account on each trade.

        Args:
            balance: Account balance
            entry_price: Entry price
            stop_loss: Stop loss price
            risk_per_trade: Risk percentage (default from config)

        Returns:
            PositionSizeResult with quantity and details
        """
        if risk_per_trade is None:
            risk_per_trade = self.default_risk_per_trade

        # Calculate stop distance
        stop_distance = abs(entry_price - stop_loss)

        if stop_distance == 0:
            raise ValueError("Stop loss cannot be equal to entry price")

        # Risk amount in quote currency
        risk_amount = balance * risk_per_trade

        # Position size = risk_amount / stop_distance
        quantity = risk_amount / stop_distance
        position_value = quantity * entry_price

        # Create explanations
        simple = (
            f"With ${balance:,.0f} risking {risk_per_trade:.1%}, "
            f"you can buy {quantity:.6f} units. "
            f"If price hits ${stop_loss:,.2f}, you lose ${risk_amount:,.2f}."
        )

        technical = (
            f"Position Size = Risk Amount / Stop Distance\n"
            f"  = ${risk_amount:,.2f} / ${stop_distance:,.2f}\n"
            f"  = {quantity:.6f} units\n"
            f"Position Value: ${position_value:,.2f}"
        )

        logger.debug(
            "position_size_calculated",
            balance=balance,
            entry=entry_price,
            stop=stop_loss,
            quantity=quantity,
        )

        return PositionSizeResult(
            quantity=quantity,
            risk_amount=risk_amount,
            stop_distance=stop_distance,
            position_value=position_value,
            risk_percentage=risk_per_trade,
            simple_explanation=simple,
            technical_details=technical,
        )

    def kelly_criterion(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        fraction: float = 0.5,
    ) -> float:
        """
        Calculate Kelly Criterion optimal bet size.

        Kelly = (W * R - L) / R
        Where:
            W = win rate
            R = win/loss ratio
            L = loss rate (1 - W)

        Args:
            win_rate: Historical win rate (0.0 to 1.0)
            avg_win: Average winning trade amount
            avg_loss: Average losing trade amount (positive number)
            fraction: Kelly fraction to use (0.5 = half Kelly, safer)

        Returns:
            Optimal fraction of capital to risk
        """
        if win_rate <= 0 or win_rate >= 1:
            raise ValueError("Win rate must be between 0 and 1 (exclusive)")

        if avg_loss <= 0:
            raise ValueError("Average loss must be positive")

        # Win/loss ratio
        r = avg_win / avg_loss

        # Kelly formula
        kelly = (win_rate * r - (1 - win_rate)) / r

        # Apply fraction (half Kelly is common for safety)
        adjusted_kelly = kelly * fraction

        # Clamp to reasonable bounds
        adjusted_kelly = max(0.0, min(adjusted_kelly, 0.25))  # Max 25%

        logger.debug(
            "kelly_calculated",
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            kelly=kelly,
            adjusted=adjusted_kelly,
        )

        return adjusted_kelly

    def atr_stop_loss(
        self,
        prices_high: list[float],
        prices_low: list[float],
        prices_close: list[float],
        entry_price: float,
        side: str,
        multiplier: float = 2.0,
        period: int = 14,
    ) -> float:
        """
        Calculate ATR-based stop loss.

        ATR (Average True Range) measures volatility. Stop loss is placed
        at entry +/- (ATR * multiplier).

        Args:
            prices_high: High prices
            prices_low: Low prices
            prices_close: Close prices
            entry_price: Entry price
            side: "buy" or "sell"
            multiplier: ATR multiplier
            period: ATR period

        Returns:
            Stop loss price
        """
        if len(prices_high) < period + 1:
            raise ValueError(f"Need at least {period + 1} candles for ATR")

        highs = np.array(prices_high)
        lows = np.array(prices_low)
        closes = np.array(prices_close)

        # True Range = max(high-low, |high-prev_close|, |low-prev_close|)
        tr1 = highs[1:] - lows[1:]
        tr2 = np.abs(highs[1:] - closes[:-1])
        tr3 = np.abs(lows[1:] - closes[:-1])

        true_range = np.maximum(tr1, np.maximum(tr2, tr3))

        # ATR = SMA of True Range
        atr = np.mean(true_range[-period:])

        # Calculate stop
        stop_distance = atr * multiplier

        stop_loss = entry_price - stop_distance if side == "buy" else entry_price + stop_distance

        logger.debug(
            "atr_stop_calculated",
            atr=atr,
            multiplier=multiplier,
            stop_distance=stop_distance,
            stop_loss=stop_loss,
        )

        return stop_loss

    def fixed_percentage_stop(
        self,
        entry_price: float,
        side: str,
        percentage: float = 0.02,
    ) -> float:
        """
        Calculate fixed percentage stop loss.

        Args:
            entry_price: Entry price
            side: "buy" or "sell"
            percentage: Stop percentage (0.02 = 2%)

        Returns:
            Stop loss price
        """
        if side == "buy":
            return entry_price * (1 - percentage)
        else:
            return entry_price * (1 + percentage)

    def risk_reward_ratio(
        self,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        quantity: float = 1.0,
    ) -> RiskRewardResult:
        """
        Calculate risk/reward ratio.

        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            quantity: Position quantity

        Returns:
            RiskRewardResult with ratio and details
        """
        potential_loss = abs(entry_price - stop_loss) * quantity
        potential_profit = abs(take_profit - entry_price) * quantity

        if potential_loss == 0:
            raise ValueError("Potential loss cannot be zero")

        ratio = potential_profit / potential_loss
        breakeven_winrate = 1 / (1 + ratio)

        is_favorable = ratio >= 1.0

        simple = (
            f"Risk ${potential_loss:,.2f} to make ${potential_profit:,.2f}. "
            f"Ratio: {ratio:.1f}:1. "
            f"Need to win {breakeven_winrate:.0%} of trades to break even."
        )

        if ratio >= 2.0:
            simple += " This is a good setup."
        elif ratio >= 1.0:
            simple += " This is acceptable."
        else:
            simple += " Consider passing on this trade."

        logger.debug(
            "risk_reward_calculated",
            entry=entry_price,
            stop=stop_loss,
            target=take_profit,
            ratio=ratio,
        )

        return RiskRewardResult(
            ratio=ratio,
            potential_profit=potential_profit,
            potential_loss=potential_loss,
            breakeven_winrate=breakeven_winrate,
            simple_explanation=simple,
            is_favorable=is_favorable,
        )

    def calculate_drawdown(
        self,
        equity_curve: list[float],
    ) -> tuple[float, float, int]:
        """
        Calculate drawdown metrics from equity curve.

        Args:
            equity_curve: List of equity values over time

        Returns:
            Tuple of (current_drawdown, max_drawdown, max_drawdown_duration)
        """
        if not equity_curve:
            return (0.0, 0.0, 0)

        equity = np.array(equity_curve)
        peak = np.maximum.accumulate(equity)

        drawdown = (peak - equity) / peak
        max_drawdown = np.max(drawdown)
        current_drawdown = drawdown[-1]

        # Calculate max drawdown duration
        in_drawdown = equity < peak
        duration = 0
        max_duration = 0
        for is_dd in in_drawdown:
            if is_dd:
                duration += 1
                max_duration = max(max_duration, duration)
            else:
                duration = 0

        return (float(current_drawdown), float(max_drawdown), max_duration)

    def calculate_sharpe_ratio(
        self,
        returns: list[float],
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252,
    ) -> float:
        """
        Calculate Sharpe ratio.

        Sharpe = (mean_return - risk_free) / std_dev * sqrt(periods)

        Args:
            returns: List of period returns
            risk_free_rate: Risk-free rate (annualized)
            periods_per_year: Number of periods per year (252 for daily)

        Returns:
            Annualized Sharpe ratio
        """
        if len(returns) < 2:
            return 0.0

        returns_arr = np.array(returns)
        mean_return = np.mean(returns_arr)
        std_return = np.std(returns_arr, ddof=1)

        if std_return == 0:
            return 0.0

        # Adjust risk-free rate to period
        rf_period = risk_free_rate / periods_per_year

        sharpe = (mean_return - rf_period) / std_return * np.sqrt(periods_per_year)

        return float(sharpe)

    def calculate_expectancy(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
    ) -> float:
        """
        Calculate trading expectancy.

        Expectancy = (win_rate * avg_win) - (loss_rate * avg_loss)

        Args:
            win_rate: Win rate (0.0 to 1.0)
            avg_win: Average winning trade
            avg_loss: Average losing trade (positive number)

        Returns:
            Expected value per trade
        """
        loss_rate = 1 - win_rate
        return (win_rate * avg_win) - (loss_rate * avg_loss)


# Global instance
_quant_engine: QuantEngine | None = None


def get_quant_engine(default_risk: float = 0.01) -> QuantEngine:
    """Get the global quant engine instance."""
    global _quant_engine
    if _quant_engine is None:
        _quant_engine = QuantEngine(default_risk_per_trade=default_risk)
    return _quant_engine
