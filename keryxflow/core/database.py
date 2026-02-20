"""Database configuration and session management."""

from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from keryxflow.config import get_settings
from keryxflow.core.models import (
    DailyStats,
    MarketContext,
    MarketPattern,
    PaperBalance,
    Position,
    Signal,
    Trade,
    TradeEpisode,
    TradingRule,
    UserProfile,
)

# Re-export models for convenience
__all__ = [
    "DailyStats",
    "MarketContext",
    "MarketPattern",
    "PaperBalance",
    "Position",
    "Signal",
    "Trade",
    "TradeEpisode",
    "TradingRule",
    "UserProfile",
    "get_session",
    "init_db",
]


def get_database_url() -> str:
    """Get the database URL from settings."""
    settings = get_settings()
    return settings.database.url


def ensure_data_directory() -> None:
    """Ensure the data directory exists."""
    settings = get_settings()
    db_url = settings.database.url

    # Extract path from sqlite URL
    if db_url.startswith("sqlite"):
        db_path = db_url.split("///")[-1]
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)


# Create async engine
_engine = None
_async_session_factory = None


def get_engine():
    """Get or create the async database engine."""
    global _engine
    if _engine is None:
        ensure_data_directory()
        _engine = create_async_engine(
            get_database_url(),
            echo=False,  # Set to True for SQL debugging
            future=True,
        )
    return _engine


def get_session_factory():
    """Get or create the async session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


async def init_db() -> None:
    """Initialize the database, creating all tables."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session."""
    async_session = get_session_factory()
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_or_create_user_profile(session: AsyncSession) -> UserProfile:
    """Get the user profile or create a default one."""
    from sqlmodel import select

    result = await session.execute(select(UserProfile).limit(1))
    profile = result.scalar_one_or_none()

    if profile is None:
        profile = UserProfile()
        session.add(profile)
        await session.commit()
        await session.refresh(profile)

    return profile


async def initialize_paper_balance(
    session: AsyncSession,
    currency: str = "USDT",
    amount: float = 10000.0,
) -> PaperBalance:
    """Initialize paper trading balance."""
    from sqlmodel import select

    result = await session.execute(select(PaperBalance).where(PaperBalance.currency == currency))
    balance = result.scalar_one_or_none()

    if balance is None:
        balance = PaperBalance(
            currency=currency,
            total=amount,
            free=amount,
            used=0.0,
        )
        session.add(balance)
        await session.commit()
        await session.refresh(balance)

    return balance
