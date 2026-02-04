"""End-to-end integration tests for Agent Session.

These tests verify the full flow from session start to agent cycle completion,
including event handling, widget updates, and guardrail enforcement.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from keryxflow.agent.session import SessionState, SessionStats, TradingSession
from keryxflow.core.events import Event, EventBus, EventType


class TestSessionLifecycleE2E:
    """End-to-end tests for session lifecycle."""

    @pytest.fixture
    def mock_engine(self):
        """Create a mock trading engine."""
        engine = MagicMock()
        engine.is_running = True
        return engine

    @pytest.fixture
    def mock_agent(self):
        """Create a mock cognitive agent."""
        agent = MagicMock()
        agent.run_cycle = AsyncMock(
            return_value=MagicMock(
                success=True,
                tool_calls=2,
                tokens_used=150,
                message="Cycle completed",
            )
        )
        return agent

    @pytest.fixture
    def event_bus(self):
        """Create a fresh event bus."""
        return EventBus()

    @pytest.mark.asyncio
    async def test_session_start_stop_cycle(self, mock_engine, mock_agent, event_bus):
        """Test complete session start and stop cycle."""
        # Create session with pre-initialized agent
        session = TradingSession(
            engine=mock_engine,
            agent=mock_agent,  # Pass agent directly to avoid import
        )
        session._event_bus = event_bus  # Use test event bus

        # Verify initial state
        assert session.state == SessionState.IDLE

        # Start session - mock agent initialization and engine methods
        mock_agent.initialize = AsyncMock()
        mock_engine.start = AsyncMock()
        mock_engine.stop = AsyncMock()

        with patch.object(session, "_run_agent_loop", new_callable=AsyncMock):
            success = await session.start()
            assert success
            assert session.state == SessionState.RUNNING

        # Stop session
        success = await session.stop()
        assert success
        assert session.state == SessionState.STOPPED

    @pytest.mark.asyncio
    async def test_session_pause_resume_cycle(self, mock_engine, mock_agent, event_bus):
        """Test session pause and resume cycle."""
        # Create session with pre-initialized agent
        session = TradingSession(
            engine=mock_engine,
            agent=mock_agent,
        )
        session._event_bus = event_bus

        # Mock agent and engine methods
        mock_agent.initialize = AsyncMock()
        mock_engine.start = AsyncMock()
        mock_engine.stop = AsyncMock()

        # Start session
        with patch.object(session, "_run_agent_loop", new_callable=AsyncMock):
            await session.start()
            assert session.state == SessionState.RUNNING

        # Pause session
        success = await session.pause()
        assert success
        assert session.state == SessionState.PAUSED

        # Resume session
        with patch.object(session, "_run_agent_loop", new_callable=AsyncMock):
            success = await session.resume()
            assert success
            assert session.state == SessionState.RUNNING

        # Stop session
        await session.stop()

    @pytest.mark.asyncio
    async def test_session_stats_accumulate(self, mock_engine, mock_agent, event_bus):
        """Test that session stats accumulate correctly."""
        # Create session with pre-initialized agent
        session = TradingSession(
            engine=mock_engine,
            agent=mock_agent,
        )
        session._event_bus = event_bus

        # Verify initial stats
        status = session.get_status()
        assert status["stats"]["cycles_completed"] == 0
        assert status["stats"]["tokens_used"] == 0

        # Record some stats
        session._stats.cycles_completed = 5
        session._stats.cycles_successful = 4
        session._stats.tool_calls = 10
        session._stats.tokens_used = 1000

        # Verify updated stats
        status = session.get_status()
        assert status["stats"]["cycles_completed"] == 5
        assert status["stats"]["cycles_successful"] == 4
        assert status["stats"]["tool_calls"] == 10
        assert status["stats"]["tokens_used"] == 1000


class TestEventFlowE2E:
    """End-to-end tests for event flow from session to subscribers."""

    @pytest.mark.asyncio
    async def test_agent_cycle_events_flow(self):
        """Test that agent cycle events flow to subscribers."""
        event_bus = EventBus()

        # Track events
        cycle_started_events = []
        cycle_completed_events = []

        async def on_cycle_started(event: Event):
            cycle_started_events.append(event)

        async def on_cycle_completed(event: Event):
            cycle_completed_events.append(event)

        event_bus.subscribe(EventType.AGENT_CYCLE_STARTED, on_cycle_started)
        event_bus.subscribe(EventType.AGENT_CYCLE_COMPLETED, on_cycle_completed)

        # Use publish_sync to ensure immediate delivery
        await event_bus.publish_sync(
            Event(
                type=EventType.AGENT_CYCLE_STARTED,
                data={"cycle": 1, "timestamp": datetime.now(UTC).isoformat()},
            )
        )

        await event_bus.publish_sync(
            Event(
                type=EventType.AGENT_CYCLE_COMPLETED,
                data={
                    "cycle": 1,
                    "success": True,
                    "tool_calls": 3,
                    "tokens": 200,
                },
            )
        )

        assert len(cycle_started_events) == 1
        assert len(cycle_completed_events) == 1
        assert cycle_completed_events[0].data["success"] is True

    @pytest.mark.asyncio
    async def test_session_state_change_events(self):
        """Test session state change events contain correct data."""
        event_bus = EventBus()
        state_changes = []

        async def on_state_change(event: Event):
            state_changes.append(event)

        event_bus.subscribe(EventType.SESSION_STATE_CHANGED, on_state_change)

        # Use publish_sync to ensure immediate delivery
        await event_bus.publish_sync(
            Event(
                type=EventType.SESSION_STATE_CHANGED,
                data={
                    "old_state": "idle",
                    "new_state": "running",
                    "reason": "User started session",
                },
            )
        )

        await event_bus.publish_sync(
            Event(
                type=EventType.SESSION_STATE_CHANGED,
                data={
                    "old_state": "running",
                    "new_state": "paused",
                    "reason": "User paused session",
                },
            )
        )

        assert len(state_changes) == 2
        assert state_changes[0].data["new_state"] == "running"
        assert state_changes[1].data["new_state"] == "paused"


class TestGuardrailEnforcementE2E:
    """End-to-end tests for guardrail enforcement during agent execution."""

    @pytest.mark.asyncio
    async def test_guarded_tools_validate_guardrails(self):
        """Test that execution tools validate guardrails."""
        from keryxflow.agent.executor import ToolExecutor
        from keryxflow.agent.tools import (
            BaseTool,
            ToolCategory,
            ToolParameter,
            ToolResult,
            TradingToolkit,
        )

        toolkit = TradingToolkit()
        executor = ToolExecutor(toolkit)

        # Register a mock guarded tool using proper property syntax
        class MockPlaceOrder(BaseTool):
            @property
            def name(self) -> str:
                return "mock_place_order"

            @property
            def description(self) -> str:
                return "Mock place order"

            @property
            def category(self) -> ToolCategory:
                return ToolCategory.EXECUTION

            @property
            def parameters(self) -> list[ToolParameter]:
                return [
                    ToolParameter(
                        name="symbol", type="string", description="Symbol", required=True
                    ),
                    ToolParameter(name="side", type="string", description="Side", required=True),
                    ToolParameter(
                        name="quantity", type="number", description="Quantity", required=True
                    ),
                ]

            async def execute(self, **_kwargs) -> ToolResult:
                return ToolResult(success=True, data={"order_id": "123"})

        toolkit.register(MockPlaceOrder())

        # Verify tool is guarded
        tool = toolkit.get_tool("mock_place_order")
        assert tool is not None
        assert tool.is_guarded

        # Execute with mock guardrail check (returns ToolResult)
        mock_guardrail_result = ToolResult(success=True)
        with patch.object(
            executor, "_check_guardrails", AsyncMock(return_value=mock_guardrail_result)
        ):
            result = await executor.execute_guarded(
                "mock_place_order",
                symbol="BTC/USDT",
                side="buy",
                quantity=0.1,
            )

        assert result.success

    @pytest.mark.asyncio
    async def test_guardrail_rejection_blocks_execution(self):
        """Test that guardrail rejection blocks tool execution."""
        from keryxflow.agent.executor import ToolExecutor
        from keryxflow.agent.tools import (
            BaseTool,
            ToolCategory,
            ToolParameter,
            ToolResult,
            TradingToolkit,
        )

        toolkit = TradingToolkit()
        executor = ToolExecutor(toolkit)

        class MockPlaceOrder(BaseTool):
            @property
            def name(self) -> str:
                return "mock_place_order"

            @property
            def description(self) -> str:
                return "Mock place order"

            @property
            def category(self) -> ToolCategory:
                return ToolCategory.EXECUTION

            @property
            def parameters(self) -> list[ToolParameter]:
                return [
                    ToolParameter(
                        name="symbol", type="string", description="Symbol", required=True
                    ),
                    ToolParameter(name="side", type="string", description="Side", required=True),
                    ToolParameter(
                        name="quantity", type="number", description="Quantity", required=True
                    ),
                ]

            async def execute(self, **_kwargs) -> ToolResult:
                return ToolResult(success=True, data={"order_id": "123"})

        toolkit.register(MockPlaceOrder())

        # Mock guardrail rejection (returns ToolResult with error)
        mock_rejection = ToolResult(
            success=False, error="Guardrail violation: Position size exceeds limit"
        )
        with patch.object(
            executor,
            "_check_guardrails",
            AsyncMock(return_value=mock_rejection),
        ):
            result = await executor.execute_guarded(
                "mock_place_order",
                symbol="BTC/USDT",
                side="buy",
                quantity=10.0,
            )

        assert not result.success
        assert result.error is not None
        assert "Position size exceeds limit" in result.error


class TestWidgetIntegrationE2E:
    """End-to-end tests for widget integration with session."""

    def test_agent_widget_status_update(self):
        """Test AgentWidget updates correctly with session status."""
        from keryxflow.hermes.widgets.agent import AgentWidget

        widget = AgentWidget()

        # Initial state
        assert not widget.is_enabled
        assert not widget.is_running
        assert widget.cycles_completed == 0

        # Update with session status
        widget.set_enabled(True)
        widget.set_status(
            {
                "state": "running",
                "stats": {
                    "cycles_completed": 10,
                    "cycles_successful": 8,
                    "trades_executed": 3,
                    "win_rate": 66.7,
                    "total_pnl": 150.50,
                    "tool_calls": 25,
                    "tokens_used": 5000,
                    "cycles_per_minute": 2.5,
                },
            }
        )

        assert widget.is_enabled
        assert widget.is_running
        assert widget.cycles_completed == 10

    def test_agent_widget_state_transitions(self):
        """Test AgentWidget reflects state transitions correctly."""
        from keryxflow.hermes.widgets.agent import AgentWidget

        widget = AgentWidget()
        widget.set_enabled(True)

        # Idle state
        widget.set_status({"state": "idle", "stats": {}})
        assert not widget.is_running

        # Running state
        widget.set_status({"state": "running", "stats": {}})
        assert widget.is_running

        # Paused state
        widget.set_status({"state": "paused", "stats": {}})
        assert not widget.is_running

        # Stopped state
        widget.set_status({"state": "stopped", "stats": {}})
        assert not widget.is_running

        # Error state
        widget.set_status({"state": "error", "stats": {}})
        assert not widget.is_running


class TestSessionStatsE2E:
    """End-to-end tests for SessionStats tracking."""

    def test_stats_win_rate_calculation(self):
        """Test win rate calculation in stats."""
        stats = SessionStats()

        # Initial state (win_rate is a property)
        assert stats.win_rate == 0.0

        # After some trades
        stats.trades_won = 6
        stats.trades_lost = 4

        # win_rate property calculates automatically
        assert stats.win_rate == 60.0

    def test_stats_pnl_tracking(self):
        """Test PnL tracking in stats."""
        stats = SessionStats()

        # Initial state
        assert stats.total_pnl == 0.0

        # Simulate adding trades manually (as TradingSession.record_trade does)
        # Trade 1: Win +100
        stats.trades_executed += 1
        stats.trades_won += 1
        stats.total_pnl += 100.0

        # Trade 2: Loss -30
        stats.trades_executed += 1
        stats.trades_lost += 1
        stats.total_pnl -= 30.0

        # Trade 3: Win +50
        stats.trades_executed += 1
        stats.trades_won += 1
        stats.total_pnl += 50.0

        assert stats.trades_executed == 3
        assert stats.trades_won == 2
        assert stats.total_pnl == 120.0
        assert stats.win_rate == pytest.approx(66.67, rel=0.01)

    def test_stats_serialization(self):
        """Test stats serialize to dict correctly."""
        stats = SessionStats()
        stats.cycles_completed = 100
        stats.cycles_successful = 95
        stats.trades_executed = 20
        stats.trades_won = 14
        stats.trades_lost = 6
        stats.total_pnl = 500.0
        stats.tool_calls = 200
        stats.tokens_used = 50000

        data = stats.to_dict()

        assert data["cycles_completed"] == 100
        assert data["cycles_successful"] == 95
        assert data["trades_executed"] == 20
        assert data["win_rate"] == 70.0
        assert data["total_pnl"] == 500.0
        assert data["tool_calls"] == 200
        assert data["tokens_used"] == 50000
