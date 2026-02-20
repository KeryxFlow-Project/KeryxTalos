"""Glossary of trading terms with beginner-friendly explanations."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class GlossaryEntry:
    """A glossary entry with multiple explanation levels."""

    term: str
    name: str
    simple: str
    technical: str
    why_matters: str
    category: Literal["basics", "indicators", "risk", "orders", "analysis"]


# Complete glossary of trading terms
GLOSSARY: dict[str, GlossaryEntry] = {
    # === BASICS ===
    "position": GlossaryEntry(
        term="position",
        name="Position",
        simple="A trade you currently have open",
        technical="An open market exposure in a specific asset, either long or short",
        why_matters="Shows what you own and your current profit/loss",
        category="basics",
    ),
    "pnl": GlossaryEntry(
        term="pnl",
        name="PnL (Profit and Loss)",
        simple="How much money you've made or lost",
        technical="Net realized and unrealized gains/losses on positions",
        why_matters="The bottom line — are you winning or losing?",
        category="basics",
    ),
    "long": GlossaryEntry(
        term="long",
        name="Long Position",
        simple="Buying something because you think the price will go up",
        technical="A position that profits from price appreciation",
        why_matters="The most common way to trade — buy low, sell high",
        category="basics",
    ),
    "short": GlossaryEntry(
        term="short",
        name="Short Position",
        simple="Betting that the price will go down",
        technical="A position that profits from price depreciation, created by selling borrowed assets",
        why_matters="Allows profit in falling markets, but has higher risk",
        category="basics",
    ),
    "paper_trading": GlossaryEntry(
        term="paper_trading",
        name="Paper Trading",
        simple="Practice trading with fake money",
        technical="Simulated trading using historical or live data without real capital",
        why_matters="Learn without risking real money",
        category="basics",
    ),
    "spot": GlossaryEntry(
        term="spot",
        name="Spot Trading",
        simple="Buying and selling the actual asset",
        technical="Trading for immediate delivery at current market price",
        why_matters="Simple and straightforward — you own what you buy",
        category="basics",
    ),
    "futures": GlossaryEntry(
        term="futures",
        name="Futures Trading",
        simple="Contracts to buy/sell at a future date, often with leverage",
        technical="Derivative contracts for future delivery at predetermined price",
        why_matters="Allows leverage but increases risk significantly",
        category="basics",
    ),
    # === INDICATORS ===
    "rsi": GlossaryEntry(
        term="rsi",
        name="RSI (Relative Strength Index)",
        simple="Shows if something is too expensive or too cheap",
        technical="Momentum oscillator (0-100). Above 70 = overbought, below 30 = oversold",
        why_matters="Helps avoid buying at the top or selling at the bottom",
        category="indicators",
    ),
    "macd": GlossaryEntry(
        term="macd",
        name="MACD (Moving Average Convergence Divergence)",
        simple="Shows if momentum is building up or fading",
        technical="Trend-following indicator using difference between 12 and 26 EMAs",
        why_matters="Helps identify when trends are starting or ending",
        category="indicators",
    ),
    "bbands": GlossaryEntry(
        term="bbands",
        name="Bollinger Bands",
        simple="Shows normal price range — above or below is unusual",
        technical="Volatility bands at 2 standard deviations from 20-period SMA",
        why_matters="Price outside bands often means reversal coming",
        category="indicators",
    ),
    "obv": GlossaryEntry(
        term="obv",
        name="OBV (On-Balance Volume)",
        simple="Shows if big players are buying or selling",
        technical="Cumulative volume indicator adding volume on up days, subtracting on down",
        why_matters="Volume often leads price — smart money moves first",
        category="indicators",
    ),
    "atr": GlossaryEntry(
        term="atr",
        name="ATR (Average True Range)",
        simple="How much the price typically moves",
        technical="14-period average of true range (high-low including gaps)",
        why_matters="Used to set stop-loss at appropriate distance",
        category="indicators",
    ),
    "ema": GlossaryEntry(
        term="ema",
        name="EMA (Exponential Moving Average)",
        simple="Smoothed price line that follows the trend",
        technical="Moving average giving more weight to recent prices",
        why_matters="Shows trend direction and dynamic support/resistance",
        category="indicators",
    ),
    # === RISK ===
    "stop_loss": GlossaryEntry(
        term="stop_loss",
        name="Stop-Loss",
        simple="Automatic sell if price drops too much",
        technical="Pre-set exit order triggered at specified price level",
        why_matters="Limits your maximum loss on a trade",
        category="risk",
    ),
    "take_profit": GlossaryEntry(
        term="take_profit",
        name="Take-Profit",
        simple="Automatic sell when you've made enough profit",
        technical="Pre-set order to close position at target price",
        why_matters="Locks in gains instead of waiting too long",
        category="risk",
    ),
    "drawdown": GlossaryEntry(
        term="drawdown",
        name="Drawdown",
        simple="How much you've lost from your highest point",
        technical="Peak-to-trough decline in account value, usually expressed as percentage",
        why_matters="Measures how bad losing periods get",
        category="risk",
    ),
    "position_sizing": GlossaryEntry(
        term="position_sizing",
        name="Position Sizing",
        simple="How much money to put in each trade",
        technical="Calculation of trade size based on risk per trade and stop-loss distance",
        why_matters="Prevents any single trade from hurting too much",
        category="risk",
    ),
    "risk_reward": GlossaryEntry(
        term="risk_reward",
        name="Risk/Reward Ratio",
        simple="How much you can win vs. how much you can lose",
        technical="Ratio of potential profit to potential loss (e.g., 2:1 means win $2 for every $1 risked)",
        why_matters="Only take trades where reward justifies the risk",
        category="risk",
    ),
    "circuit_breaker": GlossaryEntry(
        term="circuit_breaker",
        name="Circuit Breaker",
        simple="Emergency stop when losses get too big",
        technical="Automated trading halt triggered by daily drawdown limit",
        why_matters="Prevents catastrophic losses in bad days",
        category="risk",
    ),
    "kelly": GlossaryEntry(
        term="kelly",
        name="Kelly Criterion",
        simple="Math formula for optimal bet size",
        technical="Position sizing based on win rate and average win/loss ratio",
        why_matters="Maximizes long-term growth without excessive risk",
        category="risk",
    ),
    # === ORDERS ===
    "market_order": GlossaryEntry(
        term="market_order",
        name="Market Order",
        simple="Buy or sell right now at current price",
        technical="Order executed immediately at best available price",
        why_matters="Guaranteed execution but may get worse price",
        category="orders",
    ),
    "limit_order": GlossaryEntry(
        term="limit_order",
        name="Limit Order",
        simple="Buy or sell only at your specified price or better",
        technical="Order that executes only at specified price or better",
        why_matters="Better price but might not execute",
        category="orders",
    ),
    "slippage": GlossaryEntry(
        term="slippage",
        name="Slippage",
        simple="Getting a slightly different price than expected",
        technical="Difference between expected and actual execution price",
        why_matters="Can reduce profits, especially in fast markets",
        category="orders",
    ),
    # === ANALYSIS ===
    "sentiment": GlossaryEntry(
        term="sentiment",
        name="Market Sentiment",
        simple="The overall mood of the market (bullish or bearish)",
        technical="Aggregate market participants' attitude derived from news and social data",
        why_matters="Markets can move on mood, not just fundamentals",
        category="analysis",
    ),
    "bullish": GlossaryEntry(
        term="bullish",
        name="Bullish",
        simple="Expecting prices to go up",
        technical="Positive market outlook indicating upward price movement",
        why_matters="Bullish signals suggest buying opportunities",
        category="analysis",
    ),
    "bearish": GlossaryEntry(
        term="bearish",
        name="Bearish",
        simple="Expecting prices to go down",
        technical="Negative market outlook indicating downward price movement",
        why_matters="Bearish signals suggest selling or avoiding buys",
        category="analysis",
    ),
    "signal": GlossaryEntry(
        term="signal",
        name="Trading Signal",
        simple="A suggestion to buy, sell, or hold",
        technical="Actionable trading indication generated by analysis system",
        why_matters="Tells you when conditions might be favorable",
        category="analysis",
    ),
    "confidence": GlossaryEntry(
        term="confidence",
        name="Signal Confidence",
        simple="How sure we are about the signal (0-100%)",
        technical="Probability score based on indicator alignment and context",
        why_matters="Higher confidence = stronger signal",
        category="analysis",
    ),
}


def get_term(term: str) -> GlossaryEntry | None:
    """
    Get a glossary entry by term.

    Args:
        term: The term to look up (case-insensitive)

    Returns:
        GlossaryEntry if found, None otherwise
    """
    return GLOSSARY.get(term.lower())


def get_terms_by_category(category: str) -> list[GlossaryEntry]:
    """
    Get all terms in a category.

    Args:
        category: The category to filter by

    Returns:
        List of GlossaryEntry objects in that category
    """
    return [entry for entry in GLOSSARY.values() if entry.category == category]


def format_help_text(entry: GlossaryEntry, detailed: bool = False) -> str:
    """
    Format a glossary entry for display.

    Args:
        entry: The glossary entry to format
        detailed: Whether to include technical details

    Returns:
        Formatted help text string
    """
    lines = [
        f"📖 {entry.name}",
        "",
        f"   {entry.simple}",
    ]

    if detailed:
        lines.extend(
            [
                "",
                f"🔬 Technical: {entry.technical}",
            ]
        )

    lines.extend(
        [
            "",
            f"💡 Why it matters: {entry.why_matters}",
        ]
    )

    return "\n".join(lines)


def search_glossary(query: str) -> list[GlossaryEntry]:
    """
    Search glossary for terms matching query.

    Args:
        query: Search string

    Returns:
        List of matching GlossaryEntry objects
    """
    query = query.lower()
    results = []

    for entry in GLOSSARY.values():
        if (
            query in entry.term.lower()
            or query in entry.name.lower()
            or query in entry.simple.lower()
        ):
            results.append(entry)

    return results
