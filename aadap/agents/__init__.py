"""
AADAP — Agent Framework (Phase 3)
====================================
Reusable, governed agent execution framework.

Public API:
    BaseAgent, AgentState, AgentContext, AgentResult,
    AgentPoolManager, AgentHealthChecker, HealthStatus,
    TokenTracker, ToolRegistry, ToolDefinition
"""

from aadap.agents.base import (
    AgentContext,
    AgentLifecycleError,
    AgentResult,
    AgentState,
    BaseAgent,
)
from aadap.agents.health import AgentHealthChecker, HealthStatus
from aadap.agents.pool_manager import (
    AgentNotFoundError,
    AgentPoolManager,
    NoAvailableAgentError,
    PoolCapacityError,
)
from aadap.agents.token_tracker import (
    DEFAULT_TOKEN_BUDGET,
    TokenBudgetExhaustedError,
    TokenTracker,
)
from aadap.agents.tools.registry import (
    ToolDefinition,
    ToolNotFoundError,
    ToolPermissionDeniedError,
    ToolRegistry,
)

__all__ = [
    "AgentContext",
    "AgentHealthChecker",
    "AgentLifecycleError",
    "AgentNotFoundError",
    "AgentPoolManager",
    "AgentResult",
    "AgentState",
    "BaseAgent",
    "DEFAULT_TOKEN_BUDGET",
    "HealthStatus",
    "NoAvailableAgentError",
    "PoolCapacityError",
    "TokenBudgetExhaustedError",
    "TokenTracker",
    "ToolDefinition",
    "ToolNotFoundError",
    "ToolPermissionDeniedError",
    "ToolRegistry",
]
