"""Tests for semantic memory."""

import pytest

from keryxflow.core.database import get_session_factory
from keryxflow.core.models import PatternType, RuleSource, RuleStatus
from keryxflow.memory.semantic import PatternMatch, RuleMatch, SemanticMemory


@pytest.fixture
async def semantic_memory(init_db):  # noqa: ARG001
    """Create a semantic memory instance."""
    return SemanticMemory(get_session_factory())


class TestRuleMatch:
    """Tests for RuleMatch dataclass."""

    def test_rule_match_to_dict(self, init_db):  # noqa: ARG002
        """Test converting rule match to dict."""
        from keryxflow.core.models import TradingRule

        rule = TradingRule(
            id=1,
            name="RSI Oversold Buy",
            description="Buy when RSI is oversold",
            condition="RSI < 30 and trend is bullish",
            success_rate=0.65,
        )

        match = RuleMatch(
            rule=rule,
            relevance_score=0.8,
            reason="market_condition_match",
        )

        result = match.to_dict()

        assert result["rule_id"] == 1
        assert result["name"] == "RSI Oversold Buy"
        assert result["success_rate"] == 0.65
        assert result["relevance_score"] == 0.8


class TestPatternMatch:
    """Tests for PatternMatch dataclass."""

    def test_pattern_match_to_dict(self, init_db):  # noqa: ARG002
        """Test converting pattern match to dict."""
        from keryxflow.core.models import MarketPattern

        pattern = MarketPattern(
            id=1,
            name="Double Bottom",
            description="Bullish reversal pattern",
            pattern_type=PatternType.PRICE_ACTION,
            definition="Two consecutive lows at similar levels",
            win_rate=0.7,
            avg_return=5.0,
        )

        match = PatternMatch(
            pattern=pattern,
            confidence=0.85,
            match_details={"first_low": 50000, "second_low": 50100},
        )

        result = match.to_dict()

        assert result["pattern_id"] == 1
        assert result["name"] == "Double Bottom"
        assert result["pattern_type"] == "price_action"
        assert result["win_rate"] == 0.7
        assert result["confidence"] == 0.85


class TestSemanticMemoryRules:
    """Tests for trading rules in semantic memory."""

    @pytest.mark.asyncio
    async def test_create_rule(self, semantic_memory):
        """Test creating a trading rule."""
        rule = await semantic_memory.create_rule(
            name="RSI Oversold Entry",
            description="Enter long when RSI is oversold",
            condition="RSI < 30",
            source=RuleSource.LEARNED,
            category="entry",
            priority=5,
        )

        assert rule.id is not None
        assert rule.name == "RSI Oversold Entry"
        assert rule.source == RuleSource.LEARNED
        assert rule.category == "entry"
        assert rule.priority == 5
        assert rule.status == RuleStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_create_rule_with_applicability(self, semantic_memory):
        """Test creating a rule with applicability filters."""
        rule = await semantic_memory.create_rule(
            name="BTC Only Rule",
            description="Rule for BTC trading",
            condition="Test condition",
            applies_to_symbols=["BTC/USDT"],
            applies_to_timeframes=["1h", "4h"],
            applies_to_market_conditions={"bullish": True},
        )

        assert rule.applies_to_symbols is not None
        assert "BTC/USDT" in rule.applies_to_symbols

    @pytest.mark.asyncio
    async def test_get_rule(self, semantic_memory):
        """Test getting a rule by ID."""
        rule = await semantic_memory.create_rule(
            name="Test Rule",
            description="Test description",
            condition="Test condition",
        )

        retrieved = await semantic_memory.get_rule(rule.id)

        assert retrieved is not None
        assert retrieved.name == "Test Rule"

    @pytest.mark.asyncio
    async def test_get_rule_not_found(self, semantic_memory):
        """Test getting non-existent rule."""
        result = await semantic_memory.get_rule(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_rules(self, semantic_memory):
        """Test getting active rules."""
        # Create active and inactive rules
        await semantic_memory.create_rule(
            name="Active Rule 1",
            description="Test",
            condition="Test",
            category="entry",
        )
        await semantic_memory.create_rule(
            name="Active Rule 2",
            description="Test",
            condition="Test",
            category="exit",
        )

        inactive_rule = await semantic_memory.create_rule(
            name="Inactive Rule",
            description="Test",
            condition="Test",
        )
        await semantic_memory.update_rule_status(inactive_rule.id, RuleStatus.INACTIVE)

        active = await semantic_memory.get_active_rules()

        assert len(active) == 2

    @pytest.mark.asyncio
    async def test_get_active_rules_by_category(self, semantic_memory):
        """Test getting active rules filtered by category."""
        await semantic_memory.create_rule(
            name="Entry Rule",
            description="Test",
            condition="Test",
            category="entry",
        )
        await semantic_memory.create_rule(
            name="Exit Rule",
            description="Test",
            condition="Test",
            category="exit",
        )

        entry_rules = await semantic_memory.get_active_rules(category="entry")

        assert len(entry_rules) == 1
        assert entry_rules[0].category == "entry"

    @pytest.mark.asyncio
    async def test_get_active_rules_by_symbol(self, semantic_memory):
        """Test getting active rules filtered by symbol."""
        await semantic_memory.create_rule(
            name="BTC Rule",
            description="Test",
            condition="Test",
            applies_to_symbols=["BTC/USDT"],
        )
        await semantic_memory.create_rule(
            name="ETH Rule",
            description="Test",
            condition="Test",
            applies_to_symbols=["ETH/USDT"],
        )
        await semantic_memory.create_rule(
            name="All Symbols Rule",
            description="Test",
            condition="Test",
        )

        btc_rules = await semantic_memory.get_active_rules(symbol="BTC/USDT")

        assert len(btc_rules) == 2  # BTC specific + all symbols

    @pytest.mark.asyncio
    async def test_update_rule_performance(self, semantic_memory):
        """Test updating rule performance after trades."""
        rule = await semantic_memory.create_rule(
            name="Test Rule",
            description="Test",
            condition="Test",
        )

        # Simulate 10 trades: 7 wins, 3 losses
        for _i in range(7):
            await semantic_memory.update_rule_performance(rule.id, was_successful=True, pnl=100.0)
        for _i in range(3):
            await semantic_memory.update_rule_performance(rule.id, was_successful=False, pnl=-50.0)

        updated = await semantic_memory.get_rule(rule.id)

        assert updated.times_applied == 10
        assert updated.times_successful == 7
        assert updated.success_rate == 0.7
        assert updated.avg_pnl_when_applied == 55.0  # (7*100 + 3*(-50)) / 10

    @pytest.mark.asyncio
    async def test_update_rule_status(self, semantic_memory):
        """Test updating rule status."""
        rule = await semantic_memory.create_rule(
            name="Test Rule",
            description="Test",
            condition="Test",
        )

        updated = await semantic_memory.update_rule_status(rule.id, RuleStatus.DEPRECATED)

        assert updated.status == RuleStatus.DEPRECATED

    @pytest.mark.asyncio
    async def test_get_matching_rules(self, semantic_memory):
        """Test getting rules matching current context."""
        await semantic_memory.create_rule(
            name="High Priority Rule",
            description="Test",
            condition="Test",
            priority=10,
            applies_to_symbols=["BTC/USDT"],
        )
        await semantic_memory.create_rule(
            name="Low Priority Rule",
            description="Test",
            condition="Test",
            priority=1,
        )

        matches = await semantic_memory.get_matching_rules(
            symbol="BTC/USDT",
            market_condition="bullish",
        )

        assert len(matches) == 2
        # Should be sorted by relevance (priority affects it)


class TestSemanticMemoryPatterns:
    """Tests for market patterns in semantic memory."""

    @pytest.mark.asyncio
    async def test_create_pattern(self, semantic_memory):
        """Test creating a market pattern."""
        pattern = await semantic_memory.create_pattern(
            name="Bullish Engulfing",
            description="Bullish reversal candlestick pattern",
            pattern_type=PatternType.PRICE_ACTION,
            definition="Current candle body engulfs previous bearish candle",
        )

        assert pattern.id is not None
        assert pattern.name == "Bullish Engulfing"
        assert pattern.pattern_type == PatternType.PRICE_ACTION
        assert pattern.is_validated is False

    @pytest.mark.asyncio
    async def test_create_pattern_with_criteria(self, semantic_memory):
        """Test creating a pattern with detection criteria."""
        pattern = await semantic_memory.create_pattern(
            name="RSI Divergence",
            description="Price makes new low but RSI makes higher low",
            pattern_type=PatternType.INDICATOR,
            definition="Bullish divergence",
            detection_criteria={
                "rsi": {"min": 20, "max": 40},
                "price_new_low": True,
                "rsi_higher_low": True,
            },
        )

        assert pattern.detection_criteria is not None

    @pytest.mark.asyncio
    async def test_get_pattern(self, semantic_memory):
        """Test getting a pattern by ID."""
        pattern = await semantic_memory.create_pattern(
            name="Test Pattern",
            description="Test",
            pattern_type=PatternType.VOLUME,
            definition="Test",
        )

        retrieved = await semantic_memory.get_pattern(pattern.id)

        assert retrieved is not None
        assert retrieved.name == "Test Pattern"

    @pytest.mark.asyncio
    async def test_get_all_patterns(self, semantic_memory):
        """Test getting all patterns."""
        await semantic_memory.create_pattern(
            name="Pattern 1",
            description="Test",
            pattern_type=PatternType.PRICE_ACTION,
            definition="Test",
        )
        await semantic_memory.create_pattern(
            name="Pattern 2",
            description="Test",
            pattern_type=PatternType.INDICATOR,
            definition="Test",
        )

        patterns = await semantic_memory.get_all_patterns()

        assert len(patterns) == 2

    @pytest.mark.asyncio
    async def test_get_patterns_by_type(self, semantic_memory):
        """Test getting patterns filtered by type."""
        await semantic_memory.create_pattern(
            name="Price Pattern",
            description="Test",
            pattern_type=PatternType.PRICE_ACTION,
            definition="Test",
        )
        await semantic_memory.create_pattern(
            name="Indicator Pattern",
            description="Test",
            pattern_type=PatternType.INDICATOR,
            definition="Test",
        )

        price_patterns = await semantic_memory.get_all_patterns(
            pattern_type=PatternType.PRICE_ACTION
        )

        assert len(price_patterns) == 1
        assert price_patterns[0].pattern_type == PatternType.PRICE_ACTION

    @pytest.mark.asyncio
    async def test_update_pattern_stats(self, semantic_memory):
        """Test updating pattern statistics."""
        pattern = await semantic_memory.create_pattern(
            name="Test Pattern",
            description="Test",
            pattern_type=PatternType.COMBINED,
            definition="Test",
            min_occurrences_for_validity=5,
        )

        # Simulate 5 observations: 4 profitable
        for _i in range(4):
            await semantic_memory.update_pattern_stats(
                pattern.id, was_profitable=True, return_pct=5.0, duration_hours=24.0
            )
        await semantic_memory.update_pattern_stats(
            pattern.id, was_profitable=False, return_pct=-2.0, duration_hours=12.0
        )

        updated = await semantic_memory.get_pattern(pattern.id)

        assert updated.times_identified == 5
        assert updated.times_profitable == 4
        assert updated.win_rate == 0.8
        assert updated.is_validated is True  # >= min_occurrences
        assert updated.last_seen is not None

    @pytest.mark.asyncio
    async def test_find_matching_patterns(self, semantic_memory):
        """Test finding patterns matching current context."""
        await semantic_memory.create_pattern(
            name="RSI Pattern",
            description="Test",
            pattern_type=PatternType.INDICATOR,
            definition="Test",
            detection_criteria={
                "rsi": {"min": 25, "max": 35},
                "trend": {"equals": "bullish"},
            },
        )

        matches = await semantic_memory.find_matching_patterns(
            technical_context={"rsi": 30, "trend": "bullish"},
            symbol="BTC/USDT",
        )

        assert len(matches) >= 1
        assert matches[0].confidence > 0


class TestSemanticMemoryStats:
    """Tests for memory statistics."""

    @pytest.mark.asyncio
    async def test_get_rule_stats_empty(self, semantic_memory):
        """Test rule stats with no rules."""
        stats = await semantic_memory.get_rule_stats()

        assert stats["total_rules"] == 0
        assert stats["active_rules"] == 0

    @pytest.mark.asyncio
    async def test_get_rule_stats(self, semantic_memory):
        """Test rule statistics."""
        await semantic_memory.create_rule(
            name="Learned Rule",
            description="Test",
            condition="Test",
            source=RuleSource.LEARNED,
            category="entry",
        )
        await semantic_memory.create_rule(
            name="User Rule",
            description="Test",
            condition="Test",
            source=RuleSource.USER,
            category="exit",
        )

        stats = await semantic_memory.get_rule_stats()

        assert stats["total_rules"] == 2
        assert stats["active_rules"] == 2
        assert stats["by_source"]["learned"] == 1
        assert stats["by_source"]["user"] == 1
        assert stats["by_category"]["entry"] == 1
        assert stats["by_category"]["exit"] == 1

    @pytest.mark.asyncio
    async def test_get_pattern_stats_empty(self, semantic_memory):
        """Test pattern stats with no patterns."""
        stats = await semantic_memory.get_pattern_stats()

        assert stats["total_patterns"] == 0
        assert stats["validated_patterns"] == 0

    @pytest.mark.asyncio
    async def test_get_pattern_stats(self, semantic_memory):
        """Test pattern statistics."""
        pattern = await semantic_memory.create_pattern(
            name="Pattern 1",
            description="Test",
            pattern_type=PatternType.PRICE_ACTION,
            definition="Test",
            min_occurrences_for_validity=2,
        )

        # Make it validated
        await semantic_memory.update_pattern_stats(
            pattern.id, was_profitable=True, return_pct=5.0, duration_hours=24.0
        )
        await semantic_memory.update_pattern_stats(
            pattern.id, was_profitable=True, return_pct=5.0, duration_hours=24.0
        )

        stats = await semantic_memory.get_pattern_stats()

        assert stats["total_patterns"] == 1
        assert stats["validated_patterns"] == 1
        assert stats["by_type"]["price_action"] == 1


class TestPatternMatchLogic:
    """Tests for pattern matching logic."""

    def test_check_pattern_match_range(self, semantic_memory):
        """Test pattern matching with range criteria."""
        criteria = {"rsi": {"min": 25, "max": 35}}
        context = {"rsi": 30}

        score, details = semantic_memory._check_pattern_match(criteria, context)

        assert score == 1.0
        assert "rsi" in details

    def test_check_pattern_match_equals(self, semantic_memory):
        """Test pattern matching with equals criteria."""
        criteria = {"trend": {"equals": "bullish"}}
        context = {"trend": "bullish"}

        score, details = semantic_memory._check_pattern_match(criteria, context)

        assert score == 1.0

    def test_check_pattern_match_no_match(self, semantic_memory):
        """Test pattern matching with no matches."""
        criteria = {"rsi": {"min": 70, "max": 100}}
        context = {"rsi": 30}

        score, details = semantic_memory._check_pattern_match(criteria, context)

        assert score == 0.0

    def test_check_pattern_match_partial(self, semantic_memory):
        """Test pattern matching with partial match."""
        criteria = {
            "rsi": {"min": 25, "max": 35},
            "trend": {"equals": "bullish"},
        }
        context = {"rsi": 30, "trend": "bearish"}

        score, details = semantic_memory._check_pattern_match(criteria, context)

        assert score == 0.5  # One of two matches
