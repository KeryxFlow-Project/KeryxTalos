"""Database models using SQLModel."""

from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

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
    created_at: datetime = Field(default_factory=datetime.utcnow)
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
    created_at: datetime = Field(default_factory=datetime.utcnow)


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
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


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
    created_at: datetime = Field(default_factory=datetime.utcnow)
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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PaperBalance(SQLModel, table=True):
    """Paper trading balance tracker."""

    __tablename__ = "paper_balances"

    id: int | None = Field(default=None, primary_key=True)
    currency: str = Field(index=True, unique=True)
    total: float = 0.0
    free: float = 0.0
    used: float = 0.0
    updated_at: datetime = Field(default_factory=datetime.utcnow)
