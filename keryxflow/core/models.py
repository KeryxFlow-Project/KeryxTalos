"""Database models using SQLModel."""

from datetime import UTC, datetime
from enum import Enum

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(UTC)


class TradeStatus(str, Enum):
    """Status of a trade."""

    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class TradeSide(str, Enum):
    """Side of a trade."""

    BUY = "buy"
    SELL = "sell"


class SignalDirection(str, Enum):
    """Direction of a trading signal."""

    LONG = "long"
    SHORT = "short"
    HOLD = "hold"


class SignalSource(str, Enum):
    """Source of a trading signal."""

    TECHNICAL = "technical"
    LLM = "llm"
    HYBRID = "hybrid"
    WEBHOOK = "webhook"


class ExperienceLevel(str, Enum):
    """User experience level."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class RiskProfile(str, Enum):
    """User risk profile."""

    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"


class UserProfile(SQLModel, table=True):
    """User profile storing preferences and experience level."""

    __tablename__ = "user_profiles"

    id: int | None = Field(default=None, primary_key=True)
    experience_level: ExperienceLevel = Field(default=ExperienceLevel.BEGINNER)
    risk_profile: RiskProfile = Field(default=RiskProfile.CONSERVATIVE)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    # Paper trading balance
    initial_balance: float = Field(default=10000.0)


class Trade(SQLModel, table=True):
    """A trade record."""

    __tablename__ = "trades"

    id: int | None = Field(default=None, primary_key=True)
    symbol: str = Field(index=True)
    side: TradeSide
    quantity: float
    entry_price: float
    exit_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    pnl: float | None = None
    pnl_percentage: float | None = None
    status: TradeStatus = Field(default=TradeStatus.PENDING)
    signal_id: int | None = Field(default=None, foreign_key="signals.id")

    # Timestamps
    created_at: datetime = Field(default_factory=utc_now)
    opened_at: datetime | None = None
    closed_at: datetime | None = None

    # Metadata
    is_paper: bool = Field(default=True)
    notes: str | None = None


class Signal(SQLModel, table=True):
    """A trading signal."""

    __tablename__ = "signals"

    id: int | None = Field(default=None, primary_key=True)
    symbol: str = Field(index=True)
    direction: SignalDirection
    strength: float = Field(ge=0.0, le=1.0)
    source: SignalSource

    # Context
    context_summary: str | None = None
    technical_data: str | None = None  # JSON string of indicators

    # Validation
    is_validated: bool = Field(default=False)
    validated_by_llm: bool = Field(default=False)
    validation_reason: str | None = None

    # Execution
    was_executed: bool = Field(default=False)
    rejection_reason: str | None = None

    # Timestamps
    created_at: datetime = Field(default_factory=utc_now)


class Position(SQLModel, table=True):
    """An open position."""

    __tablename__ = "positions"

    id: int | None = Field(default=None, primary_key=True)
    symbol: str = Field(index=True, unique=True)
    side: TradeSide
    quantity: float
    entry_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_percentage: float = 0.0
    stop_loss: float | None = None
    take_profit: float | None = None
    trade_id: int = Field(foreign_key="trades.id")

    # Timestamps
    opened_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class MarketContext(SQLModel, table=True):
    """Market context from LLM analysis."""

    __tablename__ = "market_contexts"

    id: int | None = Field(default=None, primary_key=True)
    symbol: str = Field(index=True)

    # Sentiment analysis
    sentiment_score: float = Field(ge=-1.0, le=1.0)  # -1 bearish, 0 neutral, 1 bullish
    sentiment_label: str  # bearish, neutral, bullish

    # Summary
    news_summary: str | None = None
    llm_analysis: str | None = None
    risk_factors: str | None = None  # JSON list

    # Recommendation
    recommendation: str | None = None  # buy, sell, hold, avoid
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    # Timestamps
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime | None = None  # Context validity period


class DailyStats(SQLModel, table=True):
    """Daily trading statistics."""

    __tablename__ = "daily_stats"

    id: int | None = Field(default=None, primary_key=True)
    date: str = Field(index=True, unique=True)  # YYYY-MM-DD format

    # Balance
    starting_balance: float
    ending_balance: float

    # Performance
    pnl: float = 0.0
    pnl_percentage: float = 0.0
    max_drawdown: float = 0.0

    # Trade stats
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0

    # Risk
    max_risk_used: float = 0.0
    circuit_breaker_triggered: bool = False

    # Timestamps
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PaperBalance(SQLModel, table=True):
    """Paper trading balance tracker."""

    __tablename__ = "paper_balances"

    id: int | None = Field(default=None, primary_key=True)
    currency: str = Field(index=True, unique=True)
    total: float = 0.0
    free: float = 0.0
    used: float = 0.0
    updated_at: datetime = Field(default_factory=utc_now)


# =============================================================================
# Memory System Models (Phase 2)
# =============================================================================


class RuleSource(str, Enum):
    """Source of a trading rule."""

    LEARNED = "learned"  # Learned from trading experience
    USER = "user"  # User-defined rule
    BACKTEST = "backtest"  # Derived from backtesting
    SYSTEM = "system"  # Built-in system rule


class RuleStatus(str, Enum):
    """Status of a trading rule."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    TESTING = "testing"
    DEPRECATED = "deprecated"


class PatternType(str, Enum):
    """Type of market pattern."""

    PRICE_ACTION = "price_action"
    INDICATOR = "indicator"
    VOLUME = "volume"
    SENTIMENT = "sentiment"
    COMBINED = "combined"


class TradeOutcome(str, Enum):
    """Outcome classification of a trade."""

    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    STOPPED_OUT = "stopped_out"
    TAKE_PROFIT = "take_profit"
    MANUAL_CLOSE = "manual_close"


class TradeEpisode(SQLModel, table=True):
    """
    Complete trade episode with reasoning and lessons learned.

    Stores the full context of a trade decision for future learning.
    """

    __tablename__ = "trade_episodes"

    id: int | None = Field(default=None, primary_key=True)
    trade_id: int = Field(foreign_key="trades.id", index=True)
    symbol: str = Field(index=True)

    # Entry context
    entry_timestamp: datetime = Field(default_factory=utc_now)
    entry_price: float
    entry_reasoning: str  # Why the trade was taken
    entry_confidence: float = Field(ge=0.0, le=1.0)

    # Technical context at entry (JSON)
    technical_context: str | None = None  # JSON: indicators, trends
    market_context: str | None = None  # JSON: news, sentiment
    memory_context: str | None = None  # JSON: similar trades recalled

    # Exit context
    exit_timestamp: datetime | None = None
    exit_price: float | None = None
    exit_reasoning: str | None = None  # Why the trade was closed

    # Outcome
    outcome: TradeOutcome | None = None
    pnl: float | None = None
    pnl_percentage: float | None = None
    risk_reward_achieved: float | None = None

    # Lessons learned
    lessons_learned: str | None = None  # What was learned from this trade
    what_went_well: str | None = None
    what_went_wrong: str | None = None
    would_take_again: bool | None = None  # Would take same trade again?

    # Metadata
    rules_applied: str | None = None  # JSON list of rule IDs applied
    patterns_identified: str | None = None  # JSON list of pattern IDs
    tags: str | None = None  # JSON list of tags for categorization

    # Timestamps
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class TradingRule(SQLModel, table=True):
    """
    Trading rule learned from experience or defined by user.

    Rules guide future trading decisions.
    """

    __tablename__ = "trading_rules"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: str

    # Rule definition
    condition: str  # Human-readable condition description
    condition_code: str | None = None  # Optional: machine-readable condition

    # Classification
    source: RuleSource = Field(default=RuleSource.LEARNED)
    status: RuleStatus = Field(default=RuleStatus.ACTIVE)
    category: str = Field(default="general")  # e.g., "entry", "exit", "risk"

    # Performance metrics
    times_applied: int = Field(default=0)
    times_successful: int = Field(default=0)
    success_rate: float = Field(default=0.0)
    avg_pnl_when_applied: float = Field(default=0.0)

    # Confidence and priority
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    priority: int = Field(default=0)  # Higher = more important

    # Context applicability
    applies_to_symbols: str | None = None  # JSON list, None = all
    applies_to_timeframes: str | None = None  # JSON list, None = all
    applies_to_market_conditions: str | None = None  # JSON: bullish, bearish, etc.

    # Learning metadata
    learned_from_episodes: str | None = None  # JSON list of episode IDs
    last_validated: datetime | None = None
    validation_count: int = Field(default=0)

    # Timestamps
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class MarketPattern(SQLModel, table=True):
    """
    Identified market pattern with statistics.

    Patterns are recurring market conditions that can predict outcomes.
    """

    __tablename__ = "market_patterns"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: str

    # Pattern definition
    pattern_type: PatternType
    definition: str  # Human-readable pattern description
    definition_code: str | None = None  # Optional: machine-readable definition

    # Detection criteria (JSON)
    detection_criteria: str | None = None  # JSON: conditions to identify pattern

    # Statistics
    times_identified: int = Field(default=0)
    times_profitable: int = Field(default=0)
    win_rate: float = Field(default=0.0)
    avg_return: float = Field(default=0.0)
    avg_duration_hours: float = Field(default=0.0)

    # Reliability
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    min_occurrences_for_validity: int = Field(default=10)
    is_validated: bool = Field(default=False)

    # Context
    typical_market_conditions: str | None = None  # JSON: when pattern appears
    associated_symbols: str | None = None  # JSON list of symbols
    associated_timeframes: str | None = None  # JSON list of timeframes

    # Example episodes
    example_episodes: str | None = None  # JSON list of episode IDs

    # Timestamps
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    last_seen: datetime | None = None
