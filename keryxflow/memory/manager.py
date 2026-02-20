"""Memory manager - unified interface for all memory systems."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from keryxflow.core.logging import get_logger
from keryxflow.core.models import TradeOutcome
from keryxflow.memory.episodic import (
    EpisodeContext,
    EpisodicMemory,
    SimilarityMatch,
    get_episodic_memory,
)
from keryxflow.memory.semantic import (
    PatternMatch,
    RuleMatch,
    SemanticMemory,
    get_semantic_memory,
)

logger = get_logger(__name__)


@dataclass
class MemoryContext:
    """
    Complete memory context for a trading decision.

    Combines episodic memory (past trades) with semantic memory (rules/patterns)
    to provide full context for decision making.
    """

    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Similar past trades
    similar_episodes: list[SimilarityMatch] = field(default_factory=list)

    # Applicable rules
    matching_rules: list[RuleMatch] = field(default_factory=list)

    # Detected patterns
    detected_patterns: list[PatternMatch] = field(default_factory=list)

    # Statistics
    episode_stats: dict = field(default_factory=dict)
    rule_stats: dict = field(default_factory=dict)
    pattern_stats: dict = field(default_factory=dict)

    # Summary
    summary: str = ""
    confidence_adjustment: float = 0.0  # Adjustment to decision confidence

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "similar_episodes": [e.to_dict() for e in self.similar_episodes],
            "matching_rules": [r.to_dict() for r in self.matching_rules],
            "detected_patterns": [p.to_dict() for p in self.detected_patterns],
            "episode_stats": self.episode_stats,
            "rule_stats": self.rule_stats,
            "pattern_stats": self.pattern_stats,
            "summary": self.summary,
            "confidence_adjustment": self.confidence_adjustment,
        }

    def to_prompt_context(self) -> str:
        """
        Format memory context for LLM prompt.

        Returns a concise, readable summary for inclusion in prompts.
        """
        lines = ["## Memory Context\n"]

        # Similar past trades
        if self.similar_episodes:
            lines.append("### Similar Past Trades")
            for match in self.similar_episodes[:3]:  # Top 3
                ep = match.episode
                outcome_str = ep.outcome.value if ep.outcome else "pending"
                pnl_str = f"{ep.pnl_percentage:+.1f}%" if ep.pnl_percentage else "N/A"
                lines.append(
                    f"- {ep.symbol} ({outcome_str}, {pnl_str}): " f"{ep.entry_reasoning[:100]}..."
                )
                if ep.lessons_learned:
                    lines.append(f"  Lesson: {ep.lessons_learned[:100]}...")
            lines.append("")

        # Active rules
        if self.matching_rules:
            lines.append("### Applicable Rules")
            for match in self.matching_rules[:5]:  # Top 5
                rule = match.rule
                success_str = f"{rule.success_rate:.0%}" if rule.times_applied > 0 else "new"
                lines.append(
                    f"- [{rule.category}] {rule.name} (success: {success_str}): "
                    f"{rule.condition}"
                )
            lines.append("")

        # Detected patterns
        if self.detected_patterns:
            lines.append("### Detected Patterns")
            for match in self.detected_patterns[:3]:  # Top 3
                pattern = match.pattern
                win_str = f"{pattern.win_rate:.0%}" if pattern.times_identified > 0 else "new"
                lines.append(
                    f"- {pattern.name} (win rate: {win_str}, confidence: {match.confidence:.0%}): "
                    f"{pattern.description[:100]}..."
                )
            lines.append("")

        # Statistics summary
        if self.episode_stats.get("total_episodes", 0) > 0:
            stats = self.episode_stats
            lines.append("### Performance Summary")
            lines.append(
                f"- Recent trades: {stats['total_episodes']} "
                f"(Win rate: {stats['win_rate']:.0%}, "
                f"Avg PnL: {stats['avg_pnl_percentage']:+.2f}%)"
            )
            lines.append("")

        if self.summary:
            lines.append(f"**Summary**: {self.summary}")
        elif not self.has_relevant_context():
            lines.append("No significant memory context")

        return "\n".join(lines)

    def has_relevant_context(self) -> bool:
        """Check if there's any relevant memory context."""
        return bool(self.similar_episodes or self.matching_rules or self.detected_patterns)


class MemoryManager:
    """
    Unified memory manager combining episodic and semantic memory.

    Provides a single interface for:
    - Building context for trading decisions
    - Recording trade episodes with full context
    - Updating rules and patterns based on outcomes
    - Learning from trading experience
    """

    def __init__(
        self,
        episodic: EpisodicMemory | None = None,
        semantic: SemanticMemory | None = None,
    ):
        """Initialize memory manager."""
        self._episodic = episodic or get_episodic_memory()
        self._semantic = semantic or get_semantic_memory()

    @property
    def episodic(self) -> EpisodicMemory:
        """Get episodic memory."""
        return self._episodic

    @property
    def semantic(self) -> SemanticMemory:
        """Get semantic memory."""
        return self._semantic

    async def build_context_for_decision(
        self,
        symbol: str,
        technical_context: dict | None = None,
        market_sentiment: str | None = None,
        timeframe: str | None = None,
    ) -> MemoryContext:
        """
        Build complete memory context for a trading decision.

        This is the main method for getting memory-augmented context
        before making a trading decision.

        Args:
            symbol: Trading symbol
            technical_context: Current technical analysis data
            market_sentiment: Current market sentiment (bullish/bearish/neutral)
            timeframe: Current timeframe

        Returns:
            MemoryContext with all relevant memory information
        """
        context = MemoryContext()

        # 1. Recall similar past trades
        try:
            context.similar_episodes = await self._episodic.recall_similar(
                symbol=symbol,
                technical_indicators=technical_context,
                market_sentiment=market_sentiment,
                limit=5,
            )
        except Exception as e:
            logger.warning("failed_to_recall_episodes", error=str(e))

        # 2. Get matching rules
        try:
            context.matching_rules = await self._semantic.get_matching_rules(
                symbol=symbol,
                market_condition=market_sentiment,
                timeframe=timeframe,
            )
        except Exception as e:
            logger.warning("failed_to_get_rules", error=str(e))

        # 3. Find matching patterns
        if technical_context:
            try:
                context.detected_patterns = await self._semantic.find_matching_patterns(
                    technical_context=technical_context,
                    symbol=symbol,
                    timeframe=timeframe,
                )
            except Exception as e:
                logger.warning("failed_to_find_patterns", error=str(e))

        # 4. Get statistics
        try:
            context.episode_stats = await self._episodic.get_episode_stats(
                symbol=symbol, days_back=30
            )
            context.rule_stats = await self._semantic.get_rule_stats()
            context.pattern_stats = await self._semantic.get_pattern_stats()
        except Exception as e:
            logger.warning("failed_to_get_stats", error=str(e))

        # 5. Calculate confidence adjustment and summary
        context.confidence_adjustment = self._calculate_confidence_adjustment(context)
        context.summary = self._generate_summary(context)

        logger.debug(
            "memory_context_built",
            symbol=symbol,
            similar_episodes=len(context.similar_episodes),
            matching_rules=len(context.matching_rules),
            detected_patterns=len(context.detected_patterns),
            confidence_adjustment=context.confidence_adjustment,
        )

        return context

    def _calculate_confidence_adjustment(self, context: MemoryContext) -> float:
        """
        Calculate confidence adjustment based on memory context.

        Positive adjustments increase confidence, negative decrease it.
        """
        adjustment = 0.0

        # Similar episodes adjustment
        if context.similar_episodes:
            winning_episodes = sum(
                1 for e in context.similar_episodes if e.episode.outcome == TradeOutcome.WIN
            )
            losing_episodes = sum(
                1 for e in context.similar_episodes if e.episode.outcome == TradeOutcome.LOSS
            )

            if winning_episodes > losing_episodes:
                adjustment += 0.1 * (winning_episodes - losing_episodes)
            elif losing_episodes > winning_episodes:
                adjustment -= 0.1 * (losing_episodes - winning_episodes)

        # High-confidence rules adjustment
        for match in context.matching_rules[:3]:
            if match.rule.success_rate > 0.6 and match.rule.times_applied >= 5:
                adjustment += 0.05

        # Validated patterns adjustment
        for match in context.detected_patterns[:3]:
            if match.pattern.is_validated and match.pattern.win_rate > 0.5:
                adjustment += 0.05 * match.confidence

        # Recent performance adjustment
        if context.episode_stats.get("total_episodes", 0) >= 10:
            win_rate = context.episode_stats.get("win_rate", 0.5)
            if win_rate > 0.6:
                adjustment += 0.1
            elif win_rate < 0.4:
                adjustment -= 0.1

        # Clamp adjustment
        return max(-0.3, min(0.3, adjustment))

    def _generate_summary(self, context: MemoryContext) -> str:
        """Generate a human-readable summary of the memory context."""
        parts = []

        # Similar trades summary
        if context.similar_episodes:
            wins = sum(1 for e in context.similar_episodes if e.episode.outcome == TradeOutcome.WIN)
            total = len(context.similar_episodes)
            parts.append(f"{total} similar trades found ({wins} wins)")

        # Rules summary
        if context.matching_rules:
            high_success = sum(1 for r in context.matching_rules if r.rule.success_rate > 0.6)
            parts.append(f"{len(context.matching_rules)} rules apply ({high_success} high success)")

        # Patterns summary
        if context.detected_patterns:
            validated = sum(1 for p in context.detected_patterns if p.pattern.is_validated)
            parts.append(
                f"{len(context.detected_patterns)} patterns detected ({validated} validated)"
            )

        # Confidence
        if context.confidence_adjustment > 0.1:
            parts.append("Memory suggests increased confidence")
        elif context.confidence_adjustment < -0.1:
            parts.append("Memory suggests caution")

        return "; ".join(parts) if parts else "No significant memory context"

    async def record_trade_entry(
        self,
        trade_id: int,
        symbol: str,
        entry_price: float,
        entry_reasoning: str,
        entry_confidence: float,
        technical_context: dict | None = None,
        market_context: dict | None = None,
        memory_context: MemoryContext | None = None,
        rules_applied: list[int] | None = None,
        patterns_identified: list[int] | None = None,
        tags: list[str] | None = None,
    ) -> int | None:
        """
        Record a trade entry as a new episode.

        Args:
            trade_id: ID of the trade
            symbol: Trading symbol
            entry_price: Entry price
            entry_reasoning: Why the trade was taken
            entry_confidence: Confidence level
            technical_context: Technical analysis data
            market_context: Market context data
            memory_context: Memory context used for decision
            rules_applied: IDs of rules that led to this trade
            patterns_identified: IDs of patterns detected
            tags: Tags for categorization

        Returns:
            Episode ID or None if failed
        """
        episode_context = EpisodeContext(
            trade_id=trade_id,
            symbol=symbol,
            entry_price=entry_price,
            entry_reasoning=entry_reasoning,
            entry_confidence=entry_confidence,
            technical_context=technical_context,
            market_context=market_context,
            memory_context=memory_context.to_dict() if memory_context else None,
            rules_applied=rules_applied,
            patterns_identified=patterns_identified,
            tags=tags,
        )

        try:
            episode = await self._episodic.record_entry(episode_context)
            return episode.id
        except Exception as e:
            logger.error("failed_to_record_episode", error=str(e))
            return None

    async def record_trade_exit(
        self,
        episode_id: int,
        exit_price: float,
        exit_reasoning: str,
        outcome: TradeOutcome,
        pnl: float,
        pnl_percentage: float,
        risk_reward_achieved: float | None = None,
        rules_applied: list[int] | None = None,
        patterns_identified: list[int] | None = None,
    ) -> bool:
        """
        Record a trade exit and update related rules/patterns.

        Args:
            episode_id: ID of the episode to update
            exit_price: Exit price
            exit_reasoning: Why the trade was closed
            outcome: Trade outcome
            pnl: Profit/loss amount
            pnl_percentage: Profit/loss percentage
            risk_reward_achieved: Achieved risk/reward ratio
            rules_applied: IDs of rules applied (to update performance)
            patterns_identified: IDs of patterns identified (to update stats)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Record episode exit
            episode = await self._episodic.record_exit(
                episode_id=episode_id,
                exit_price=exit_price,
                exit_reasoning=exit_reasoning,
                outcome=outcome,
                pnl=pnl,
                pnl_percentage=pnl_percentage,
                risk_reward_achieved=risk_reward_achieved,
            )

            if episode is None:
                return False

            # Update rule performance
            was_successful = outcome in (TradeOutcome.WIN, TradeOutcome.TAKE_PROFIT)
            if rules_applied:
                for rule_id in rules_applied:
                    await self._semantic.update_rule_performance(
                        rule_id=rule_id,
                        was_successful=was_successful,
                        pnl=pnl,
                    )

            # Update pattern statistics
            if patterns_identified and episode.entry_timestamp and episode.exit_timestamp:
                duration_hours = (
                    episode.exit_timestamp - episode.entry_timestamp
                ).total_seconds() / 3600
                for pattern_id in patterns_identified:
                    await self._semantic.update_pattern_stats(
                        pattern_id=pattern_id,
                        was_profitable=was_successful,
                        return_pct=pnl_percentage,
                        duration_hours=duration_hours,
                    )

            logger.info(
                "trade_exit_recorded",
                episode_id=episode_id,
                outcome=outcome.value,
                pnl_percentage=pnl_percentage,
            )

            return True

        except Exception as e:
            logger.error("failed_to_record_exit", error=str(e))
            return False

    async def record_lessons_learned(
        self,
        episode_id: int,
        lessons_learned: str,
        what_went_well: str | None = None,
        what_went_wrong: str | None = None,
        would_take_again: bool | None = None,
    ) -> bool:
        """
        Record lessons learned from a trade.

        Args:
            episode_id: ID of the episode
            lessons_learned: Main lessons from the trade
            what_went_well: What worked well
            what_went_wrong: What could be improved
            would_take_again: Whether trader would repeat this trade

        Returns:
            True if successful, False otherwise
        """
        try:
            episode = await self._episodic.record_lessons(
                episode_id=episode_id,
                lessons_learned=lessons_learned,
                what_went_well=what_went_well,
                what_went_wrong=what_went_wrong,
                would_take_again=would_take_again,
            )
            return episode is not None
        except Exception as e:
            logger.error("failed_to_record_lessons", error=str(e))
            return False

    async def get_stats(self) -> dict:
        """Get combined statistics from all memory systems."""
        episode_stats = await self._episodic.get_episode_stats()
        rule_stats = await self._semantic.get_rule_stats()
        pattern_stats = await self._semantic.get_pattern_stats()

        return {
            "episodes": episode_stats,
            "rules": rule_stats,
            "patterns": pattern_stats,
        }


# Global instance
_memory_manager: MemoryManager | None = None


def get_memory_manager() -> MemoryManager:
    """Get the global MemoryManager instance."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager
