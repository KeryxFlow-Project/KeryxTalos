"""Reflection engine for learning from trading experience.

This module provides capabilities for the agent to learn from past trades:
- Trade Post-Mortem: Analyze individual closed trades
- Daily Reflection: Review the day's trading performance
- Weekly Reflection: Identify patterns and update rules
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from keryxflow.agent.cognitive import _is_retryable_api_error
from keryxflow.config import get_settings
from keryxflow.core.logging import get_logger
from keryxflow.core.models import (
    RuleSource,
    RuleStatus,
    TradeEpisode,
    TradeOutcome,
)
from keryxflow.memory.episodic import EpisodicMemory, get_episodic_memory
from keryxflow.memory.semantic import SemanticMemory, get_semantic_memory

logger = get_logger(__name__)


class ReflectionType(str, Enum):
    """Type of reflection."""

    POST_MORTEM = "post_mortem"
    DAILY = "daily"
    WEEKLY = "weekly"


@dataclass
class PostMortemResult:
    """Result of a trade post-mortem analysis."""

    episode_id: int
    symbol: str
    outcome: TradeOutcome
    pnl_percentage: float

    # Analysis
    lessons_learned: str
    what_went_well: str
    what_went_wrong: str
    would_take_again: bool

    # Extracted insights
    new_rules: list[dict[str, Any]] = field(default_factory=list)
    pattern_observations: list[str] = field(default_factory=list)

    # Metadata
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "episode_id": self.episode_id,
            "symbol": self.symbol,
            "outcome": self.outcome.value,
            "pnl_percentage": self.pnl_percentage,
            "lessons_learned": self.lessons_learned,
            "what_went_well": self.what_went_well,
            "what_went_wrong": self.what_went_wrong,
            "would_take_again": self.would_take_again,
            "new_rules": self.new_rules,
            "pattern_observations": self.pattern_observations,
            "analyzed_at": self.analyzed_at.isoformat(),
        }


@dataclass
class DailyReflectionResult:
    """Result of daily reflection."""

    date: str  # YYYY-MM-DD
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    total_pnl_percentage: float

    # Analysis
    summary: str
    key_lessons: list[str]
    mistakes_made: list[str]
    good_decisions: list[str]

    # Recommendations
    recommendations: list[str]
    rules_to_review: list[int]  # Rule IDs that need review

    # Metadata
    episodes_analyzed: list[int]
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "date": self.date,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "total_pnl": self.total_pnl,
            "total_pnl_percentage": self.total_pnl_percentage,
            "summary": self.summary,
            "key_lessons": self.key_lessons,
            "mistakes_made": self.mistakes_made,
            "good_decisions": self.good_decisions,
            "recommendations": self.recommendations,
            "rules_to_review": self.rules_to_review,
            "episodes_analyzed": self.episodes_analyzed,
            "analyzed_at": self.analyzed_at.isoformat(),
        }


@dataclass
class WeeklyReflectionResult:
    """Result of weekly reflection."""

    week_start: str  # YYYY-MM-DD
    week_end: str  # YYYY-MM-DD
    total_trades: int
    win_rate: float
    total_pnl: float
    avg_pnl_per_trade: float

    # Pattern analysis
    patterns_identified: list[dict[str, Any]]
    recurring_mistakes: list[str]
    successful_strategies: list[str]

    # Rule updates
    new_rules_created: list[dict[str, Any]]
    rules_updated: list[dict[str, Any]]
    rules_deprecated: list[int]

    # Performance by symbol
    performance_by_symbol: dict[str, dict[str, Any]]

    # Recommendations
    focus_areas: list[str]
    improvement_plan: str

    # Metadata
    daily_summaries: list[str]
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "week_start": self.week_start,
            "week_end": self.week_end,
            "total_trades": self.total_trades,
            "win_rate": self.win_rate,
            "total_pnl": self.total_pnl,
            "avg_pnl_per_trade": self.avg_pnl_per_trade,
            "patterns_identified": self.patterns_identified,
            "recurring_mistakes": self.recurring_mistakes,
            "successful_strategies": self.successful_strategies,
            "new_rules_created": self.new_rules_created,
            "rules_updated": self.rules_updated,
            "rules_deprecated": self.rules_deprecated,
            "performance_by_symbol": self.performance_by_symbol,
            "focus_areas": self.focus_areas,
            "improvement_plan": self.improvement_plan,
            "daily_summaries": self.daily_summaries,
            "analyzed_at": self.analyzed_at.isoformat(),
        }


@dataclass
class ReflectionStats:
    """Statistics for the reflection engine."""

    total_post_mortems: int = 0
    total_daily_reflections: int = 0
    total_weekly_reflections: int = 0
    rules_created: int = 0
    rules_updated: int = 0
    patterns_identified: int = 0
    total_tokens_used: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    last_reflection_time: datetime | None = None


class ReflectionEngine:
    """Engine for generating reflections and learning from trades.

    The ReflectionEngine analyzes trading performance at different time scales:
    - Post-Mortem: Immediate analysis after each trade closes
    - Daily: End-of-day summary and lessons
    - Weekly: Pattern identification and rule updates

    Example:
        engine = ReflectionEngine()
        await engine.initialize()

        # Analyze a closed trade
        result = await engine.post_mortem(episode_id=123)

        # Run daily reflection
        daily = await engine.daily_reflection()

        # Run weekly reflection
        weekly = await engine.weekly_reflection()
    """

    POST_MORTEM_PROMPT = """Analyze this closed trade and extract lessons.

Trade Details:
- Symbol: {symbol}
- Entry: ${entry_price:.2f} at {entry_time}
- Exit: ${exit_price:.2f} at {exit_time}
- Outcome: {outcome} ({pnl_percentage:+.2f}%)
- Entry Reasoning: {entry_reasoning}
- Exit Reasoning: {exit_reasoning}

Technical Context at Entry:
{technical_context}

Respond with a JSON object (and nothing else) with these fields:
{{
  "lessons_learned": "string - key lesson from this trade",
  "what_went_well": "string - what worked",
  "what_went_wrong": "string - what could improve",
  "would_take_again": true/false,
  "new_rules": [
    {{"name": "rule name", "condition": "when to apply", "description": "what to do"}}
  ],
  "pattern_observations": ["string - observed pattern"]
}}"""

    DAILY_REFLECTION_PROMPT = """Analyze today's trading performance.

Date: {date}
Total Trades: {total_trades}
Winners: {winning_trades} | Losers: {losing_trades}
Total P&L: {total_pnl:+.2f}%

Trade Summaries:
{trade_summaries}

Respond with a JSON object (and nothing else) with these fields:
{{
  "summary": "string - brief summary of today",
  "key_lessons": ["string - lesson learned"],
  "mistakes_made": ["string - mistake identified"],
  "good_decisions": ["string - good decision made"],
  "recommendations": ["string - recommendation for tomorrow"],
  "rules_to_review": [0]
}}"""

    WEEKLY_REFLECTION_PROMPT = """Analyze this week's trading performance and identify patterns.

Week: {week_start} to {week_end}
Total Trades: {total_trades}
Win Rate: {win_rate:.1f}%
Total P&L: {total_pnl:+.2f}%
Average P&L per Trade: {avg_pnl:+.2f}%

Daily Summaries:
{daily_summaries}

Performance by Symbol:
{symbol_performance}

Existing Rules Performance:
{rules_performance}

Respond with a JSON object (and nothing else) with these fields:
{{
  "patterns_identified": [{{"description": "string"}}],
  "recurring_mistakes": ["string"],
  "successful_strategies": ["string"],
  "new_rules_created": [
    {{"name": "rule name", "condition": "when to apply", "description": "what to do"}}
  ],
  "rules_updated": [{{"id": 0, "confidence": 0.0}}],
  "rules_deprecated": [0],
  "focus_areas": ["string"],
  "improvement_plan": "string"
}}"""

    def __init__(
        self,
        episodic_memory: EpisodicMemory | None = None,
        semantic_memory: SemanticMemory | None = None,
    ):
        """Initialize the reflection engine.

        Args:
            episodic_memory: Episodic memory instance. Uses global if None.
            semantic_memory: Semantic memory instance. Uses global if None.
        """
        self.settings = get_settings()
        self.episodic = episodic_memory or get_episodic_memory()
        self.semantic = semantic_memory or get_semantic_memory()

        self._initialized = False
        self._client: Any = None
        self._stats = ReflectionStats()
        self._reflection_history: list[dict[str, Any]] = []

    async def initialize(self) -> None:
        """Initialize the reflection engine."""
        if self._initialized:
            return

        try:
            import anthropic

            api_key = self.settings.anthropic_api_key.get_secret_value()

            if not api_key:
                logger.warning("anthropic_api_key_not_configured_for_reflection")
                self._client = None
            else:
                self._client = anthropic.Anthropic(api_key=api_key)
                logger.info("reflection_engine_initialized")

        except ImportError:
            logger.error("anthropic_package_not_installed")
            self._client = None

        self._initialized = True

    async def post_mortem(self, episode_id: int) -> PostMortemResult | None:
        """Analyze a closed trade and extract lessons.

        Args:
            episode_id: ID of the trade episode to analyze

        Returns:
            PostMortemResult or None if analysis failed
        """
        if not self._initialized:
            await self.initialize()

        # Get the episode
        episode = await self.episodic.get_episode(episode_id)
        if episode is None:
            logger.warning("episode_not_found", episode_id=episode_id)
            return None

        if episode.exit_timestamp is None:
            logger.warning("episode_not_closed", episode_id=episode_id)
            return None

        # Build the prompt
        technical_context = "Not available"
        if episode.technical_context:
            try:
                technical_context = json.dumps(json.loads(episode.technical_context), indent=2)
            except json.JSONDecodeError:
                technical_context = episode.technical_context

        prompt = self.POST_MORTEM_PROMPT.format(
            symbol=episode.symbol,
            entry_price=episode.entry_price,
            entry_time=episode.entry_timestamp.isoformat(),
            exit_price=episode.exit_price or 0,
            exit_time=episode.exit_timestamp.isoformat() if episode.exit_timestamp else "N/A",
            outcome=episode.outcome.value if episode.outcome else "unknown",
            pnl_percentage=episode.pnl_percentage or 0,
            entry_reasoning=episode.entry_reasoning,
            exit_reasoning=episode.exit_reasoning or "Not specified",
            technical_context=technical_context,
        )

        # Get analysis from Claude
        analysis_text = await self._get_analysis(prompt)

        # Parse as JSON; fallback to basic if not available
        parsed = self._parse_json_response(analysis_text) if analysis_text else None
        if parsed is None:
            parsed = self._generate_basic_post_mortem_json(episode)

        # Build result from parsed JSON
        result = PostMortemResult(
            episode_id=episode.id or 0,
            symbol=episode.symbol,
            outcome=episode.outcome or TradeOutcome.LOSS,
            pnl_percentage=episode.pnl_percentage or 0,
            lessons_learned=str(parsed.get("lessons_learned", episode.entry_reasoning[:200])),
            what_went_well=str(parsed.get("what_went_well", "Trade executed as planned")),
            what_went_wrong=str(parsed.get("what_went_wrong", "No significant issues")),
            would_take_again=bool(parsed.get("would_take_again", False)),
            new_rules=list(parsed.get("new_rules", [])),
            pattern_observations=list(parsed.get("pattern_observations", [])),
        )

        # Update the episode with lessons learned
        await self.episodic.record_lessons(
            episode_id=episode_id,
            lessons=result.lessons_learned,
            what_went_well=result.what_went_well,
            what_went_wrong=result.what_went_wrong,
            would_take_again=result.would_take_again,
        )

        # Create any new rules
        for rule_data in result.new_rules:
            await self._create_rule_from_reflection(rule_data)

        self._stats.total_post_mortems += 1
        self._stats.last_reflection_time = datetime.now(UTC)

        logger.info(
            "post_mortem_completed",
            episode_id=episode_id,
            outcome=result.outcome.value,
            new_rules=len(result.new_rules),
        )

        return result

    async def daily_reflection(self, date: datetime | None = None) -> DailyReflectionResult | None:
        """Run daily reflection on trading performance.

        Args:
            date: Date to analyze. Defaults to today.

        Returns:
            DailyReflectionResult or None if no trades to analyze
        """
        if not self._initialized:
            await self.initialize()

        if date is None:
            date = datetime.now(UTC)

        date_str = date.strftime("%Y-%m-%d")

        # Get episodes for the day
        episodes = await self.episodic.get_episodes_by_date_range(
            start_date=date.replace(hour=0, minute=0, second=0, microsecond=0),
            end_date=date.replace(hour=23, minute=59, second=59, microsecond=999999),
        )

        if not episodes:
            logger.info("no_trades_for_daily_reflection", date=date_str)
            return None

        # Calculate statistics
        total_trades = len(episodes)
        winning_trades = sum(
            1 for e in episodes if e.outcome in (TradeOutcome.WIN, TradeOutcome.TAKE_PROFIT)
        )
        losing_trades = sum(
            1 for e in episodes if e.outcome in (TradeOutcome.LOSS, TradeOutcome.STOPPED_OUT)
        )
        total_pnl = sum(e.pnl or 0 for e in episodes)
        total_pnl_pct = sum(e.pnl_percentage or 0 for e in episodes)

        # Build trade summaries
        trade_summaries = self._build_trade_summaries(episodes)

        # Build the prompt
        prompt = self.DAILY_REFLECTION_PROMPT.format(
            date=date_str,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            total_pnl=total_pnl_pct,
            trade_summaries=trade_summaries,
        )

        # Get analysis from Claude
        analysis_text = await self._get_analysis(prompt)

        # Parse as JSON; fallback to basic if not available
        parsed = self._parse_json_response(analysis_text) if analysis_text else None
        if parsed is None:
            parsed = self._generate_basic_daily_reflection_json(
                date_str, total_trades, winning_trades, losing_trades, total_pnl_pct
            )

        episode_ids = [e.id for e in episodes if e.id]

        result = DailyReflectionResult(
            date=date_str,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            total_pnl=total_pnl,
            total_pnl_percentage=total_pnl_pct,
            summary=str(parsed.get("summary", f"Traded {total_trades} times today")),
            key_lessons=list(parsed.get("key_lessons", ["Continue following the trading plan"])),
            mistakes_made=list(parsed.get("mistakes_made", ["None significant"])),
            good_decisions=list(parsed.get("good_decisions", ["Maintained discipline"])),
            recommendations=list(parsed.get("recommendations", ["Stay consistent"])),
            rules_to_review=list(parsed.get("rules_to_review", [])),
            episodes_analyzed=episode_ids,
        )

        self._stats.total_daily_reflections += 1
        self._stats.last_reflection_time = datetime.now(UTC)

        # Store the reflection
        self._reflection_history.append(
            {
                "type": ReflectionType.DAILY.value,
                "result": result.to_dict(),
            }
        )

        logger.info(
            "daily_reflection_completed",
            date=date_str,
            total_trades=total_trades,
            pnl_percentage=total_pnl_pct,
        )

        return result

    async def weekly_reflection(
        self, week_end: datetime | None = None
    ) -> WeeklyReflectionResult | None:
        """Run weekly reflection to identify patterns and update rules.

        Args:
            week_end: End date of the week. Defaults to today.

        Returns:
            WeeklyReflectionResult or None if no trades to analyze
        """
        if not self._initialized:
            await self.initialize()

        if week_end is None:
            week_end = datetime.now(UTC)

        week_start = week_end - timedelta(days=7)
        week_start_str = week_start.strftime("%Y-%m-%d")
        week_end_str = week_end.strftime("%Y-%m-%d")

        # Get episodes for the week
        episodes = await self.episodic.get_episodes_by_date_range(
            start_date=week_start,
            end_date=week_end,
        )

        if not episodes:
            logger.info("no_trades_for_weekly_reflection", week=week_start_str)
            return None

        # Calculate statistics
        total_trades = len(episodes)
        winning_trades = sum(
            1 for e in episodes if e.outcome in (TradeOutcome.WIN, TradeOutcome.TAKE_PROFIT)
        )
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        total_pnl = sum(e.pnl_percentage or 0 for e in episodes)
        avg_pnl = total_pnl / total_trades if total_trades > 0 else 0

        # Build daily summaries
        daily_summaries = await self._build_daily_summaries(week_start, week_end)

        # Build symbol performance
        symbol_performance = self._build_symbol_performance(episodes)

        # Get rules performance
        rules_performance = await self._build_rules_performance()

        # Build the prompt
        prompt = self.WEEKLY_REFLECTION_PROMPT.format(
            week_start=week_start_str,
            week_end=week_end_str,
            total_trades=total_trades,
            win_rate=win_rate,
            total_pnl=total_pnl,
            avg_pnl=avg_pnl,
            daily_summaries="\n".join(daily_summaries),
            symbol_performance=json.dumps(symbol_performance, indent=2),
            rules_performance=rules_performance,
        )

        # Get analysis from Claude
        analysis_text = await self._get_analysis(prompt)

        # Parse as JSON; fallback to basic if not available
        parsed = self._parse_json_response(analysis_text) if analysis_text else None
        if parsed is None:
            parsed = self._generate_basic_weekly_reflection_json(
                total_trades, win_rate, total_pnl, symbol_performance
            )

        result = WeeklyReflectionResult(
            week_start=week_start_str,
            week_end=week_end_str,
            total_trades=total_trades,
            win_rate=win_rate,
            total_pnl=total_pnl,
            avg_pnl_per_trade=avg_pnl,
            patterns_identified=list(parsed.get("patterns_identified", [])),
            recurring_mistakes=list(parsed.get("recurring_mistakes", ["None identified"])),
            successful_strategies=list(
                parsed.get("successful_strategies", ["Maintained discipline"])
            ),
            new_rules_created=list(parsed.get("new_rules_created", [])),
            rules_updated=list(parsed.get("rules_updated", [])),
            rules_deprecated=list(parsed.get("rules_deprecated", [])),
            performance_by_symbol=symbol_performance,
            focus_areas=list(parsed.get("focus_areas", ["Consistency"])),
            improvement_plan=str(parsed.get("improvement_plan", "Continue current approach")),
            daily_summaries=daily_summaries,
        )

        # Create new rules
        for rule_data in result.new_rules_created:
            await self._create_rule_from_reflection(rule_data)
            self._stats.rules_created += 1

        # Update existing rules
        for rule_update in result.rules_updated:
            await self._update_rule_from_reflection(rule_update)
            self._stats.rules_updated += 1

        # Deprecate rules
        for rule_id in result.rules_deprecated:
            await self.semantic.update_rule_status(rule_id, RuleStatus.DEPRECATED)

        self._stats.total_weekly_reflections += 1
        self._stats.patterns_identified += len(result.patterns_identified)
        self._stats.last_reflection_time = datetime.now(UTC)

        # Store the reflection
        self._reflection_history.append(
            {
                "type": ReflectionType.WEEKLY.value,
                "result": result.to_dict(),
            }
        )

        logger.info(
            "weekly_reflection_completed",
            week=week_start_str,
            total_trades=total_trades,
            new_rules=len(result.new_rules_created),
            patterns=len(result.patterns_identified),
        )

        return result

    async def _get_analysis(self, prompt: str) -> str | None:
        """Get analysis from Claude with retry on transient errors.

        Args:
            prompt: The analysis prompt

        Returns:
            Analysis text or None if failed
        """
        if self._client is None:
            return None

        try:
            response = self._call_api_with_retry(prompt)

            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            self._stats.total_tokens_used += input_tokens + output_tokens
            self._stats.total_input_tokens += input_tokens
            self._stats.total_output_tokens += output_tokens

            # Calculate cost
            agent_settings = self.settings.agent
            input_cost = (input_tokens / 1000) * agent_settings.input_cost_per_1k
            output_cost = (output_tokens / 1000) * agent_settings.output_cost_per_1k
            self._stats.total_cost_usd += round(input_cost + output_cost, 6)

            # Extract text from response
            text_blocks = [block.text for block in response.content if block.type == "text"]
            return " ".join(text_blocks)

        except Exception as e:
            logger.error("reflection_analysis_failed", error=str(e))
            return None

    def _call_api_with_retry(self, prompt: str) -> Any:
        """Call Anthropic API with retry logic.

        Args:
            prompt: The prompt to send

        Returns:
            API response
        """

        @retry(
            retry=retry_if_exception(_is_retryable_api_error),
            stop=stop_after_attempt(3),
            wait=wait_exponential_jitter(initial=1, max=30, jitter=2),
            before_sleep=lambda retry_state: logger.warning(
                "reflection_api_retry",
                attempt=retry_state.attempt_number,
                error=str(retry_state.outcome.exception()) if retry_state.outcome else None,
            ),
            reraise=True,
        )
        def _make_request() -> Any:
            return self._client.messages.create(
                model=self.settings.agent.model,
                max_tokens=2048,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )

        return _make_request()

    def _parse_json_response(self, text: str) -> dict[str, Any] | None:
        """Parse a JSON response from Claude, tolerant of markdown fences.

        Args:
            text: Raw response text

        Returns:
            Parsed dict or None if parsing fails
        """
        if not text:
            return None

        # Try direct parse first
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code fence
        stripped = text.strip()
        if "```" in stripped:
            # Find content between code fences
            start = stripped.find("```")
            end = stripped.rfind("```")
            if start != end:
                inner = stripped[start:end]
                # Remove the opening fence line
                first_newline = inner.find("\n")
                if first_newline != -1:
                    inner = inner[first_newline + 1 :]
                try:
                    return json.loads(inner.strip())
                except json.JSONDecodeError:
                    pass

        # Try finding first { to last }
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end > brace_start:
            try:
                return json.loads(text[brace_start : brace_end + 1])
            except json.JSONDecodeError:
                pass

        logger.warning("failed_to_parse_json_response", text_preview=text[:200])
        return None

    def _generate_basic_post_mortem_json(self, episode: TradeEpisode) -> dict[str, Any]:
        """Generate basic post-mortem as a dict without LLM."""
        pnl = episode.pnl_percentage or 0

        if pnl > 0:
            return {
                "lessons_learned": f"Profitable trade on {episode.symbol}. Entry reasoning was validated.",
                "what_went_well": "Trade closed in profit as planned.",
                "what_went_wrong": "None identified in this winning trade.",
                "would_take_again": True,
                "new_rules": [],
                "pattern_observations": [],
            }
        return {
            "lessons_learned": f"Loss on {episode.symbol}. Review entry criteria.",
            "what_went_well": "Risk was managed with stop loss.",
            "what_went_wrong": "Entry timing or criteria may need review.",
            "would_take_again": False,
            "new_rules": [],
            "pattern_observations": [],
        }

    def _generate_basic_daily_reflection_json(
        self,
        date_str: str,
        total_trades: int,
        winning: int,
        losing: int,
        pnl_pct: float,
    ) -> dict[str, Any]:
        """Generate basic daily reflection as dict without LLM."""
        win_rate = (winning / total_trades * 100) if total_trades > 0 else 0

        return {
            "summary": f"{total_trades} trades on {date_str} with {win_rate:.1f}% win rate.",
            "key_lessons": ["Maintain discipline" if pnl_pct > 0 else "Review entry criteria"],
            "mistakes_made": ["None significant" if pnl_pct > 0 else "Possible overtrading"],
            "good_decisions": [
                "Followed the plan" if winning > losing else "Respected stop losses"
            ],
            "recommendations": [
                "Continue current approach" if pnl_pct > 0 else "Be more selective with entries"
            ],
            "rules_to_review": [],
        }

    def _generate_basic_weekly_reflection_json(
        self,
        _total_trades: int,
        win_rate: float,
        total_pnl: float,
        symbol_perf: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate basic weekly reflection as dict without LLM."""
        best_symbol = (
            max(symbol_perf.items(), key=lambda x: x[1].get("pnl", 0))[0] if symbol_perf else "N/A"
        )

        return {
            "patterns_identified": [
                {
                    "description": "Consistent performance"
                    if win_rate > 50
                    else "Need improvement in entry timing"
                }
            ],
            "recurring_mistakes": [
                "None significant" if win_rate > 50 else "Possible premature entries"
            ],
            "successful_strategies": [f"Best performance on {best_symbol}"],
            "new_rules_created": [],
            "rules_updated": [],
            "rules_deprecated": [],
            "focus_areas": ["Maintain consistency" if total_pnl > 0 else "Improve entry criteria"],
            "improvement_plan": (
                "Continue current approach" if total_pnl > 0 else "Review and refine entry signals"
            ),
        }

    def _build_trade_summaries(self, episodes: list[TradeEpisode]) -> str:
        """Build trade summaries for daily reflection."""
        summaries = []
        for ep in episodes:
            outcome = ep.outcome.value if ep.outcome else "unknown"
            pnl = ep.pnl_percentage or 0
            summaries.append(f"- {ep.symbol}: {outcome} ({pnl:+.2f}%) - {ep.entry_reasoning[:100]}")
        return "\n".join(summaries)

    async def _build_daily_summaries(self, start: datetime, end: datetime) -> list[str]:
        """Build daily summaries for weekly reflection."""
        summaries = []
        current = start

        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            episodes = await self.episodic.get_episodes_by_date_range(
                start_date=current.replace(hour=0, minute=0, second=0),
                end_date=current.replace(hour=23, minute=59, second=59),
            )

            if episodes:
                wins = sum(1 for e in episodes if e.outcome == TradeOutcome.WIN)
                pnl = sum(e.pnl_percentage or 0 for e in episodes)
                summaries.append(f"{date_str}: {len(episodes)} trades, {wins} wins, {pnl:+.2f}%")

            current += timedelta(days=1)

        return summaries

    def _build_symbol_performance(self, episodes: list[TradeEpisode]) -> dict[str, dict[str, Any]]:
        """Build performance breakdown by symbol."""
        performance: dict[str, dict[str, Any]] = {}

        for ep in episodes:
            if ep.symbol not in performance:
                performance[ep.symbol] = {
                    "trades": 0,
                    "wins": 0,
                    "pnl": 0.0,
                }

            performance[ep.symbol]["trades"] += 1
            if ep.outcome in (TradeOutcome.WIN, TradeOutcome.TAKE_PROFIT):
                performance[ep.symbol]["wins"] += 1
            performance[ep.symbol]["pnl"] += ep.pnl_percentage or 0

        # Calculate win rates
        for symbol in performance:
            trades = performance[symbol]["trades"]
            wins = performance[symbol]["wins"]
            performance[symbol]["win_rate"] = (wins / trades * 100) if trades > 0 else 0

        return performance

    async def _build_rules_performance(self) -> str:
        """Build rules performance summary."""
        rules = await self.semantic.get_active_rules()
        if not rules:
            return "No rules have been applied yet."

        lines = []
        for rule in rules[:10]:  # Top 10 rules
            success_rate = f"{rule.success_rate:.0%}" if rule.times_applied > 0 else "N/A"
            lines.append(f"- {rule.name}: applied {rule.times_applied}x, success {success_rate}")

        return "\n".join(lines)

    async def _create_rule_from_reflection(self, rule_data: dict[str, Any]) -> int | None:
        """Create a new rule from reflection insights."""
        if not rule_data.get("name") or not rule_data.get("condition"):
            return None

        rule_id = await self.semantic.create_rule(
            name=rule_data["name"],
            description=rule_data.get("description", "Created from reflection"),
            condition=rule_data["condition"],
            source=RuleSource.LEARNED,
            category=rule_data.get("category", "general"),
        )

        logger.info("rule_created_from_reflection", rule_id=rule_id, name=rule_data["name"])
        return rule_id

    async def _update_rule_from_reflection(self, update_data: dict[str, Any]) -> None:
        """Update an existing rule based on reflection."""
        rule_id = update_data.get("id")
        if not rule_id:
            return

        if "confidence" in update_data:
            await self.semantic.update_rule_confidence(rule_id, update_data["confidence"])

        if "status" in update_data:
            await self.semantic.update_rule_status(rule_id, RuleStatus(update_data["status"]))

    def get_stats(self) -> dict[str, Any]:
        """Get reflection engine statistics."""
        return {
            "total_post_mortems": self._stats.total_post_mortems,
            "total_daily_reflections": self._stats.total_daily_reflections,
            "total_weekly_reflections": self._stats.total_weekly_reflections,
            "rules_created": self._stats.rules_created,
            "rules_updated": self._stats.rules_updated,
            "patterns_identified": self._stats.patterns_identified,
            "total_tokens_used": self._stats.total_tokens_used,
            "total_input_tokens": self._stats.total_input_tokens,
            "total_output_tokens": self._stats.total_output_tokens,
            "total_cost_usd": self._stats.total_cost_usd,
            "last_reflection_time": (
                self._stats.last_reflection_time.isoformat()
                if self._stats.last_reflection_time
                else None
            ),
        }

    def get_recent_reflections(
        self, reflection_type: ReflectionType | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get recent reflections.

        Args:
            reflection_type: Filter by type. None for all.
            limit: Maximum number to return.

        Returns:
            List of recent reflection results.
        """
        reflections = self._reflection_history

        if reflection_type:
            reflections = [r for r in reflections if r["type"] == reflection_type.value]

        return reflections[-limit:]


# Global instance
_reflection_engine: ReflectionEngine | None = None


def get_reflection_engine() -> ReflectionEngine:
    """Get the global reflection engine instance."""
    global _reflection_engine
    if _reflection_engine is None:
        _reflection_engine = ReflectionEngine()
    return _reflection_engine
