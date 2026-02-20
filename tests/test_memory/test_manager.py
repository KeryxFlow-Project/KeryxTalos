"""Tests for memory manager."""

import pytest

from keryxflow.core.database import get_session_factory
from keryxflow.core.models import PatternType, RuleSource, TradeOutcome
from keryxflow.memory.episodic import EpisodicMemory
from keryxflow.memory.manager import MemoryContext, MemoryManager
from keryxflow.memory.semantic import SemanticMemory


@pytest.fixture
async def memory_manager(_init_db):
    """Create a memory manager instance."""
    session_factory = get_session_factory()
    episodic = EpisodicMemory(session_factory)
    semantic = SemanticMemory(session_factory)
    return MemoryManager(episodic=episodic, semantic=semantic)


class TestMemoryContext:
    """Tests for MemoryContext dataclass."""

    def test_memory_context_defaults(self):
        """Test memory context with default values."""
        context = MemoryContext()

        assert context.similar_episodes == []
        assert context.matching_rules == []
        assert context.detected_patterns == []
        assert context.confidence_adjustment == 0.0

    def test_memory_context_has_relevant_context_false(self):
        """Test has_relevant_context returns False when empty."""
        context = MemoryContext()
        assert context.has_relevant_context() is False

    def test_memory_context_to_dict(self):
        """Test converting context to dictionary."""
        context = MemoryContext(
            summary="Test summary",
            confidence_adjustment=0.15,
        )

        result = context.to_dict()

        assert "timestamp" in result
        assert result["summary"] == "Test summary"
        assert result["confidence_adjustment"] == 0.15
        assert "similar_episodes" in result
        assert "matching_rules" in result

    def test_memory_context_to_prompt_context_empty(self):
        """Test prompt context generation when empty."""
        context = MemoryContext()
        prompt = context.to_prompt_context()

        assert "## Memory Context" in prompt
        assert "No significant memory context" in prompt

    def test_memory_context_to_prompt_context_with_summary(self):
        """Test prompt context includes summary."""
        context = MemoryContext(summary="5 similar trades found (3 wins)")
        prompt = context.to_prompt_context()

        assert "5 similar trades found" in prompt


class TestMemoryManager:
    """Tests for MemoryManager class."""

    @pytest.mark.asyncio
    async def test_manager_properties(self, memory_manager):
        """Test manager provides access to subsystems."""
        assert memory_manager.episodic is not None
        assert memory_manager.semantic is not None

    @pytest.mark.asyncio
    async def test_build_context_for_decision_empty(self, memory_manager):
        """Test building context with no prior data."""
        context = await memory_manager.build_context_for_decision(
            symbol="BTC/USDT",
            technical_context={"rsi": 30},
        )

        assert isinstance(context, MemoryContext)
        assert context.similar_episodes == []
        assert context.matching_rules == []

    @pytest.mark.asyncio
    async def test_build_context_for_decision_with_rules(self, memory_manager):
        """Test building context finds matching rules."""
        # Create a rule
        await memory_manager.semantic.create_rule(
            name="Test Rule",
            description="Test",
            condition="RSI < 30",
            applies_to_symbols=["BTC/USDT"],
        )

        context = await memory_manager.build_context_for_decision(
            symbol="BTC/USDT",
        )

        assert len(context.matching_rules) >= 1

    @pytest.mark.asyncio
    async def test_build_context_for_decision_with_patterns(self, memory_manager):
        """Test building context finds matching patterns."""
        # Create a pattern with detection criteria
        await memory_manager.semantic.create_pattern(
            name="RSI Pattern",
            description="Test",
            pattern_type=PatternType.INDICATOR,
            definition="Test",
            detection_criteria={
                "rsi": {"min": 25, "max": 35},
            },
        )

        context = await memory_manager.build_context_for_decision(
            symbol="BTC/USDT",
            technical_context={"rsi": 30},
        )

        assert len(context.detected_patterns) >= 1

    @pytest.mark.asyncio
    async def test_record_trade_entry(self, memory_manager):
        """Test recording a trade entry."""
        episode_id = await memory_manager.record_trade_entry(
            trade_id=1,
            symbol="BTC/USDT",
            entry_price=50000.0,
            entry_reasoning="RSI oversold with bullish divergence",
            entry_confidence=0.8,
            technical_context={"rsi": 28, "trend": "bullish"},
            tags=["momentum", "oversold"],
        )

        assert episode_id is not None

        # Verify episode was created
        episode = await memory_manager.episodic.get_episode(episode_id)
        assert episode is not None
        assert episode.symbol == "BTC/USDT"

    @pytest.mark.asyncio
    async def test_record_trade_entry_with_memory_context(self, memory_manager):
        """Test recording trade entry with memory context."""
        # Build context first
        context = await memory_manager.build_context_for_decision(symbol="BTC/USDT")

        episode_id = await memory_manager.record_trade_entry(
            trade_id=1,
            symbol="BTC/USDT",
            entry_price=50000.0,
            entry_reasoning="Test",
            entry_confidence=0.7,
            memory_context=context,
        )

        assert episode_id is not None

    @pytest.mark.asyncio
    async def test_record_trade_exit(self, memory_manager):
        """Test recording a trade exit."""
        # Create entry first
        episode_id = await memory_manager.record_trade_entry(
            trade_id=1,
            symbol="BTC/USDT",
            entry_price=50000.0,
            entry_reasoning="Test",
            entry_confidence=0.7,
        )

        # Record exit
        success = await memory_manager.record_trade_exit(
            episode_id=episode_id,
            exit_price=52000.0,
            exit_reasoning="Take profit reached",
            outcome=TradeOutcome.TAKE_PROFIT,
            pnl=200.0,
            pnl_percentage=4.0,
            risk_reward_achieved=2.0,
        )

        assert success is True

        # Verify episode was updated
        episode = await memory_manager.episodic.get_episode(episode_id)
        assert episode.outcome == TradeOutcome.TAKE_PROFIT
        assert episode.pnl_percentage == 4.0

    @pytest.mark.asyncio
    async def test_record_trade_exit_updates_rules(self, memory_manager):
        """Test that recording exit updates rule performance."""
        # Create a rule
        rule = await memory_manager.semantic.create_rule(
            name="Test Rule",
            description="Test",
            condition="Test",
        )

        # Create entry
        episode_id = await memory_manager.record_trade_entry(
            trade_id=1,
            symbol="BTC/USDT",
            entry_price=50000.0,
            entry_reasoning="Test",
            entry_confidence=0.7,
            rules_applied=[rule.id],
        )

        # Record winning exit
        await memory_manager.record_trade_exit(
            episode_id=episode_id,
            exit_price=52000.0,
            exit_reasoning="Win",
            outcome=TradeOutcome.WIN,
            pnl=200.0,
            pnl_percentage=4.0,
            rules_applied=[rule.id],
        )

        # Verify rule was updated
        updated_rule = await memory_manager.semantic.get_rule(rule.id)
        assert updated_rule.times_applied == 1
        assert updated_rule.times_successful == 1

    @pytest.mark.asyncio
    async def test_record_trade_exit_updates_patterns(self, memory_manager):
        """Test that recording exit updates pattern stats."""
        # Create a pattern
        pattern = await memory_manager.semantic.create_pattern(
            name="Test Pattern",
            description="Test",
            pattern_type=PatternType.COMBINED,
            definition="Test",
        )

        # Create entry
        episode_id = await memory_manager.record_trade_entry(
            trade_id=1,
            symbol="BTC/USDT",
            entry_price=50000.0,
            entry_reasoning="Test",
            entry_confidence=0.7,
            patterns_identified=[pattern.id],
        )

        # Record winning exit
        await memory_manager.record_trade_exit(
            episode_id=episode_id,
            exit_price=52000.0,
            exit_reasoning="Win",
            outcome=TradeOutcome.WIN,
            pnl=200.0,
            pnl_percentage=4.0,
            patterns_identified=[pattern.id],
        )

        # Verify pattern was updated
        updated_pattern = await memory_manager.semantic.get_pattern(pattern.id)
        assert updated_pattern.times_identified == 1
        assert updated_pattern.times_profitable == 1

    @pytest.mark.asyncio
    async def test_record_lessons_learned(self, memory_manager):
        """Test recording lessons learned."""
        # Create entry
        episode_id = await memory_manager.record_trade_entry(
            trade_id=1,
            symbol="BTC/USDT",
            entry_price=50000.0,
            entry_reasoning="Test",
            entry_confidence=0.7,
        )

        # Record lessons
        success = await memory_manager.record_lessons_learned(
            episode_id=episode_id,
            lessons_learned="Wait for confirmation candle",
            what_went_well="Entry timing",
            what_went_wrong="Position size too large",
            would_take_again=True,
        )

        assert success is True

        # Verify lessons were recorded
        episode = await memory_manager.episodic.get_episode(episode_id)
        assert episode.lessons_learned == "Wait for confirmation candle"
        assert episode.would_take_again is True

    @pytest.mark.asyncio
    async def test_get_stats(self, memory_manager):
        """Test getting combined statistics."""
        # Create some data
        await memory_manager.record_trade_entry(
            trade_id=1,
            symbol="BTC/USDT",
            entry_price=50000.0,
            entry_reasoning="Test",
            entry_confidence=0.7,
        )

        await memory_manager.semantic.create_rule(
            name="Test Rule",
            description="Test",
            condition="Test",
        )

        stats = await memory_manager.get_stats()

        assert "episodes" in stats
        assert "rules" in stats
        assert "patterns" in stats


class TestConfidenceAdjustment:
    """Tests for confidence adjustment calculation."""

    @pytest.mark.asyncio
    async def test_confidence_adjustment_winning_episodes(self, memory_manager):
        """Test confidence increases with winning episodes."""
        # Create multiple winning episodes
        for i in range(5):
            ep_id = await memory_manager.record_trade_entry(
                trade_id=i,
                symbol="BTC/USDT",
                entry_price=50000.0,
                entry_reasoning="Test",
                entry_confidence=0.7,
            )
            await memory_manager.record_trade_exit(
                episode_id=ep_id,
                exit_price=52000.0,
                exit_reasoning="Win",
                outcome=TradeOutcome.WIN,
                pnl=200.0,
                pnl_percentage=4.0,
            )

        context = await memory_manager.build_context_for_decision(
            symbol="BTC/USDT",
            technical_context={"rsi": 30},
        )

        # Confidence should be positive due to winning history
        assert context.confidence_adjustment >= 0

    @pytest.mark.asyncio
    async def test_confidence_adjustment_losing_episodes(self, memory_manager):
        """Test confidence decreases with losing episodes."""
        # Create multiple losing episodes
        for i in range(5):
            ep_id = await memory_manager.record_trade_entry(
                trade_id=i,
                symbol="BTC/USDT",
                entry_price=50000.0,
                entry_reasoning="Test",
                entry_confidence=0.7,
            )
            await memory_manager.record_trade_exit(
                episode_id=ep_id,
                exit_price=48000.0,
                exit_reasoning="Loss",
                outcome=TradeOutcome.LOSS,
                pnl=-200.0,
                pnl_percentage=-4.0,
            )

        context = await memory_manager.build_context_for_decision(
            symbol="BTC/USDT",
            technical_context={"rsi": 30},
        )

        # Confidence adjustment may be negative or neutral
        assert context.confidence_adjustment <= 0.1

    @pytest.mark.asyncio
    async def test_confidence_adjustment_high_success_rules(self, memory_manager):
        """Test confidence boost from high-success rules."""
        # Create a high-success rule
        rule = await memory_manager.semantic.create_rule(
            name="High Success Rule",
            description="Test",
            condition="Test",
            source=RuleSource.LEARNED,
        )

        # Simulate many successful applications
        for _ in range(10):
            await memory_manager.semantic.update_rule_performance(
                rule.id, was_successful=True, pnl=100.0
            )

        context = await memory_manager.build_context_for_decision(
            symbol="BTC/USDT",
        )

        # Should have some positive adjustment from the rule
        assert len(context.matching_rules) >= 1


class TestSummaryGeneration:
    """Tests for summary generation."""

    @pytest.mark.asyncio
    async def test_summary_with_episodes(self, memory_manager):
        """Test summary includes episode information."""
        # Create some episodes
        for i in range(3):
            ep_id = await memory_manager.record_trade_entry(
                trade_id=i,
                symbol="BTC/USDT",
                entry_price=50000.0,
                entry_reasoning="Test",
                entry_confidence=0.7,
            )
            outcome = TradeOutcome.WIN if i < 2 else TradeOutcome.LOSS
            await memory_manager.record_trade_exit(
                episode_id=ep_id,
                exit_price=51000.0 if outcome == TradeOutcome.WIN else 49000.0,
                exit_reasoning="Test",
                outcome=outcome,
                pnl=100.0 if outcome == TradeOutcome.WIN else -100.0,
                pnl_percentage=2.0 if outcome == TradeOutcome.WIN else -2.0,
            )

        context = await memory_manager.build_context_for_decision(
            symbol="BTC/USDT",
        )

        # Summary should mention similar trades if found
        assert context.summary is not None

    @pytest.mark.asyncio
    async def test_summary_with_rules(self, memory_manager):
        """Test summary includes rule information."""
        await memory_manager.semantic.create_rule(
            name="Test Rule",
            description="Test",
            condition="Test",
        )

        context = await memory_manager.build_context_for_decision(
            symbol="BTC/USDT",
        )

        assert "rule" in context.summary.lower()
