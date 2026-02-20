"""Multi-agent coordinator with role-based tool filtering."""

from enum import Enum


class AgentRole(str, Enum):
    """Roles for specialized trading agents."""

    ANALYST = "analyst"
    RISK_MANAGER = "risk_manager"
    EXECUTOR = "executor"


ROLE_TOOLS: dict[AgentRole, list[str]] = {
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

ROLE_PROMPTS: dict[AgentRole, str] = {
    AgentRole.ANALYST: (
        "You are a market analyst agent. Your role is to perceive market data, "
        "compute technical indicators, and identify trading patterns and rules."
    ),
    AgentRole.RISK_MANAGER: (
        "You are a risk manager agent. Your role is to evaluate portfolio state, "
        "calculate position sizes, and assess risk-reward for proposed trades."
    ),
    AgentRole.EXECUTOR: (
        "You are a trade executor agent. Your role is to place orders, manage "
        "stop-losses and take-profits, and close positions when instructed."
    ),
}


class AgentOrchestrator:
    """Coordinates multiple role-based agents with filtered tool access."""

    def __init__(self) -> None:
        self.roles = list(AgentRole)

    def get_tools_for_role(self, role: AgentRole) -> list[str]:
        """Return the allowed tool names for a given role."""
        return ROLE_TOOLS[role]

    def get_system_prompt_for_role(self, role: AgentRole) -> str:
        """Return a system prompt describing the role's responsibilities."""
        return ROLE_PROMPTS[role]


_orchestrator: AgentOrchestrator | None = None


def get_agent_orchestrator() -> AgentOrchestrator:
    """Get the global AgentOrchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator
