"""Tests for the Reflection Engine."""

import pytest

from keryxflow.agent.reflection import (
    DailyReflectionResult,
    PostMortemResult,
    ReflectionEngine,
    ReflectionType,
    WeeklyReflectionResult,
    get_reflection_engine,
)
from keryxflow.core.models import TradeOutcome


class TestReflectionType:
    """Tests for ReflectionType enum."""

    def test_reflection_type_values(self):
        """Test reflection type values."""
        assert ReflectionType.POST_MORTEM.value == "post_mortem"
        assert ReflectionType.DAILY.value == "daily"
        assert ReflectionType.WEEKLY.value == "weekly"


class TestPostMortemResult:
    """Tests for PostMortemResult dataclass."""

    def test_create_post_mortem_result(self):
        """Test creating a post-mortem result."""
        result = PostMortemResult(
            episode_id=1,
            symbol="BTC/USDT",
            outcome=TradeOutcome.WIN,
            pnl_percentage=2.5,
            lessons_learned="Good entry timing",
            what_went_well="Followed the plan",
            what_went_wrong="Nothing significant",
            would_take_again=True,
        )

        assert result.episode_id == 1
        assert result.symbol == "BTC/USDT"
        assert result.outcome == TradeOutcome.WIN
        assert result.pnl_percentage == 2.5
        assert result.would_take_again is True

    def test_post_mortem_to_dict(self):
        """Test converting to dictionary."""
        result = PostMortemResult(
            episode_id=1,
            symbol="ETH/USDT",
            outcome=TradeOutcome.LOSS,
            pnl_percentage=-1.5,
            lessons_learned="Test lesson",
            what_went_well="Risk management",
            what_went_wrong="Bad timing",
            would_take_again=False,
        )

        data = result.to_dict()

        assert data["episode_id"] == 1
        assert data["symbol"] == "ETH/USDT"
        assert data["outcome"] == "loss"
        assert data["pnl_percentage"] == -1.5


class TestDailyReflectionResult:
    """Tests for DailyReflectionResult dataclass."""

    def test_create_daily_result(self):
        """Test creating a daily reflection result."""
        result = DailyReflectionResult(
            date="2024-01-15",
            total_trades=5,
            winning_trades=3,
            losing_trades=2,
            total_pnl=150.0,
            total_pnl_percentage=1.5,
            summary="Good trading day",
            key_lessons=["Be patient"],
            mistakes_made=["Overtraded"],
            good_decisions=["Held winners"],
            recommendations=["Continue same approach"],
            rules_to_review=[1, 2],
            episodes_analyzed=[10, 11, 12, 13, 14],
        )

        assert result.date == "2024-01-15"
        assert result.total_trades == 5
        assert result.winning_trades == 3
        assert result.total_pnl_percentage == 1.5

    def test_daily_result_to_dict(self):
        """Test converting to dictionary."""
        result = DailyReflectionResult(
            date="2024-01-15",
            total_trades=3,
            winning_trades=2,
            losing_trades=1,
            total_pnl=50.0,
            total_pnl_percentage=0.5,
            summary="Okay day",
            key_lessons=["Test"],
            mistakes_made=["Test"],
            good_decisions=["Test"],
            recommendations=["Test"],
            rules_to_review=[],
            episodes_analyzed=[1, 2, 3],
        )

        data = result.to_dict()

        assert data["date"] == "2024-01-15"
        assert data["total_trades"] == 3
        assert len(data["episodes_analyzed"]) == 3


class TestWeeklyReflectionResult:
    """Tests for WeeklyReflectionResult dataclass."""

    def test_create_weekly_result(self):
        """Test creating a weekly reflection result."""
        result = WeeklyReflectionResult(
            week_start="2024-01-08",
            week_end="2024-01-14",
            total_trades=20,
            win_rate=60.0,
            total_pnl=500.0,
            avg_pnl_per_trade=25.0,
            patterns_identified=[{"name": "Test pattern"}],
            recurring_mistakes=["Overtrading"],
            successful_strategies=["Trend following"],
            new_rules_created=[],
            rules_updated=[],
            rules_deprecated=[],
            performance_by_symbol={"BTC/USDT": {"trades": 10, "pnl": 300.0}},
            focus_areas=["Patience"],
            improvement_plan="Focus on quality over quantity",
            daily_summaries=["Day 1 summary", "Day 2 summary"],
        )

        assert result.week_start == "2024-01-08"
        assert result.total_trades == 20
        assert result.win_rate == 60.0

    def test_weekly_result_to_dict(self):
        """Test converting to dictionary."""
        result = WeeklyReflectionResult(
            week_start="2024-01-01",
            week_end="2024-01-07",
            total_trades=10,
            win_rate=50.0,
            total_pnl=100.0,
            avg_pnl_per_trade=10.0,
            patterns_identified=[],
            recurring_mistakes=["Test"],
            successful_strategies=["Test"],
            new_rules_created=[],
            rules_updated=[],
            rules_deprecated=[],
            performance_by_symbol={},
            focus_areas=["Test"],
            improvement_plan="Test plan",
            daily_summaries=[],
        )

        data = result.to_dict()

        assert data["week_start"] == "2024-01-01"
        assert data["win_rate"] == 50.0


class TestReflectionEngine:
    """Tests for ReflectionEngine class."""

    def test_create_engine(self):
        """Test creating a reflection engine."""
        engine = ReflectionEngine()

        assert engine._initialized is False
        assert engine._client is None

    @pytest.mark.asyncio
    async def test_initialize_without_api_key(self):
        """Test initializing without API key."""
        engine = ReflectionEngine()

        await engine.initialize()

        assert engine._initialized is True
        assert engine._client is None

    def test_generate_basic_post_mortem_win(self):
        """Test generating basic post-mortem JSON for winning trade."""
        from keryxflow.core.models import TradeEpisode

        engine = ReflectionEngine()

        episode = TradeEpisode(
            id=1,
            trade_id=100,
            symbol="BTC/USDT",
            entry_price=50000.0,
            entry_reasoning="Test entry",
            pnl_percentage=2.5,
            outcome=TradeOutcome.WIN,
        )

        result = engine._generate_basic_post_mortem_json(episode)

        assert "Profitable" in result["lessons_learned"]
        assert result["would_take_again"] is True
        assert isinstance(result["new_rules"], list)

    def test_generate_basic_post_mortem_loss(self):
        """Test generating basic post-mortem JSON for losing trade."""
        from keryxflow.core.models import TradeEpisode

        engine = ReflectionEngine()

        episode = TradeEpisode(
            id=1,
            trade_id=100,
            symbol="BTC/USDT",
            entry_price=50000.0,
            entry_reasoning="Test entry",
            pnl_percentage=-1.5,
            outcome=TradeOutcome.LOSS,
        )

        result = engine._generate_basic_post_mortem_json(episode)

        assert "Loss" in result["lessons_learned"]
        assert result["would_take_again"] is False

    def test_generate_basic_daily_reflection(self):
        """Test generating basic daily reflection JSON."""
        engine = ReflectionEngine()

        result = engine._generate_basic_daily_reflection_json(
            date_str="2024-01-15",
            total_trades=5,
            winning=3,
            losing=2,
            pnl_pct=1.5,
        )

        assert "2024-01-15" in result["summary"]
        assert "5" in result["summary"]
        assert isinstance(result["key_lessons"], list)
        assert isinstance(result["recommendations"], list)

    def test_generate_basic_weekly_reflection(self):
        """Test generating basic weekly reflection JSON."""
        engine = ReflectionEngine()

        result = engine._generate_basic_weekly_reflection_json(
            _total_trades=10,
            win_rate=60.0,
            total_pnl=5.0,
            symbol_perf={"BTC/USDT": {"trades": 5, "pnl": 3.0}},
        )

        assert isinstance(result["patterns_identified"], list)
        assert isinstance(result["focus_areas"], list)
        assert isinstance(result["improvement_plan"], str)

    def test_parse_json_response_direct(self):
        """Test parsing direct JSON response."""
        engine = ReflectionEngine()

        text = '{"lessons_learned": "Test", "would_take_again": true}'
        result = engine._parse_json_response(text)

        assert result is not None
        assert result["lessons_learned"] == "Test"
        assert result["would_take_again"] is True

    def test_parse_json_response_with_markdown_fence(self):
        """Test parsing JSON wrapped in markdown code fence."""
        engine = ReflectionEngine()

        text = '```json\n{"summary": "Good day", "key_lessons": ["Patience"]}\n```'
        result = engine._parse_json_response(text)

        assert result is not None
        assert result["summary"] == "Good day"

    def test_parse_json_response_with_surrounding_text(self):
        """Test parsing JSON with surrounding text."""
        engine = ReflectionEngine()

        text = 'Here is my analysis:\n{"summary": "Good day"}\nThank you.'
        result = engine._parse_json_response(text)

        assert result is not None
        assert result["summary"] == "Good day"

    def test_parse_json_response_empty(self):
        """Test parsing empty text returns None."""
        engine = ReflectionEngine()
        assert engine._parse_json_response("") is None
        assert engine._parse_json_response(None) is None

    def test_parse_json_response_invalid(self):
        """Test parsing invalid JSON returns None."""
        engine = ReflectionEngine()
        result = engine._parse_json_response("This is not JSON at all")
        assert result is None

    def test_parse_json_response_nested_braces(self):
        """Test parsing JSON with nested objects."""
        engine = ReflectionEngine()

        text = '{"rules": [{"name": "Test", "condition": "RSI > 70"}], "plan": "Improve"}'
        result = engine._parse_json_response(text)

        assert result is not None
        assert len(result["rules"]) == 1
        assert result["rules"][0]["name"] == "Test"

    def test_get_stats(self):
        """Test getting engine statistics."""
        engine = ReflectionEngine()

        stats = engine.get_stats()

        assert stats["total_post_mortems"] == 0
        assert stats["total_daily_reflections"] == 0
        assert stats["rules_created"] == 0
        assert stats["total_input_tokens"] == 0
        assert stats["total_output_tokens"] == 0
        assert stats["total_cost_usd"] == 0.0

    def test_get_recent_reflections(self):
        """Test getting recent reflections."""
        engine = ReflectionEngine()

        # Add some mock reflections
        engine._reflection_history.append(
            {
                "type": ReflectionType.DAILY.value,
                "result": {"test": "data"},
            }
        )

        recent = engine.get_recent_reflections()

        assert len(recent) == 1
        assert recent[0]["type"] == "daily"

    def test_get_recent_reflections_filtered(self):
        """Test getting filtered recent reflections."""
        engine = ReflectionEngine()

        engine._reflection_history.append(
            {
                "type": ReflectionType.DAILY.value,
                "result": {},
            }
        )
        engine._reflection_history.append(
            {
                "type": ReflectionType.WEEKLY.value,
                "result": {},
            }
        )

        daily = engine.get_recent_reflections(ReflectionType.DAILY)
        weekly = engine.get_recent_reflections(ReflectionType.WEEKLY)

        assert len(daily) == 1
        assert len(weekly) == 1


class TestGetReflectionEngine:
    """Tests for get_reflection_engine function."""

    def test_returns_singleton(self):
        """Test that function returns singleton."""
        engine1 = get_reflection_engine()
        engine2 = get_reflection_engine()

        assert engine1 is engine2

    def test_creates_engine(self):
        """Test that function creates engine."""
        engine = get_reflection_engine()

        assert isinstance(engine, ReflectionEngine)
