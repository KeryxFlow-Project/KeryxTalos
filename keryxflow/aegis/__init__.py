"""Aegis - Risk management and mathematical trading layer."""

from keryxflow.aegis.circuit import CircuitBreaker, get_circuit_breaker
from keryxflow.aegis.guardrails import (
    GuardrailCheckResult,
    GuardrailEnforcer,
    GuardrailViolation,
    TradingGuardrails,
    get_guardrail_enforcer,
    get_guardrails,
)
from keryxflow.aegis.portfolio import PortfolioState, PositionState, create_portfolio_state
from keryxflow.aegis.profiles import get_risk_profile
from keryxflow.aegis.quant import QuantEngine, get_quant_engine
from keryxflow.aegis.risk import RiskManager, get_risk_manager
from keryxflow.aegis.trailing import (
    TrailingStopManager,
    TrailingStopState,
    get_trailing_stop_manager,
)

__all__ = [
    # Circuit breaker
    "CircuitBreaker",
    "get_circuit_breaker",
    # Guardrails
    "GuardrailCheckResult",
    "GuardrailEnforcer",
    "GuardrailViolation",
    "TradingGuardrails",
    "get_guardrail_enforcer",
    "get_guardrails",
    # Portfolio
    "PortfolioState",
    "PositionState",
    "create_portfolio_state",
    # Profiles
    "get_risk_profile",
    # Quant
    "QuantEngine",
    "get_quant_engine",
    # Risk
    "RiskManager",
    "get_risk_manager",
    # Trailing stop
    "TrailingStopManager",
    "TrailingStopState",
    "get_trailing_stop_manager",
]
