"""
AADAP — Orchestration Engine (Phase 2)
========================================
Deterministic task lifecycle and orchestration backbone.

Public API:
    create_task, transition, replay, schedule
    run_task_graph - Execute task through LangGraph
    get_compiled_graph - Get compiled LangGraph
    OrchestratorExecutor - Full workflow executor
    AgentDispatcher - Agent dispatch and execution
"""

from aadap.orchestrator.state_machine import (
    InvalidTransitionError,
    TaskState,
    TaskStateMachine,
)
from aadap.orchestrator.events import EventStore
from aadap.orchestrator.checkpoints import CheckpointManager
from aadap.orchestrator.scheduler import TaskScheduler
from aadap.orchestrator.guards import Guards, LoopDetectedError
from aadap.orchestrator.dispatcher import AgentDispatcher
from aadap.orchestrator.executor import OrchestratorExecutor, WorkflowResult
from aadap.orchestrator.graph import (
    build_graph,
    get_compiled_graph,
    run_task_graph,
    create_task,
    transition,
    replay,
    schedule,
)

__all__ = [
    "TaskState",
    "TaskStateMachine",
    "InvalidTransitionError",
    "EventStore",
    "CheckpointManager",
    "TaskScheduler",
    "Guards",
    "LoopDetectedError",
    "AgentDispatcher",
    "OrchestratorExecutor",
    "WorkflowResult",
    "build_graph",
    "get_compiled_graph",
    "run_task_graph",
    "create_task",
    "transition",
    "replay",
    "schedule",
]
