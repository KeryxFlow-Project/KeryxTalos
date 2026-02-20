"""Episodic memory for trade episodes - record and recall similar situations."""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlmodel import select

from keryxflow.core.logging import get_logger
from keryxflow.core.models import (
    TradeEpisode,
    TradeOutcome,
)

logger = get_logger(__name__)


@dataclass
class SimilarityMatch:
    """A similar trade episode match."""

    episode: TradeEpisode
    similarity_score: float  # 0.0 to 1.0
    matching_factors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "episode_id": self.episode.id,
            "symbol": self.episode.symbol,
            "outcome": self.episode.outcome.value if self.episode.outcome else None,
            "pnl_percentage": self.episode.pnl_percentage,
            "entry_reasoning": self.episode.entry_reasoning,
            "lessons_learned": self.episode.lessons_learned,
            "similarity_score": self.similarity_score,
            "matching_factors": self.matching_factors,
        }


@dataclass
class EpisodeContext:
    """Context for creating a new trade episode."""

    trade_id: int
    symbol: str
    entry_price: float
    entry_reasoning: str
    entry_confidence: float
    technical_context: dict | None = None
    market_context: dict | None = None
    memory_context: dict | None = None
    rules_applied: list[int] | None = None
    patterns_identified: list[int] | None = None
    tags: list[str] | None = None


class EpisodicMemory:
    """
    Episodic memory for recording and recalling trade episodes.

    Provides functionality to:
    - Record complete trade episodes with full context
    - Recall similar past trades based on conditions
    - Update episodes with outcomes and lessons learned
    """

    def __init__(self, session_factory):
        """Initialize episodic memory."""
        self._session_factory = session_factory

    async def record_entry(self, context: EpisodeContext) -> TradeEpisode:
        """
        Record a trade entry as a new episode.

        Args:
            context: The entry context for the trade

        Returns:
            The created TradeEpisode
        """
        async with self._session_factory() as session:
            episode = TradeEpisode(
                trade_id=context.trade_id,
                symbol=context.symbol,
                entry_price=context.entry_price,
                entry_reasoning=context.entry_reasoning,
                entry_confidence=context.entry_confidence,
                technical_context=(
                    json.dumps(context.technical_context)
                    if context.technical_context
                    else None
                ),
                market_context=(
                    json.dumps(context.market_context) if context.market_context else None
                ),
                memory_context=(
                    json.dumps(context.memory_context) if context.memory_context else None
                ),
                rules_applied=(
                    json.dumps(context.rules_applied) if context.rules_applied else None
                ),
                patterns_identified=(
                    json.dumps(context.patterns_identified)
                    if context.patterns_identified
                    else None
                ),
                tags=json.dumps(context.tags) if context.tags else None,
            )

            session.add(episode)
            await session.commit()
            await session.refresh(episode)

            logger.info(
                "episode_recorded",
                episode_id=episode.id,
                trade_id=context.trade_id,
                symbol=context.symbol,
            )

            return episode

    async def record_exit(
        self,
        episode_id: int,
        exit_price: float,
        exit_reasoning: str,
        outcome: TradeOutcome,
        pnl: float,
        pnl_percentage: float,
        risk_reward_achieved: float | None = None,
    ) -> TradeEpisode | None:
        """
        Record the exit of a trade episode.

        Args:
            episode_id: ID of the episode to update
            exit_price: Exit price
            exit_reasoning: Why the trade was closed
            outcome: Outcome classification
            pnl: Profit/loss amount
            pnl_percentage: Profit/loss percentage
            risk_reward_achieved: Achieved risk/reward ratio

        Returns:
            Updated TradeEpisode or None if not found
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(TradeEpisode).where(TradeEpisode.id == episode_id)
            )
            episode = result.scalar_one_or_none()

            if episode is None:
                logger.warning("episode_not_found", episode_id=episode_id)
                return None

            episode.exit_timestamp = datetime.now(UTC)
            episode.exit_price = exit_price
            episode.exit_reasoning = exit_reasoning
            episode.outcome = outcome
            episode.pnl = pnl
            episode.pnl_percentage = pnl_percentage
            episode.risk_reward_achieved = risk_reward_achieved
            episode.updated_at = datetime.now(UTC)

            await session.commit()
            await session.refresh(episode)

            logger.info(
                "episode_exit_recorded",
                episode_id=episode_id,
                outcome=outcome.value,
                pnl_percentage=pnl_percentage,
            )

            return episode

    async def record_lessons(
        self,
        episode_id: int,
        lessons_learned: str,
        what_went_well: str | None = None,
        what_went_wrong: str | None = None,
        would_take_again: bool | None = None,
    ) -> TradeEpisode | None:
        """
        Record lessons learned from a trade episode.

        Args:
            episode_id: ID of the episode to update
            lessons_learned: Main lessons from the trade
            what_went_well: What worked well
            what_went_wrong: What could be improved
            would_take_again: Whether trader would repeat this trade

        Returns:
            Updated TradeEpisode or None if not found
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(TradeEpisode).where(TradeEpisode.id == episode_id)
            )
            episode = result.scalar_one_or_none()

            if episode is None:
                return None

            episode.lessons_learned = lessons_learned
            episode.what_went_well = what_went_well
            episode.what_went_wrong = what_went_wrong
            episode.would_take_again = would_take_again
            episode.updated_at = datetime.now(UTC)

            await session.commit()
            await session.refresh(episode)

            logger.info("episode_lessons_recorded", episode_id=episode_id)

            return episode

    async def get_episode(self, episode_id: int) -> TradeEpisode | None:
        """Get a specific episode by ID."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(TradeEpisode).where(TradeEpisode.id == episode_id)
            )
            return result.scalar_one_or_none()

    async def get_episode_by_trade(self, trade_id: int) -> TradeEpisode | None:
        """Get episode by trade ID."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(TradeEpisode).where(TradeEpisode.trade_id == trade_id)
            )
            return result.scalar_one_or_none()

    async def recall_similar(
        self,
        symbol: str | None = None,
        technical_indicators: dict | None = None,
        market_sentiment: str | None = None,
        limit: int = 5,
        min_similarity: float = 0.3,
        days_back: int = 90,
    ) -> list[SimilarityMatch]:
        """
        Recall similar past trade episodes.

        Args:
            symbol: Filter by symbol (optional)
            technical_indicators: Current technical context for matching
            market_sentiment: Current market sentiment
            limit: Maximum number of matches to return
            min_similarity: Minimum similarity score (0.0 to 1.0)
            days_back: How many days back to search

        Returns:
            List of SimilarityMatch objects sorted by similarity
        """
        async with self._session_factory() as session:
            # Build query
            query = select(TradeEpisode).where(
                TradeEpisode.entry_timestamp
                >= datetime.now(UTC) - timedelta(days=days_back),
                TradeEpisode.outcome.isnot(None),  # Only completed trades
            )

            if symbol:
                query = query.where(TradeEpisode.symbol == symbol)

            query = query.order_by(TradeEpisode.entry_timestamp.desc()).limit(100)

            result = await session.execute(query)
            episodes = result.scalars().all()

            # Calculate similarity for each episode
            matches = []
            for episode in episodes:
                score, factors = self._calculate_similarity(
                    episode, technical_indicators, market_sentiment
                )

                if score >= min_similarity:
                    matches.append(
                        SimilarityMatch(
                            episode=episode, similarity_score=score, matching_factors=factors
                        )
                    )

            # Sort by similarity and return top matches
            matches.sort(key=lambda x: x.similarity_score, reverse=True)
            return matches[:limit]

    def _calculate_similarity(
        self,
        episode: TradeEpisode,
        technical_indicators: dict | None,
        market_sentiment: str | None,
    ) -> tuple[float, list[str]]:
        """
        Calculate similarity score between current context and a past episode.

        Returns:
            Tuple of (similarity_score, matching_factors)
        """
        score = 0.0
        factors = []

        if technical_indicators and episode.technical_context:
            try:
                past_tech = json.loads(episode.technical_context)
                tech_score = self._compare_technical(technical_indicators, past_tech)
                if tech_score > 0:
                    score += tech_score * 0.5  # Technical has 50% weight
                    factors.append(f"technical_match:{tech_score:.0%}")
            except json.JSONDecodeError:
                logger.warning(
                    "failed_to_parse_technical_context",
                    episode_id=episode.id,
                )

        if market_sentiment and episode.market_context:
            try:
                past_market = json.loads(episode.market_context)
                if past_market.get("sentiment") == market_sentiment:
                    score += 0.3  # Sentiment match has 30% weight
                    factors.append("sentiment_match")
            except json.JSONDecodeError:
                logger.warning(
                    "failed_to_parse_market_context",
                    episode_id=episode.id,
                )

        # Outcome quality bonus
        if episode.outcome == TradeOutcome.WIN:
            score += 0.1
            factors.append("past_winner")
        elif episode.lessons_learned:
            score += 0.1
            factors.append("has_lessons")

        return min(score, 1.0), factors

    def _compare_technical(self, current: dict, past: dict) -> float:
        """Compare technical indicators and return similarity score."""
        if not current or not past:
            return 0.0

        matches = 0
        total = 0

        # Compare RSI zones
        if "rsi" in current and "rsi" in past:
            total += 1
            current_zone = self._get_rsi_zone(current["rsi"])
            past_zone = self._get_rsi_zone(past["rsi"])
            if current_zone == past_zone:
                matches += 1

        # Compare trend direction
        if "trend" in current and "trend" in past:
            total += 1
            if current["trend"] == past["trend"]:
                matches += 1

        # Compare MACD signal
        if "macd_signal" in current and "macd_signal" in past:
            total += 1
            if current["macd_signal"] == past["macd_signal"]:
                matches += 1

        # Compare Bollinger position
        if "bb_position" in current and "bb_position" in past:
            total += 1
            if current["bb_position"] == past["bb_position"]:
                matches += 1

        return matches / total if total > 0 else 0.0

    def _get_rsi_zone(self, rsi: float) -> str:
        """Categorize RSI into zones."""
        if rsi >= 70:
            return "overbought"
        elif rsi <= 30:
            return "oversold"
        elif rsi >= 50:
            return "bullish"
        else:
            return "bearish"

    async def get_recent_episodes(
        self,
        symbol: str | None = None,
        limit: int = 10,
        outcome_filter: TradeOutcome | None = None,
    ) -> list[TradeEpisode]:
        """
        Get recent trade episodes.

        Args:
            symbol: Filter by symbol (optional)
            limit: Maximum number to return
            outcome_filter: Filter by outcome (optional)

        Returns:
            List of TradeEpisode objects
        """
        async with self._session_factory() as session:
            query = select(TradeEpisode)

            if symbol:
                query = query.where(TradeEpisode.symbol == symbol)

            if outcome_filter:
                query = query.where(TradeEpisode.outcome == outcome_filter)

            query = query.order_by(TradeEpisode.entry_timestamp.desc()).limit(limit)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_episode_stats(
        self, symbol: str | None = None, days_back: int = 30
    ) -> dict:
        """
        Get statistics for trade episodes.

        Args:
            symbol: Filter by symbol (optional)
            days_back: How many days back to analyze

        Returns:
            Dictionary with episode statistics
        """
        async with self._session_factory() as session:
            query = select(TradeEpisode).where(
                TradeEpisode.entry_timestamp
                >= datetime.now(UTC) - timedelta(days=days_back),
                TradeEpisode.outcome.isnot(None),
            )

            if symbol:
                query = query.where(TradeEpisode.symbol == symbol)

            result = await session.execute(query)
            episodes = result.scalars().all()

            if not episodes:
                return {
                    "total_episodes": 0,
                    "win_rate": 0.0,
                    "avg_pnl_percentage": 0.0,
                    "avg_confidence": 0.0,
                    "lessons_recorded": 0,
                }

            wins = sum(1 for e in episodes if e.outcome == TradeOutcome.WIN)
            total_pnl = sum(e.pnl_percentage or 0 for e in episodes)
            total_confidence = sum(e.entry_confidence for e in episodes)
            lessons = sum(1 for e in episodes if e.lessons_learned)

            return {
                "total_episodes": len(episodes),
                "win_rate": wins / len(episodes) if episodes else 0.0,
                "avg_pnl_percentage": total_pnl / len(episodes) if episodes else 0.0,
                "avg_confidence": total_confidence / len(episodes) if episodes else 0.0,
                "lessons_recorded": lessons,
                "wins": wins,
                "losses": len(episodes) - wins,
            }


# Global instance
_episodic_memory: EpisodicMemory | None = None


def get_episodic_memory() -> EpisodicMemory:
    """Get the global EpisodicMemory instance."""
    global _episodic_memory
    if _episodic_memory is None:
        from keryxflow.core.database import get_session_factory

        _episodic_memory = EpisodicMemory(get_session_factory())
    return _episodic_memory
