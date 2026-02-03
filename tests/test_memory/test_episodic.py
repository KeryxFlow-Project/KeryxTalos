"""Tests for episodic memory."""

import json

import pytest

from keryxflow.core.database import get_session_factory
from keryxflow.core.models import TradeOutcome
from keryxflow.memory.episodic import EpisodeContext, EpisodicMemory, SimilarityMatch


@pytest.fixture
async def episodic_memory(init_db):
    """Create an episodic memory instance."""
    return EpisodicMemory(get_session_factory())


class TestEpisodeContext:
    """Tests for EpisodeContext dataclass."""

    def test_episode_context_creation(self):
        """Test creating an episode context."""
        context = EpisodeContext(
            trade_id=1,
            symbol="BTC/USDT",
            entry_price=50000.0,
            entry_reasoning="RSI oversold, MACD bullish crossover",
            entry_confidence=0.75,
        )

        assert context.trade_id == 1
        assert context.symbol == "BTC/USDT"
        assert context.entry_price == 50000.0
        assert context.entry_confidence == 0.75

    def test_episode_context_with_optional_fields(self):
        """Test episode context with all optional fields."""
        context = EpisodeContext(
            trade_id=1,
            symbol="BTC/USDT",
            entry_price=50000.0,
            entry_reasoning="Test",
            entry_confidence=0.8,
            technical_context={"rsi": 30, "trend": "bullish"},
            market_context={"sentiment": "bullish"},
            rules_applied=[1, 2, 3],
            tags=["momentum", "oversold"],
        )

        assert context.technical_context == {"rsi": 30, "trend": "bullish"}
        assert context.rules_applied == [1, 2, 3]
        assert context.tags == ["momentum", "oversold"]


class TestSimilarityMatch:
    """Tests for SimilarityMatch dataclass."""

    def test_similarity_match_to_dict(self, init_db):
        """Test converting similarity match to dict."""
        from keryxflow.core.models import TradeEpisode

        episode = TradeEpisode(
            id=1,
            trade_id=1,
            symbol="BTC/USDT",
            entry_price=50000.0,
            entry_reasoning="Test reasoning",
            entry_confidence=0.8,
            outcome=TradeOutcome.WIN,
            pnl_percentage=5.0,
            lessons_learned="Test lesson",
        )

        match = SimilarityMatch(
            episode=episode,
            similarity_score=0.85,
            matching_factors=["technical_match:80%", "sentiment_match"],
        )

        result = match.to_dict()

        assert result["episode_id"] == 1
        assert result["symbol"] == "BTC/USDT"
        assert result["outcome"] == "win"
        assert result["pnl_percentage"] == 5.0
        assert result["similarity_score"] == 0.85
        assert len(result["matching_factors"]) == 2


class TestEpisodicMemory:
    """Tests for EpisodicMemory class."""

    @pytest.mark.asyncio
    async def test_record_entry(self, episodic_memory):
        """Test recording a trade entry."""
        context = EpisodeContext(
            trade_id=1,
            symbol="BTC/USDT",
            entry_price=50000.0,
            entry_reasoning="Strong buy signal from technical analysis",
            entry_confidence=0.8,
            technical_context={"rsi": 28, "macd_signal": "bullish"},
        )

        episode = await episodic_memory.record_entry(context)

        assert episode.id is not None
        assert episode.trade_id == 1
        assert episode.symbol == "BTC/USDT"
        assert episode.entry_price == 50000.0
        assert episode.entry_confidence == 0.8
        assert episode.technical_context is not None
        assert json.loads(episode.technical_context)["rsi"] == 28

    @pytest.mark.asyncio
    async def test_record_exit(self, episodic_memory):
        """Test recording a trade exit."""
        # First create an entry
        context = EpisodeContext(
            trade_id=1,
            symbol="BTC/USDT",
            entry_price=50000.0,
            entry_reasoning="Test entry",
            entry_confidence=0.7,
        )
        episode = await episodic_memory.record_entry(context)

        # Then record exit
        updated = await episodic_memory.record_exit(
            episode_id=episode.id,
            exit_price=52000.0,
            exit_reasoning="Take profit hit",
            outcome=TradeOutcome.TAKE_PROFIT,
            pnl=200.0,
            pnl_percentage=4.0,
            risk_reward_achieved=2.0,
        )

        assert updated is not None
        assert updated.exit_price == 52000.0
        assert updated.outcome == TradeOutcome.TAKE_PROFIT
        assert updated.pnl == 200.0
        assert updated.pnl_percentage == 4.0
        assert updated.risk_reward_achieved == 2.0

    @pytest.mark.asyncio
    async def test_record_exit_not_found(self, episodic_memory):
        """Test recording exit for non-existent episode."""
        result = await episodic_memory.record_exit(
            episode_id=999,
            exit_price=52000.0,
            exit_reasoning="Test",
            outcome=TradeOutcome.WIN,
            pnl=100.0,
            pnl_percentage=2.0,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_record_lessons(self, episodic_memory):
        """Test recording lessons learned."""
        # Create entry
        context = EpisodeContext(
            trade_id=1,
            symbol="BTC/USDT",
            entry_price=50000.0,
            entry_reasoning="Test",
            entry_confidence=0.7,
        )
        episode = await episodic_memory.record_entry(context)

        # Record lessons
        updated = await episodic_memory.record_lessons(
            episode_id=episode.id,
            lessons_learned="Wait for confirmation before entry",
            what_went_well="Entry timing was good",
            what_went_wrong="Exit was too early",
            would_take_again=True,
        )

        assert updated is not None
        assert updated.lessons_learned == "Wait for confirmation before entry"
        assert updated.what_went_well == "Entry timing was good"
        assert updated.would_take_again is True

    @pytest.mark.asyncio
    async def test_get_episode(self, episodic_memory):
        """Test getting episode by ID."""
        context = EpisodeContext(
            trade_id=1,
            symbol="ETH/USDT",
            entry_price=3000.0,
            entry_reasoning="Test",
            entry_confidence=0.6,
        )
        episode = await episodic_memory.record_entry(context)

        retrieved = await episodic_memory.get_episode(episode.id)

        assert retrieved is not None
        assert retrieved.symbol == "ETH/USDT"

    @pytest.mark.asyncio
    async def test_get_episode_by_trade(self, episodic_memory):
        """Test getting episode by trade ID."""
        context = EpisodeContext(
            trade_id=42,
            symbol="BTC/USDT",
            entry_price=50000.0,
            entry_reasoning="Test",
            entry_confidence=0.7,
        )
        await episodic_memory.record_entry(context)

        retrieved = await episodic_memory.get_episode_by_trade(42)

        assert retrieved is not None
        assert retrieved.trade_id == 42

    @pytest.mark.asyncio
    async def test_recall_similar_no_matches(self, episodic_memory):
        """Test recalling similar when no completed trades exist."""
        matches = await episodic_memory.recall_similar(
            symbol="BTC/USDT",
            technical_indicators={"rsi": 30},
        )

        assert matches == []

    @pytest.mark.asyncio
    async def test_recall_similar_with_matches(self, episodic_memory):
        """Test recalling similar past trades."""
        # Create a completed episode
        context = EpisodeContext(
            trade_id=1,
            symbol="BTC/USDT",
            entry_price=50000.0,
            entry_reasoning="RSI oversold",
            entry_confidence=0.8,
            technical_context={"rsi": 28, "trend": "bullish", "macd_signal": "bullish"},
            market_context={"sentiment": "bullish"},
        )
        episode = await episodic_memory.record_entry(context)

        # Complete it
        await episodic_memory.record_exit(
            episode_id=episode.id,
            exit_price=52000.0,
            exit_reasoning="Take profit",
            outcome=TradeOutcome.WIN,
            pnl=200.0,
            pnl_percentage=4.0,
        )

        # Try to recall similar
        matches = await episodic_memory.recall_similar(
            symbol="BTC/USDT",
            technical_indicators={"rsi": 30, "trend": "bullish", "macd_signal": "bullish"},
            market_sentiment="bullish",
            min_similarity=0.2,
        )

        assert len(matches) >= 1
        assert matches[0].episode.symbol == "BTC/USDT"
        assert matches[0].similarity_score > 0

    @pytest.mark.asyncio
    async def test_get_recent_episodes(self, episodic_memory):
        """Test getting recent episodes."""
        # Create multiple episodes
        for i in range(5):
            context = EpisodeContext(
                trade_id=i,
                symbol="BTC/USDT",
                entry_price=50000.0 + i * 100,
                entry_reasoning=f"Test {i}",
                entry_confidence=0.7,
            )
            await episodic_memory.record_entry(context)

        episodes = await episodic_memory.get_recent_episodes(limit=3)

        assert len(episodes) == 3

    @pytest.mark.asyncio
    async def test_get_recent_episodes_with_filter(self, episodic_memory):
        """Test getting recent episodes with outcome filter."""
        # Create winning episode
        context1 = EpisodeContext(
            trade_id=1,
            symbol="BTC/USDT",
            entry_price=50000.0,
            entry_reasoning="Test win",
            entry_confidence=0.7,
        )
        ep1 = await episodic_memory.record_entry(context1)
        await episodic_memory.record_exit(
            episode_id=ep1.id,
            exit_price=52000.0,
            exit_reasoning="Win",
            outcome=TradeOutcome.WIN,
            pnl=200.0,
            pnl_percentage=4.0,
        )

        # Create losing episode
        context2 = EpisodeContext(
            trade_id=2,
            symbol="BTC/USDT",
            entry_price=50000.0,
            entry_reasoning="Test loss",
            entry_confidence=0.7,
        )
        ep2 = await episodic_memory.record_entry(context2)
        await episodic_memory.record_exit(
            episode_id=ep2.id,
            exit_price=49000.0,
            exit_reasoning="Loss",
            outcome=TradeOutcome.LOSS,
            pnl=-100.0,
            pnl_percentage=-2.0,
        )

        # Get only wins
        wins = await episodic_memory.get_recent_episodes(outcome_filter=TradeOutcome.WIN)

        assert len(wins) == 1
        assert wins[0].outcome == TradeOutcome.WIN

    @pytest.mark.asyncio
    async def test_get_episode_stats_empty(self, episodic_memory):
        """Test episode stats with no episodes."""
        stats = await episodic_memory.get_episode_stats()

        assert stats["total_episodes"] == 0
        assert stats["win_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_get_episode_stats(self, episodic_memory):
        """Test episode statistics calculation."""
        # Create episodes with different outcomes
        for i in range(10):
            context = EpisodeContext(
                trade_id=i,
                symbol="BTC/USDT",
                entry_price=50000.0,
                entry_reasoning=f"Test {i}",
                entry_confidence=0.7,
            )
            ep = await episodic_memory.record_entry(context)

            outcome = TradeOutcome.WIN if i < 6 else TradeOutcome.LOSS
            pnl_pct = 5.0 if outcome == TradeOutcome.WIN else -2.0

            await episodic_memory.record_exit(
                episode_id=ep.id,
                exit_price=50000.0,
                exit_reasoning="Test",
                outcome=outcome,
                pnl=pnl_pct * 10,
                pnl_percentage=pnl_pct,
            )

        stats = await episodic_memory.get_episode_stats()

        assert stats["total_episodes"] == 10
        assert stats["wins"] == 6
        assert stats["losses"] == 4
        assert stats["win_rate"] == 0.6


class TestEpisodicMemorySimilarity:
    """Tests for similarity calculation."""

    def test_get_rsi_zone_overbought(self, episodic_memory):
        """Test RSI zone classification - overbought."""
        assert episodic_memory._get_rsi_zone(75) == "overbought"
        assert episodic_memory._get_rsi_zone(70) == "overbought"

    def test_get_rsi_zone_oversold(self, episodic_memory):
        """Test RSI zone classification - oversold."""
        assert episodic_memory._get_rsi_zone(25) == "oversold"
        assert episodic_memory._get_rsi_zone(30) == "oversold"

    def test_get_rsi_zone_bullish(self, episodic_memory):
        """Test RSI zone classification - bullish."""
        assert episodic_memory._get_rsi_zone(60) == "bullish"
        assert episodic_memory._get_rsi_zone(50) == "bullish"

    def test_get_rsi_zone_bearish(self, episodic_memory):
        """Test RSI zone classification - bearish."""
        assert episodic_memory._get_rsi_zone(40) == "bearish"
        assert episodic_memory._get_rsi_zone(31) == "bearish"

    def test_compare_technical_matching(self, episodic_memory):
        """Test technical comparison with matching indicators."""
        current = {
            "rsi": 28,
            "trend": "bullish",
            "macd_signal": "bullish",
            "bb_position": "lower",
        }
        past = {
            "rsi": 25,  # Same zone (oversold)
            "trend": "bullish",
            "macd_signal": "bullish",
            "bb_position": "lower",
        }

        score = episodic_memory._compare_technical(current, past)
        assert score == 1.0  # All match

    def test_compare_technical_partial_match(self, episodic_memory):
        """Test technical comparison with partial match."""
        current = {"rsi": 28, "trend": "bullish"}
        past = {"rsi": 75, "trend": "bullish"}  # Different RSI zone

        score = episodic_memory._compare_technical(current, past)
        assert score == 0.5  # One of two matches

    def test_compare_technical_empty(self, episodic_memory):
        """Test technical comparison with empty data."""
        assert episodic_memory._compare_technical({}, {}) == 0.0
        assert episodic_memory._compare_technical(None, None) == 0.0
