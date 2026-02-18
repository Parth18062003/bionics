"""
AADAP — Agent Framework (Phase 3)
====================================
Reusable, governed agent execution framework.

Public API:
    BaseAgent, AgentState, AgentContext, AgentResult,
    AgentPoolManager, AgentHealthChecker, HealthStatus,
    TokenTracker, ToolRegistry, ToolDefinition,
    DeveloperAgent, FabricAgent
"""

from aadap.agents.base import (
    AgentContext,
    AgentLifecycleError,
    AgentResult,
    AgentState,
    BaseAgent,
)
from aadap.agents.adapters import (
    DatabricksAdapter,
    FabricAdapter,
    PlatformAdapter,
    PlatformAdapterError,
    PlatformCapabilityError,
    PlatformExecutionError,
)
from aadap.agents.catalog_agent import CatalogAgent
from aadap.agents.developer_agent import DeveloperAgent
from aadap.agents.etl_pipeline_agent import ETLPipelineAgent
from aadap.agents.fabric_agent import FabricAgent
from aadap.agents.ingestion_agent import IngestionAgent
from aadap.agents.job_scheduler_agent import JobSchedulerAgent
from aadap.agents.factory import (
    create_developer_agent,
    create_fabric_agent,
    wire_pool,
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
    "CatalogAgent",
    "DatabricksAdapter",
    "DEFAULT_TOKEN_BUDGET",
    "DeveloperAgent",
    "ETLPipelineAgent",
    "FabricAgent",
    "FabricAdapter",
    "IngestionAgent",
    "JobSchedulerAgent",
    "HealthStatus",
    "NoAvailableAgentError",
    "PlatformAdapter",
    "PlatformAdapterError",
    "PlatformCapabilityError",
    "PlatformExecutionError",
    "PoolCapacityError",
    "TokenBudgetExhaustedError",
    "TokenTracker",
    "ToolDefinition",
    "ToolNotFoundError",
    "ToolPermissionDeniedError",
    "ToolRegistry",
    "create_developer_agent",
    "create_fabric_agent",
    "wire_pool",
]
