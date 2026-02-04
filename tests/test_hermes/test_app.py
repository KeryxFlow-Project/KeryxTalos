"""Tests for Hermes app - logic and state tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from keryxflow.hermes.app import KeryxFlowApp


class TestKeryxFlowAppInit:
    """Tests for KeryxFlowApp initialization."""

    def test_init_defaults(self):
        """Test app initializes with defaults."""
        app = KeryxFlowApp()
        assert app.exchange_client is None
        assert app.paper_engine is None
        assert app.trading_engine is None
        assert app.trading_session is None
        assert app._paused is False
        assert app._current_symbol_index == 0

    def test_init_with_session(self):
        """Test app initializes with trading session."""
        mock_session = MagicMock()
        app = KeryxFlowApp(trading_session=mock_session)
        assert app.trading_session is mock_session

    def test_init_with_engines(self):
        """Test app initializes with engines."""
        mock_event_bus = MagicMock()
        mock_exchange = MagicMock()
        mock_paper = MagicMock()
        mock_trading = MagicMock()

        app = KeryxFlowApp(
            event_bus=mock_event_bus,
            exchange_client=mock_exchange,
            paper_engine=mock_paper,
            trading_engine=mock_trading,
        )

        assert app.event_bus is mock_event_bus
        assert app.exchange_client is mock_exchange
        assert app.paper_engine is mock_paper
        assert app.trading_engine is mock_trading


class TestKeryxFlowAppBindings:
    """Tests for app keybindings."""

    def test_bindings_exist(self):
        """Test all expected bindings are defined."""
        app = KeryxFlowApp()
        binding_keys = [b.key for b in app.BINDINGS]

        assert "q" in binding_keys  # Quit
        assert "p" in binding_keys  # Panic
        assert "space" in binding_keys  # Pause/Resume
        assert "a" in binding_keys  # Toggle Agent
        assert "question_mark" in binding_keys  # Help
        assert "l" in binding_keys  # Toggle Logs
        assert "s" in binding_keys  # Cycle Symbol

    def test_agent_binding_description(self):
        """Test agent binding has correct description."""
        app = KeryxFlowApp()
        agent_binding = next((b for b in app.BINDINGS if b.key == "a"), None)

        assert agent_binding is not None
        assert "Agent" in agent_binding.description


class TestKeryxFlowAppCurrentSymbol:
    """Tests for symbol management."""

    def test_current_symbol_default(self):
        """Test current symbol returns first symbol."""
        app = KeryxFlowApp()
        assert app.current_symbol == app._symbols[0]

    def test_current_symbol_after_cycle(self):
        """Test current symbol changes after cycling."""
        app = KeryxFlowApp()
        first_symbol = app.current_symbol

        app._current_symbol_index = 1
        if len(app._symbols) > 1:
            assert app.current_symbol != first_symbol


class TestKeryxFlowAppToggleAgent:
    """Tests for agent toggle action logic."""

    @pytest.mark.asyncio
    async def test_toggle_agent_no_session_no_engine(self):
        """Test toggle agent when no session and no engine."""
        app = KeryxFlowApp()

        # Mock the query_one to avoid DOM issues
        mock_logs = MagicMock()
        mock_logs.add_entry = MagicMock()
        mock_agent_widget = MagicMock()

        with patch.object(app, "query_one") as mock_query:
            mock_query.side_effect = lambda selector, _cls: (
                mock_logs if "#logs" in selector else mock_agent_widget
            )
            with patch.object(app, "notify"):
                await app.action_toggle_agent()

        # Should log warning about no trading engine
        mock_logs.add_entry.assert_called()
        call_args = [call[0][0] for call in mock_logs.add_entry.call_args_list]
        assert any("No trading engine" in arg for arg in call_args)

    @pytest.mark.asyncio
    async def test_toggle_agent_creates_session(self):
        """Test toggle agent creates session when engine available."""
        mock_engine = MagicMock()
        mock_event_bus = MagicMock()
        app = KeryxFlowApp(trading_engine=mock_engine, event_bus=mock_event_bus)

        mock_logs = MagicMock()
        mock_agent_widget = MagicMock()
        mock_agent_widget.is_running = False

        mock_session = MagicMock()
        mock_session.start = AsyncMock(return_value=True)
        mock_session.state = MagicMock()
        mock_session.state.value = "idle"

        with (
            patch.object(app, "query_one") as mock_query,
            patch("keryxflow.hermes.app.TradingSession", return_value=mock_session),
            patch.object(app, "notify"),
        ):
            mock_query.side_effect = lambda selector, _cls: (
                mock_logs if "#logs" in selector else mock_agent_widget
            )
            await app.action_toggle_agent()

        # Session should be created and started
        mock_session.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_toggle_agent_pauses_running_session(self):
        """Test toggle agent pauses a running session."""
        mock_session = MagicMock()
        mock_session.pause = AsyncMock(return_value=True)
        mock_session.state = MagicMock()
        mock_session.state.value = "running"

        app = KeryxFlowApp(trading_session=mock_session)

        mock_logs = MagicMock()
        mock_agent_widget = MagicMock()
        mock_agent_widget.is_running = True

        with patch.object(app, "query_one") as mock_query:
            mock_query.side_effect = lambda selector, _cls: (
                mock_logs if "#logs" in selector else mock_agent_widget
            )
            with patch.object(app, "notify"):
                await app.action_toggle_agent()

        mock_session.pause.assert_called_once()

    @pytest.mark.asyncio
    async def test_toggle_agent_resumes_paused_session(self):
        """Test toggle agent resumes a paused session."""
        mock_session = MagicMock()
        mock_session.resume = AsyncMock(return_value=True)
        mock_session.state = MagicMock()
        mock_session.state.value = "paused"

        app = KeryxFlowApp(trading_session=mock_session)

        mock_logs = MagicMock()
        mock_agent_widget = MagicMock()
        mock_agent_widget.is_running = False

        with patch.object(app, "query_one") as mock_query:
            mock_query.side_effect = lambda selector, _cls: (
                mock_logs if "#logs" in selector else mock_agent_widget
            )
            with patch.object(app, "notify"):
                await app.action_toggle_agent()

        mock_session.resume.assert_called_once()


class TestKeryxFlowAppSessionEvents:
    """Tests for session event handlers."""

    @pytest.mark.asyncio
    async def test_on_session_state_changed_running(self):
        """Test session state changed to running."""
        mock_session = MagicMock()
        mock_session.get_status = MagicMock(return_value={"state": "running"})

        app = KeryxFlowApp(trading_session=mock_session)

        mock_logs = MagicMock()
        mock_agent_widget = MagicMock()

        mock_event = MagicMock()
        mock_event.data = {"new_state": "running", "old_state": "idle"}

        with patch.object(app, "query_one") as mock_query:
            mock_query.side_effect = lambda selector, _cls: (
                mock_logs if "#logs" in selector else mock_agent_widget
            )
            with patch.object(app, "notify"):
                await app._on_session_state_changed(mock_event)

        # Agent widget should be updated
        mock_agent_widget.set_status.assert_called()
        # Should log the state change
        mock_logs.add_entry.assert_called()

    @pytest.mark.asyncio
    async def test_on_session_state_changed_error(self):
        """Test session state changed to error."""
        mock_session = MagicMock()
        mock_session.get_status = MagicMock(return_value={"state": "error"})

        app = KeryxFlowApp(trading_session=mock_session)

        mock_logs = MagicMock()
        mock_agent_widget = MagicMock()

        mock_event = MagicMock()
        mock_event.data = {
            "new_state": "error",
            "old_state": "running",
            "reason": "API error",
        }

        with patch.object(app, "query_one") as mock_query:
            mock_query.side_effect = lambda selector, _cls: (
                mock_logs if "#logs" in selector else mock_agent_widget
            )
            with patch.object(app, "notify"):
                await app._on_session_state_changed(mock_event)

        # Should log error with reason
        call_args = [call[0][0] for call in mock_logs.add_entry.call_args_list]
        assert any("ERROR" in arg for arg in call_args)

    @pytest.mark.asyncio
    async def test_on_agent_cycle_refreshes_widgets(self):
        """Test agent cycle completion refreshes widgets."""
        mock_session = MagicMock()
        mock_session.get_status = MagicMock(return_value={"state": "running"})

        app = KeryxFlowApp(trading_session=mock_session)

        mock_agent_widget = MagicMock()
        mock_positions = MagicMock()
        mock_positions.refresh_data = AsyncMock()
        mock_stats = MagicMock()
        mock_stats.refresh_data = AsyncMock()
        mock_aegis = MagicMock()
        mock_aegis.refresh_data = AsyncMock()

        mock_event = MagicMock()
        mock_event.data = {"cycle": 1}

        def mock_query(selector, _cls):
            if "#agent" in selector:
                return mock_agent_widget
            if "#positions" in selector:
                return mock_positions
            if "#stats" in selector:
                return mock_stats
            if "#aegis" in selector:
                return mock_aegis
            return MagicMock()

        with patch.object(app, "query_one", side_effect=mock_query):
            await app._on_agent_cycle(mock_event)

        # All widgets should be refreshed
        mock_agent_widget.set_status.assert_called()
        mock_positions.refresh_data.assert_called()
        mock_stats.refresh_data.assert_called()
        mock_aegis.refresh_data.assert_called()
