"""Tests for multi-agent coordinator."""

from keryxflow.agent.multi_agent import AgentOrchestrator, AgentRole


def test_get_tools_and_prompts_for_roles():
    """Verify get_tools_for_role returns correct tools and prompts are non-empty."""
    orchestrator = AgentOrchestrator()

    expected_tools = {
        AgentRole.ANALYST: [
            "get_current_price",
            "get_ohlcv",
            "get_order_book",
            "calculate_indicators",
            "get_trading_rules",
            "recall_similar_trades",
            "get_market_patterns",
        ],
        AgentRole.RISK_MANAGER: [
            "get_portfolio_state",
            "get_balance",
            "get_positions",
            "calculate_position_size",
            "calculate_risk_reward",
            "calculate_stop_loss",
        ],
        AgentRole.EXECUTOR: [
            "place_order",
            "close_position",
            "set_stop_loss",
            "set_take_profit",
            "cancel_order",
            "close_all_positions",
        ],
    }

    for role in AgentRole:
        assert orchestrator.get_tools_for_role(role) == expected_tools[role]
        prompt = orchestrator.get_system_prompt_for_role(role)
        assert isinstance(prompt, str)
        assert len(prompt) > 0
