"""Semantic memory for trading rules and market patterns."""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlmodel import select

from keryxflow.core.logging import get_logger
from keryxflow.core.models import (
    MarketPattern,
    PatternType,
    RuleSource,
    RuleStatus,
    TradingRule,
)

logger = get_logger(__name__)


@dataclass
class RuleMatch:
    """A matching rule for the current context."""

    rule: TradingRule
    relevance_score: float  # 0.0 to 1.0
    reason: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "rule_id": self.rule.id,
            "name": self.rule.name,
            "description": self.rule.description,
            "condition": self.rule.condition,
            "success_rate": self.rule.success_rate,
            "relevance_score": self.relevance_score,
            "reason": self.reason,
        }


@dataclass
class PatternMatch:
    """A matching pattern for the current context."""

    pattern: MarketPattern
    confidence: float  # 0.0 to 1.0
    match_details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "pattern_id": self.pattern.id,
            "name": self.pattern.name,
            "description": self.pattern.description,
            "pattern_type": self.pattern.pattern_type.value,
            "win_rate": self.pattern.win_rate,
            "avg_return": self.pattern.avg_return,
            "confidence": self.confidence,
            "match_details": self.match_details,
        }


class SemanticMemory:
    """
    Semantic memory for managing trading rules and patterns.

    Provides functionality to:
    - Store and retrieve trading rules
    - Track rule performance
    - Store and match market patterns
    - Get active rules for decision making
    """

    def __init__(self, session_factory):
        """Initialize semantic memory."""
        self._session_factory = session_factory

    # =========================================================================
    # Trading Rules
    # =========================================================================

    async def create_rule(
        self,
        name: str,
        description: str,
        condition: str,
        source: RuleSource = RuleSource.LEARNED,
        category: str = "general",
        priority: int = 0,
        applies_to_symbols: list[str] | None = None,
        applies_to_timeframes: list[str] | None = None,
        applies_to_market_conditions: dict | None = None,
        learned_from_episodes: list[int] | None = None,
    ) -> TradingRule:
        """
        Create a new trading rule.

        Args:
            name: Rule name
            description: Rule description
            condition: Human-readable condition
            source: Where the rule came from
            category: Rule category (entry, exit, risk, etc.)
            priority: Rule priority (higher = more important)
            applies_to_symbols: Symbols this rule applies to
            applies_to_timeframes: Timeframes this rule applies to
            applies_to_market_conditions: Market conditions for applicability
            learned_from_episodes: Episode IDs that led to this rule

        Returns:
            Created TradingRule
        """
        async with self._session_factory() as session:
            rule = TradingRule(
                name=name,
                description=description,
                condition=condition,
                source=source,
                category=category,
                priority=priority,
                applies_to_symbols=(
                    json.dumps(applies_to_symbols) if applies_to_symbols else None
                ),
                applies_to_timeframes=(
                    json.dumps(applies_to_timeframes) if applies_to_timeframes else None
                ),
                applies_to_market_conditions=(
                    json.dumps(applies_to_market_conditions)
                    if applies_to_market_conditions
                    else None
                ),
                learned_from_episodes=(
                    json.dumps(learned_from_episodes) if learned_from_episodes else None
                ),
            )

            session.add(rule)
            await session.commit()
            await session.refresh(rule)

            logger.info(
                "rule_created",
                rule_id=rule.id,
                name=name,
                source=source.value,
                category=category,
            )

            return rule

    async def get_rule(self, rule_id: int) -> TradingRule | None:
        """Get a specific rule by ID."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(TradingRule).where(TradingRule.id == rule_id)
            )
            return result.scalar_one_or_none()

    async def get_active_rules(
        self,
        category: str | None = None,
        symbol: str | None = None,
        min_success_rate: float = 0.0,
    ) -> list[TradingRule]:
        """
        Get all active rules, optionally filtered.

        Args:
            category: Filter by category
            symbol: Filter by applicable symbol
            min_success_rate: Minimum success rate

        Returns:
            List of active TradingRule objects
        """
        async with self._session_factory() as session:
            query = select(TradingRule).where(TradingRule.status == RuleStatus.ACTIVE)

            if category:
                query = query.where(TradingRule.category == category)

            if min_success_rate > 0:
                query = query.where(TradingRule.success_rate >= min_success_rate)

            query = query.order_by(TradingRule.priority.desc())

            result = await session.execute(query)
            rules = result.scalars().all()

            # Filter by symbol if provided
            if symbol:
                filtered = []
                for rule in rules:
                    if rule.applies_to_symbols is None:
                        filtered.append(rule)
                    else:
                        try:
                            symbols = json.loads(rule.applies_to_symbols)
                            if symbol in symbols:
                                filtered.append(rule)
                        except json.JSONDecodeError:
                            logger.warning(
                                "failed_to_parse_applies_to_symbols",
                                rule_id=rule.id,
                            )
                return filtered

            return list(rules)

    async def update_rule_performance(
        self,
        rule_id: int,
        was_successful: bool,
        pnl: float | None = None,
    ) -> TradingRule | None:
        """
        Update rule performance after a trade.

        Args:
            rule_id: ID of the rule
            was_successful: Whether the trade was successful
            pnl: Profit/loss from the trade

        Returns:
            Updated TradingRule or None if not found
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(TradingRule).where(TradingRule.id == rule_id)
            )
            rule = result.scalar_one_or_none()

            if rule is None:
                return None

            rule.times_applied += 1
            if was_successful:
                rule.times_successful += 1

            rule.success_rate = rule.times_successful / rule.times_applied

            if pnl is not None:
                # Update running average of PnL
                rule.avg_pnl_when_applied = (
                    rule.avg_pnl_when_applied * (rule.times_applied - 1) + pnl
                ) / rule.times_applied

            rule.last_validated = datetime.now(UTC)
            rule.validation_count += 1
            rule.updated_at = datetime.now(UTC)

            await session.commit()
            await session.refresh(rule)

            logger.debug(
                "rule_performance_updated",
                rule_id=rule_id,
                success_rate=rule.success_rate,
                times_applied=rule.times_applied,
            )

            return rule

    async def update_rule_status(
        self, rule_id: int, status: RuleStatus
    ) -> TradingRule | None:
        """Update rule status."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(TradingRule).where(TradingRule.id == rule_id)
            )
            rule = result.scalar_one_or_none()

            if rule is None:
                return None

            rule.status = status
            rule.updated_at = datetime.now(UTC)

            await session.commit()
            await session.refresh(rule)

            logger.info("rule_status_updated", rule_id=rule_id, status=status.value)

            return rule

    async def get_matching_rules(
        self,
        symbol: str,
        market_condition: str | None = None,
        timeframe: str | None = None,
    ) -> list[RuleMatch]:
        """
        Get rules matching the current context.

        Args:
            symbol: Trading symbol
            market_condition: Current market condition (bullish, bearish, etc.)
            timeframe: Current timeframe

        Returns:
            List of RuleMatch objects with relevance scores
        """
        rules = await self.get_active_rules(symbol=symbol)
        matches = []

        for rule in rules:
            relevance = 1.0
            reason_parts = []

            # Check market condition match
            if rule.applies_to_market_conditions and market_condition:
                try:
                    conditions = json.loads(rule.applies_to_market_conditions)
                    if market_condition in conditions:
                        relevance += 0.2
                        reason_parts.append("market_condition_match")
                except json.JSONDecodeError:
                    logger.warning(
                        "failed_to_parse_applies_to_market_conditions",
                        rule_id=rule.id,
                    )

            # Check timeframe match
            if rule.applies_to_timeframes and timeframe:
                try:
                    timeframes = json.loads(rule.applies_to_timeframes)
                    if timeframe in timeframes:
                        relevance += 0.1
                        reason_parts.append("timeframe_match")
                except json.JSONDecodeError:
                    logger.warning(
                        "failed_to_parse_applies_to_timeframes",
                        rule_id=rule.id,
                    )

            # Boost by success rate
            relevance *= 0.5 + (rule.success_rate * 0.5)

            # Boost by confidence
            relevance *= rule.confidence

            matches.append(
                RuleMatch(
                    rule=rule,
                    relevance_score=min(relevance, 1.0),
                    reason=", ".join(reason_parts) if reason_parts else "general_match",
                )
            )

        # Sort by relevance
        matches.sort(key=lambda x: x.relevance_score, reverse=True)
        return matches

    # =========================================================================
    # Market Patterns
    # =========================================================================

    async def create_pattern(
        self,
        name: str,
        description: str,
        pattern_type: PatternType,
        definition: str,
        detection_criteria: dict | None = None,
        typical_market_conditions: dict | None = None,
        associated_symbols: list[str] | None = None,
        associated_timeframes: list[str] | None = None,
        min_occurrences_for_validity: int = 10,
    ) -> MarketPattern:
        """
        Create a new market pattern.

        Args:
            name: Pattern name
            description: Pattern description
            pattern_type: Type of pattern
            definition: Human-readable definition
            detection_criteria: Criteria for detecting pattern
            typical_market_conditions: When pattern typically appears
            associated_symbols: Symbols where pattern is common
            associated_timeframes: Timeframes where pattern appears

        Returns:
            Created MarketPattern
        """
        async with self._session_factory() as session:
            pattern = MarketPattern(
                name=name,
                description=description,
                pattern_type=pattern_type,
                definition=definition,
                detection_criteria=(
                    json.dumps(detection_criteria) if detection_criteria else None
                ),
                typical_market_conditions=(
                    json.dumps(typical_market_conditions)
                    if typical_market_conditions
                    else None
                ),
                associated_symbols=(
                    json.dumps(associated_symbols) if associated_symbols else None
                ),
                associated_timeframes=(
                    json.dumps(associated_timeframes) if associated_timeframes else None
                ),
                min_occurrences_for_validity=min_occurrences_for_validity,
            )

            session.add(pattern)
            await session.commit()
            await session.refresh(pattern)

            logger.info(
                "pattern_created",
                pattern_id=pattern.id,
                name=name,
                pattern_type=pattern_type.value,
            )

            return pattern

    async def get_pattern(self, pattern_id: int) -> MarketPattern | None:
        """Get a specific pattern by ID."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(MarketPattern).where(MarketPattern.id == pattern_id)
            )
            return result.scalar_one_or_none()

    async def get_all_patterns(
        self,
        pattern_type: PatternType | None = None,
        validated_only: bool = False,
    ) -> list[MarketPattern]:
        """
        Get all patterns, optionally filtered.

        Args:
            pattern_type: Filter by pattern type
            validated_only: Only return validated patterns

        Returns:
            List of MarketPattern objects
        """
        async with self._session_factory() as session:
            query = select(MarketPattern)

            if pattern_type:
                query = query.where(MarketPattern.pattern_type == pattern_type)

            if validated_only:
                query = query.where(MarketPattern.is_validated.is_(True))

            query = query.order_by(MarketPattern.confidence.desc())

            result = await session.execute(query)
            return list(result.scalars().all())

    async def update_pattern_stats(
        self,
        pattern_id: int,
        was_profitable: bool,
        return_pct: float,
        duration_hours: float,
    ) -> MarketPattern | None:
        """
        Update pattern statistics after observation.

        Args:
            pattern_id: ID of the pattern
            was_profitable: Whether observation was profitable
            return_pct: Return percentage
            duration_hours: Duration of the pattern in hours

        Returns:
            Updated MarketPattern or None if not found
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(MarketPattern).where(MarketPattern.id == pattern_id)
            )
            pattern = result.scalar_one_or_none()

            if pattern is None:
                return None

            pattern.times_identified += 1
            if was_profitable:
                pattern.times_profitable += 1

            pattern.win_rate = pattern.times_profitable / pattern.times_identified

            # Update running averages
            n = pattern.times_identified
            pattern.avg_return = (pattern.avg_return * (n - 1) + return_pct) / n
            pattern.avg_duration_hours = (
                pattern.avg_duration_hours * (n - 1) + duration_hours
            ) / n

            # Update confidence based on sample size and win rate
            if n >= pattern.min_occurrences_for_validity:
                pattern.is_validated = True
                pattern.confidence = min(0.5 + (pattern.win_rate * 0.5), 1.0)
            else:
                pattern.confidence = 0.3 + (n / pattern.min_occurrences_for_validity) * 0.2

            pattern.last_seen = datetime.now(UTC)
            pattern.updated_at = datetime.now(UTC)

            await session.commit()
            await session.refresh(pattern)

            logger.debug(
                "pattern_stats_updated",
                pattern_id=pattern_id,
                win_rate=pattern.win_rate,
                times_identified=pattern.times_identified,
            )

            return pattern

    async def find_matching_patterns(
        self,
        technical_context: dict,
        symbol: str | None = None,  # noqa: ARG002 - reserved for future use
        timeframe: str | None = None,  # noqa: ARG002 - reserved for future use
    ) -> list[PatternMatch]:
        """
        Find patterns matching the current market context.

        Args:
            technical_context: Current technical analysis data
            symbol: Trading symbol
            timeframe: Current timeframe

        Returns:
            List of PatternMatch objects
        """
        patterns = await self.get_all_patterns()
        matches = []

        for pattern in patterns:
            if pattern.detection_criteria is None:
                continue

            try:
                criteria = json.loads(pattern.detection_criteria)
                match_score, details = self._check_pattern_match(
                    criteria, technical_context
                )

                if match_score > 0.3:  # Minimum match threshold
                    # Adjust by pattern confidence and validation
                    confidence = match_score * pattern.confidence
                    if pattern.is_validated:
                        confidence *= 1.2  # Boost validated patterns

                    matches.append(
                        PatternMatch(
                            pattern=pattern,
                            confidence=min(confidence, 1.0),
                            match_details=details,
                        )
                    )
            except json.JSONDecodeError:
                logger.warning(
                    "failed_to_parse_detection_criteria",
                    pattern_id=pattern.id,
                )
                continue

        # Sort by confidence
        matches.sort(key=lambda x: x.confidence, reverse=True)
        return matches

    def _check_pattern_match(
        self, criteria: dict, context: dict
    ) -> tuple[float, dict]:
        """
        Check if current context matches pattern criteria.

        Returns:
            Tuple of (match_score, match_details)
        """
        matches = 0
        total = 0
        details = {}

        for key, expected in criteria.items():
            if key in context:
                total += 1
                actual = context[key]

                if isinstance(expected, dict):
                    # Range check
                    if "min" in expected and actual >= expected["min"]:
                        if "max" in expected and actual <= expected["max"]:
                            matches += 1
                            details[key] = f"in_range({actual})"
                    elif "equals" in expected and actual == expected["equals"]:
                        matches += 1
                        details[key] = f"equals({actual})"
                elif actual == expected:
                    matches += 1
                    details[key] = f"matched({actual})"

        score = matches / total if total > 0 else 0.0
        return score, details

    async def get_rule_stats(self) -> dict:
        """Get statistics about trading rules."""
        async with self._session_factory() as session:
            result = await session.execute(select(TradingRule))
            rules = result.scalars().all()

            if not rules:
                return {
                    "total_rules": 0,
                    "active_rules": 0,
                    "avg_success_rate": 0.0,
                }

            active = [r for r in rules if r.status == RuleStatus.ACTIVE]
            applied = [r for r in rules if r.times_applied > 0]

            return {
                "total_rules": len(rules),
                "active_rules": len(active),
                "rules_applied": len(applied),
                "avg_success_rate": (
                    sum(r.success_rate for r in applied) / len(applied)
                    if applied
                    else 0.0
                ),
                "by_source": {
                    source.value: sum(1 for r in rules if r.source == source)
                    for source in RuleSource
                },
                "by_category": self._count_by_category(rules),
            }

    def _count_by_category(self, rules: list[TradingRule]) -> dict:
        """Count rules by category."""
        counts = {}
        for rule in rules:
            counts[rule.category] = counts.get(rule.category, 0) + 1
        return counts

    async def get_pattern_stats(self) -> dict:
        """Get statistics about market patterns."""
        async with self._session_factory() as session:
            result = await session.execute(select(MarketPattern))
            patterns = result.scalars().all()

            if not patterns:
                return {
                    "total_patterns": 0,
                    "validated_patterns": 0,
                    "avg_win_rate": 0.0,
                }

            validated = [p for p in patterns if p.is_validated]
            identified = [p for p in patterns if p.times_identified > 0]

            return {
                "total_patterns": len(patterns),
                "validated_patterns": len(validated),
                "patterns_identified": len(identified),
                "avg_win_rate": (
                    sum(p.win_rate for p in identified) / len(identified)
                    if identified
                    else 0.0
                ),
                "by_type": {
                    ptype.value: sum(1 for p in patterns if p.pattern_type == ptype)
                    for ptype in PatternType
                },
            }


# Global instance
_semantic_memory: SemanticMemory | None = None


def get_semantic_memory() -> SemanticMemory:
    """Get the global SemanticMemory instance."""
    global _semantic_memory
    if _semantic_memory is None:
        from keryxflow.core.database import get_session_factory

        _semantic_memory = SemanticMemory(get_session_factory())
    return _semantic_memory
