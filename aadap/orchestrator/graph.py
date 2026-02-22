"""
AADAP — LangGraph StateGraph Definition
==========================================
Orchestration backbone graph using LangGraph with real agent-invoking nodes.

Architecture layer: L5 (Orchestration).
Source of truth: ARCHITECTURE.md, PHASE_2_CONTRACTS.md.

This module provides:
- Compiled LangGraph StateGraph with agent execution
- Top-level API for task creation and state transitions
- run_task_graph() for full graph-based orchestration

Usage:
    task_id = await create_task("My task")
    result = await run_task_graph(task_id)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from aadap.agents.base import AgentContext, AgentResult
from aadap.core.exceptions import (
    AADAPError,
    AgentLifecycleError,
    ConfigurationError,
    ExecutionError,
    IntegrationError,
    OrchestratorError,
)
from aadap.core.logging import get_logger
from aadap.db.models import Task
from aadap.db.session import get_db_session
from aadap.orchestrator.checkpoints import CheckpointManager
from aadap.orchestrator.dispatcher import AgentDispatcher
from aadap.orchestrator.events import EventStore
from aadap.orchestrator.graph_executor import GraphExecutor
from aadap.orchestrator.guards import Guards
from aadap.orchestrator.routing import TaskRouter, RoutingDecision
from aadap.orchestrator.scheduler import TaskScheduler
from aadap.orchestrator.state_machine import (
    TERMINAL_STATES,
    VALID_TRANSITIONS,
    TaskState,
    TaskStateMachine,
)

logger = get_logger("aadap.orchestrator.graph")


class GraphState(TypedDict, total=False):
    """State carried through the LangGraph execution."""

    task_id: str
    current_state: str
    previous_state: str | None
    triggered_by: str | None
    reason: str | None
    metadata: dict[str, Any]
    routing_decision: dict[str, Any] | None
    agent_result: dict[str, Any] | None
    error: str | None
    code: str | None


class CompiledGraphHolder:
    """Holder for the compiled graph and its dependencies."""

    _instance: "CompiledGraphHolder | None" = None

    def __init__(self) -> None:
        self._compiled_graph: Any = None
        self._dispatcher: AgentDispatcher | None = None
        self._router: TaskRouter | None = None
        self._executor: GraphExecutor | None = None
        self._event_store = EventStore(get_db_session)

    @classmethod
    def get_instance(cls) -> "CompiledGraphHolder":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_dispatcher(self) -> AgentDispatcher:
        if self._dispatcher is None:
            from aadap.integrations.llm_client import AzureOpenAIClient
            try:
                llm = AzureOpenAIClient.from_settings()
                self._dispatcher = AgentDispatcher(llm_client=llm)
            except (ConfigurationError, IntegrationError):
                from aadap.integrations.llm_client import MockLLMClient
                self._dispatcher = AgentDispatcher(llm_client=MockLLMClient())
        return self._dispatcher

    def _get_router(self) -> TaskRouter:
        if self._router is None:
            from aadap.integrations.llm_client import AzureOpenAIClient
            try:
                llm = AzureOpenAIClient.from_settings()
                self._router = TaskRouter(llm_client=llm, use_llm_fallback=True)
            except (ConfigurationError, IntegrationError):
                self._router = TaskRouter(llm_client=None, use_llm_fallback=False)
        return self._router

    def _get_executor(self) -> GraphExecutor:
        if self._executor is None:
            self._executor = GraphExecutor(
                dispatcher=self._get_dispatcher(),
                router=self._get_router(),
            )
        return self._executor


_holder = CompiledGraphHolder.get_instance()


def _create_node(state: TaskState) -> Callable:
    """Create a node function that executes state-specific logic."""

    async def node_fn(graph_state: GraphState) -> GraphState:
        task_id_str = graph_state.get("task_id", "")
        task_id = uuid.UUID(task_id_str) if task_id_str else None
        metadata = graph_state.get("metadata") or {}

        logger.info(
            "graph.node_enter",
            node=state.value,
            task_id=task_id_str,
        )

        new_state: GraphState = {
            **graph_state,
            "previous_state": graph_state.get("current_state"),
            "current_state": state.value,
        }

        executor = _holder._get_executor()

        if state == TaskState.AGENT_ASSIGNMENT and task_id:
            routing = await executor.execute_routing(task_id, metadata)
            if routing:
                new_state["routing_decision"] = {
                    "agent_type": routing.agent_type,
                    "confidence": routing.confidence,
                    "routing_method": routing.routing_method,
                    "reasoning": routing.reasoning,
                }

        elif state == TaskState.IN_DEVELOPMENT and task_id:
            if executor.is_direct_execution(metadata):
                result = await executor.execute_direct_operation(task_id, metadata)
            else:
                routing = graph_state.get("routing_decision")
                result = await executor.execute_development(task_id, metadata, routing)
            
            if result:
                new_state["agent_result"] = {
                    "success": result.success,
                    "output": result.output,
                    "error": result.error,
                    "tokens_used": result.tokens_used,
                }
                if result.success and result.output:
                    code = result.output.get("code") if isinstance(result.output, dict) else None
                    if code:
                        new_state["code"] = code
                if not result.success:
                    new_state["error"] = result.error

        elif state == TaskState.IN_VALIDATION and task_id:
            code = graph_state.get("code") or ""
            if not code:
                dev_result = graph_state.get("agent_result") or {}
                output = dev_result.get("output") or {}
                code = output.get("code") or ""
            
            result = await executor.execute_validation(task_id, code, metadata)
            if result:
                new_state["agent_result"] = {
                    "success": result.success,
                    "output": result.output,
                    "error": result.error,
                }
                if not result.success:
                    new_state["error"] = result.error

        elif state == TaskState.IN_OPTIMIZATION and task_id:
            code = graph_state.get("code") or ""
            result = await executor.execute_optimization(task_id, code, metadata)
            if result:
                new_state["agent_result"] = {
                    "success": result.success,
                    "output": result.output,
                }
                if result.success and result.output:
                    optimized = result.output.get("optimized_code") if isinstance(result.output, dict) else None
                    if optimized:
                        new_state["code"] = optimized

        elif state == TaskState.DEPLOYING and task_id:
            code = graph_state.get("code") or ""
            if code:
                result = await executor.execute_on_platform(task_id, code, metadata)
                if result:
                    new_state["agent_result"] = {
                        "success": result.success,
                        "output": result.output,
                        "error": result.error,
                    }
                    if not result.success:
                        new_state["error"] = result.error

        elif state == TaskState.APPROVAL_PENDING and task_id:
            code = graph_state.get("code") or ""
            if code:
                approval = await executor.request_approval(task_id, code, metadata)
                new_state["metadata"] = {
                    **metadata,
                    "approval_id": approval.get("approval_id"),
                    "requires_approval": approval.get("requires_approval"),
                }
                if not approval.get("requires_approval"):
                    new_state["reason"] = "Auto-approved for sandbox environment"

        if task_id:
            prev = graph_state.get("previous_state")
            if prev:
                await _persist_transition(
                    task_id=task_id,
                    from_state=TaskState(prev),
                    to_state=state,
                    metadata=dict(new_state),
                )

        return new_state

    node_fn.__name__ = f"node_{state.lower()}"
    node_fn.__doc__ = f"Execute {state.value} state logic."
    return node_fn


def _create_router(from_state: TaskState, targets: dict[str, str]) -> Callable:
    """Create a router function for conditional edges."""

    def router_fn(graph_state: GraphState) -> str:
        current = graph_state.get("current_state", "")
        error = graph_state.get("error")
        metadata = graph_state.get("metadata") or {}

        if from_state in TERMINAL_STATES:
            return END

        if error:
            if from_state == TaskState.IN_DEVELOPMENT:
                if TaskState.DEV_FAILED.value in targets:
                    return TaskState.DEV_FAILED.value
            elif from_state == TaskState.IN_VALIDATION:
                if TaskState.VALIDATION_FAILED.value in targets:
                    return TaskState.VALIDATION_FAILED.value
            elif from_state == TaskState.DEPLOYING:
                if TaskState.DEV_FAILED.value in targets:
                    return TaskState.DEV_FAILED.value

        if from_state == TaskState.APPROVAL_PENDING:
            requires_approval = metadata.get("requires_approval", True)
            if not requires_approval:
                if TaskState.IN_REVIEW.value in targets:
                    return TaskState.IN_REVIEW.value

        if from_state == TaskState.IN_REVIEW:
            if TaskState.APPROVED.value in targets:
                return TaskState.APPROVED.value

        if current in targets:
            return current

        if targets:
            first_target = next(iter(targets.keys()))
            if first_target:
                return first_target

        return END

    router_fn.__name__ = f"route_{from_state.lower()}"
    return router_fn


async def _execute_routing(
    task_id: uuid.UUID,
    graph_state: GraphState,
) -> RoutingDecision | None:
    """Execute routing decision for task."""
    try:
        metadata = graph_state.get("metadata", {})
        router = _holder._get_router()
        decision = router.route(
            task_id=task_id,
            title=metadata.get("title", ""),
            description=metadata.get("description", ""),
            metadata=metadata,
            environment=metadata.get("environment", "SANDBOX"),
        )
        logger.info(
            "graph.routing_complete",
            task_id=str(task_id),
            agent_type=decision.agent_type,
            confidence=decision.confidence,
        )
        return decision
    except OrchestratorError as exc:
        logger.error(
            "graph.routing_failed",
            task_id=str(task_id),
            error_code=exc.error_code,
            severity=exc.severity.value,
            error=str(exc),
        )
        return None


async def _execute_development(
    task_id: uuid.UUID,
    graph_state: GraphState,
) -> AgentResult | None:
    """Execute development agent for code generation."""
    try:
        routing_dict = graph_state.get("routing_decision") or {}
        agent_type = routing_dict.get("agent_type", "developer")
        metadata = graph_state.get("metadata") or {}

        context = AgentContext(
            task_id=task_id,
            task_data={
                "title": metadata.get("title", ""),
                "description": metadata.get("description", ""),
                "environment": metadata.get("environment", "SANDBOX"),
                "platform": metadata.get("platform", "databricks"),
            },
            token_budget=metadata.get("token_budget", 50_000),
            allowed_tools=set(),
            metadata=metadata,
        )

        dispatcher = _holder._get_dispatcher()
        return await dispatcher.dispatch_and_execute(
            agent_type=agent_type,
            context=context,
        )
    except (AgentLifecycleError, OrchestratorError) as exc:
        logger.error(
            "graph.development_failed",
            task_id=str(task_id),
            error_code=exc.error_code,
            severity=exc.severity.value,
            error=str(exc),
        )
        return AgentResult(success=False, error=str(exc))


async def _execute_validation(
    task_id: uuid.UUID,
    graph_state: GraphState,
) -> AgentResult | None:
    """Execute validation agent."""
    try:
        metadata = graph_state.get("metadata") or {}
        code = graph_state.get("code") or ""

        if not code:
            dev_result = graph_state.get("agent_result") or {}
            output = dev_result.get("output") or {}
            code = output.get("code") or ""

        context = AgentContext(
            task_id=task_id,
            task_data={
                "code": code,
                "language": metadata.get("language", "python"),
                "description": metadata.get("description", ""),
                "environment": metadata.get("environment", "SANDBOX"),
            },
            token_budget=metadata.get("token_budget", 50_000),
            allowed_tools=set(),
        )

        dispatcher = _holder._get_dispatcher()
        return await dispatcher.dispatch_and_execute(
            agent_type="validation",
            context=context,
        )
    except ExecutionError as exc:
        logger.error(
            "graph.validation_failed",
            task_id=str(task_id),
            error_code=exc.error_code,
            severity=exc.severity.value,
            error=str(exc),
        )
        return AgentResult(success=False, error=str(exc))


async def _execute_optimization(
    task_id: uuid.UUID,
    graph_state: GraphState,
) -> AgentResult | None:
    """Execute optimization agent."""
    try:
        metadata = graph_state.get("metadata", {})
        code = graph_state.get("code", "")

        context = AgentContext(
            task_id=task_id,
            task_data={
                "code": code,
                "platform": metadata.get("platform", "databricks"),
                "environment": metadata.get("environment", "SANDBOX"),
            },
            token_budget=metadata.get("token_budget", 50_000),
            allowed_tools=set(),
        )

        dispatcher = _holder._get_dispatcher()
        return await dispatcher.dispatch_and_execute(
            agent_type="optimization",
            context=context,
        )
    except ExecutionError as exc:
        logger.error(
            "graph.optimization_failed",
            task_id=str(task_id),
            error_code=exc.error_code,
            severity=exc.severity.value,
            error=str(exc),
        )
        return AgentResult(success=False, error=str(exc))


async def _persist_transition(
    task_id: uuid.UUID,
    from_state: TaskState,
    to_state: TaskState,
    metadata: dict[str, Any],
) -> None:
    """Persist state transition to event store."""
    try:
        await _holder._event_store.record_transition(
            task_id=task_id,
            from_state=from_state,
            to_state=to_state,
            triggered_by="langgraph",
            reason=f"Graph transition: {from_state.value} → {to_state.value}",
        )
    except AADAPError as exc:
        logger.error(
            "graph.persist_failed",
            task_id=str(task_id),
            error_code=exc.error_code,
            severity=exc.severity.value,
            error=str(exc),
        )


def build_graph() -> StateGraph:
    """
    Construct the LangGraph StateGraph for the 25-state machine.

    Nodes: one per authoritative state with execution logic.
    Edges: conditional, matching ``VALID_TRANSITIONS``.
    Entry: START → SUBMITTED.
    Exit: COMPLETED / CANCELLED → END.
    """
    graph = StateGraph(GraphState)

    for task_state in TaskState:
        node_fn = _create_node(task_state)
        graph.add_node(task_state.value, node_fn)

    graph.add_edge(START, TaskState.SUBMITTED.value)

    for task_state in TaskState:
        if task_state in TERMINAL_STATES:
            graph.add_edge(task_state.value, END)
            continue

        allowed = VALID_TRANSITIONS[task_state]
        if not allowed:
            continue

        targets = {s.value: s.value for s in allowed}
        router_fn = _create_router(task_state, targets)

        graph.add_conditional_edges(
            task_state.value,
            router_fn,
            targets | {END: END},  # type: ignore[arg-type]
        )

    return graph


def get_compiled_graph():
    """
    Get or create the compiled LangGraph.

    The graph is compiled once and cached for reuse.
    """
    if _holder._compiled_graph is None:
        graph = build_graph()
        checkpointer = MemorySaver()
        _holder._compiled_graph = graph.compile(checkpointer=checkpointer)
        logger.info("graph.compiled")
    return _holder._compiled_graph


async def run_task_graph(
    task_id: uuid.UUID,
    initial_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Execute a task through the LangGraph from current state.

    This is the main entry point for graph-based orchestration.

    Parameters
    ----------
    task_id
        The task to execute
    initial_metadata
        Initial metadata to pass to the graph

    Returns
    -------
    dict
        Final state with results
    """
    logger.info("graph.run_start", task_id=str(task_id))

    try:
        current_state = await _holder._event_store.replay(task_id)

        initial_state: GraphState = {
            "task_id": str(task_id),
            "current_state": current_state.value,
            "previous_state": None,
            "triggered_by": "run_task_graph",
            "reason": "Initiating graph execution",
            "metadata": initial_metadata or {},
            "routing_decision": None,
            "agent_result": None,
            "error": None,
            "code": None,
        }

        compiled = get_compiled_graph()

        config = {
            "configurable": {
                "thread_id": str(task_id),
            }
        }

        final_state = await compiled.ainvoke(initial_state, config)

        result = {
            "task_id": str(task_id),
            "final_state": final_state.get("current_state", "UNKNOWN"),
            "success": final_state.get("current_state") == TaskState.COMPLETED.value,
            "agent_result": final_state.get("agent_result"),
            "routing_decision": final_state.get("routing_decision"),
            "error": final_state.get("error"),
            "code": final_state.get("code"),
        }

        logger.info(
            "graph.run_complete",
            task_id=str(task_id),
            final_state=result["final_state"],
            success=result["success"],
        )

        return result

    except (OrchestratorError, AgentLifecycleError) as exc:
        logger.error(
            "graph.run_failed",
            task_id=str(task_id),
            error_code=exc.error_code,
            severity=exc.severity.value,
            error=str(exc),
        )
        return {
            "task_id": str(task_id),
            "final_state": "CANCELLED",
            "success": False,
            "error_code": exc.error_code,
            "error": str(exc),
        }
    except Exception as exc:
        logger.exception(
            "graph.run_unexpected_error",
            task_id=str(task_id),
            error=str(exc),
        )
        raise


async def create_task(
    title: str,
    description: str | None = None,
    priority: int = 0,
    environment: str = "SANDBOX",
    created_by: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> uuid.UUID:
    """
    Create a new task in SUBMITTED state.

    Interface: ``create_task(input) -> task_id`` (PHASE_2_CONTRACTS.md).
    """
    task_id = uuid.uuid4()

    async with get_db_session() as session:
        task = Task(
            id=task_id,
            title=title,
            description=description,
            current_state=TaskState.SUBMITTED.value,
            priority=priority,
            environment=environment,
            created_by=created_by,
            metadata_=metadata or {},
        )
        session.add(task)

    logger.info(
        "task.created",
        task_id=str(task_id),
        title=title,
        priority=priority,
        environment=environment,
    )
    return task_id


async def transition(
    task_id: uuid.UUID,
    next_state: str,
    triggered_by: str | None = None,
    reason: str | None = None,
) -> TaskState:
    """
    Transition a task to the next state.

    Interface: ``transition(task_id, next_state)`` (PHASE_2_CONTRACTS.md).

    Runs all guards, records the transition event, and updates the
    checkpoint.
    """
    event_store = EventStore(get_db_session)

    current_state = await event_store.replay(task_id)

    target = TaskStateMachine.parse_state(next_state)

    history = await event_store.get_history(task_id)

    Guards.check_transition_valid(current_state, target)
    Guards.check_loop(target, history)

    await event_store.record_transition(
        task_id=task_id,
        from_state=current_state,
        to_state=target,
        triggered_by=triggered_by,
        reason=reason,
    )

    logger.info(
        "task.transitioned",
        task_id=str(task_id),
        from_state=current_state.value,
        to_state=target.value,
        triggered_by=triggered_by,
    )
    return target


async def replay(task_id: uuid.UUID) -> TaskState:
    """
    Replay a task's event history to derive the current state.

    Interface: ``replay(task_id) -> state`` (PHASE_2_CONTRACTS.md).
    """
    event_store = EventStore(get_db_session)
    state = await event_store.replay(task_id)
    logger.info("task.replayed", task_id=str(task_id), state=state.value)
    return state


async def schedule(task_id: uuid.UUID, priority: int = 0) -> None:
    """
    Schedule a task for execution.

    Interface: ``schedule(task_id, priority)`` (PHASE_2_CONTRACTS.md).
    """
    _scheduler.schedule(task_id, priority)
    logger.info(
        "task.scheduled",
        task_id=str(task_id),
        priority=priority,
        pending=_scheduler.pending_count(),
    )


_scheduler = TaskScheduler()


def get_scheduler() -> TaskScheduler:
    """Return the module-level scheduler. Useful for tests and inspection."""
    return _scheduler
