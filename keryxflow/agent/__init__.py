"""Agent module for AI-first trading.

This module provides tools and infrastructure for the cognitive trading agent
to perceive market conditions, analyze data, and execute trades safely.

Tool Categories:
- PERCEPTION: Read-only market data (get_price, get_ohlcv, etc.)
- ANALYSIS: Computation tools (calculate_indicators, position_size, etc.)
- INTROSPECTION: Memory access (get_trading_rules, recall_similar_trades)
- EXECUTION: Order execution - GUARDED (place_order, close_position, etc.)

Cognitive Agent:
- CognitiveAgent: AI-first autonomous trading agent
- Cycle: Perceive → Remember → Analyze → Decide → Validate → Execute → Learn

Learning & Reflection:
- ReflectionEngine: Post-mortem, daily, and weekly reflections
- StrategyManager: Strategy selection and adaptation
- TaskScheduler: Scheduled tasks for reflections
"""

from keryxflow.agent.cognitive import (
    AgentDecision,
    AgentStats,
    CognitiveAgent,
    CycleResult,
    CycleStatus,
    DecisionType,
    get_cognitive_agent,
)
from keryxflow.agent.executor import ToolExecutor, get_tool_executor
from keryxflow.agent.reflection import (
    DailyReflectionResult,
    PostMortemResult,
    ReflectionEngine,
    ReflectionType,
    WeeklyReflectionResult,
    get_reflection_engine,
)
from keryxflow.agent.scheduler import (
    ScheduledTask,
    TaskFrequency,
    TaskResult,
    TaskScheduler,
    TaskStatus,
    get_task_scheduler,
    setup_default_tasks,
)
from keryxflow.agent.session import (
    SessionState,
    SessionStats,
    TradingSession,
    get_trading_session,
)
from keryxflow.agent.strategy import (
    MarketRegime,
    StrategyConfig,
    StrategyManager,
    StrategySelection,
    StrategyType,
    get_strategy_manager,
)
from keryxflow.agent.tools import (
    BaseTool,
    ToolCategory,
    ToolParameter,
    ToolResult,
    TradingToolkit,
    create_tool,
    get_trading_toolkit,
    register_all_tools,
)

__all__ = [
    # Base classes
    "BaseTool",
    "ToolCategory",
    "ToolParameter",
    "ToolResult",
    # Toolkit
    "TradingToolkit",
    "get_trading_toolkit",
    "register_all_tools",
    # Executor
    "ToolExecutor",
    "get_tool_executor",
    # Decorator
    "create_tool",
    # Cognitive Agent
    "CognitiveAgent",
    "get_cognitive_agent",
    "CycleResult",
    "CycleStatus",
    "AgentDecision",
    "DecisionType",
    "AgentStats",
    # Reflection
    "ReflectionEngine",
    "get_reflection_engine",
    "ReflectionType",
    "PostMortemResult",
    "DailyReflectionResult",
    "WeeklyReflectionResult",
    # Strategy
    "StrategyManager",
    "get_strategy_manager",
    "StrategyConfig",
    "StrategySelection",
    "StrategyType",
    "MarketRegime",
    # Scheduler
    "TaskScheduler",
    "get_task_scheduler",
    "setup_default_tasks",
    "ScheduledTask",
    "TaskResult",
    "TaskFrequency",
    "TaskStatus",
    # Session
    "TradingSession",
    "get_trading_session",
    "SessionState",
    "SessionStats",
]
