"""
AADAP — Orchestrator Executor
================================
Compiles and executes the LangGraph with real agent-invoking nodes.

Architecture layer: L5 (Orchestration).
Source of truth: ARCHITECTURE.md, PHASE_2_CONTRACTS.md.

This module provides the glue that connects:
- LangGraph StateGraph (state machine orchestration)
- TaskRouter (routing decisions)
- AgentPoolManager (agent lifecycle)
- ExecutionService (actual work)

Usage:
    executor = OrchestratorExecutor.create()
    result = await executor.run_workflow(task_id)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from aadap.agents.base import AgentContext, AgentResult, BaseAgent
from aadap.agents.pool_manager import AgentPoolManager
from aadap.core.logging import get_logger
from aadap.integrations.llm_client import BaseLLMClient
from aadap.orchestrator.dispatcher import AgentDispatcher
from aadap.orchestrator.events import EventStore
from aadap.orchestrator.routing import RoutingDecision, TaskRouter
from aadap.orchestrator.state_machine import (
    TERMINAL_STATES,
    VALID_TRANSITIONS,
    TaskState,
    TaskStateMachine,
)
from aadap.db.session import get_db_session

logger = get_logger(__name__)


class OrchestratorState(TypedDict, total=False):
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


from typing import TypedDict


@dataclass
class WorkflowResult:
    """Result of a workflow execution."""

    task_id: uuid.UUID
    final_state: TaskState
    success: bool
    agent_result: AgentResult | None = None
    routing_decision: RoutingDecision | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class OrchestratorExecutor:
    """
    Compiles and executes the LangGraph with real agent-invoking nodes.

    This is the authoritative orchestrator that:
    1. Compiles the LangGraph StateGraph
    2. Routes tasks to appropriate agents via TaskRouter
    3. Executes agents via AgentDispatcher
    4. Manages state transitions through the graph
    """

    def __init__(
        self,
        llm_client: BaseLLMClient,
        agent_pool: AgentPoolManager | None = None,
        dispatcher: AgentDispatcher | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._agent_pool = agent_pool or AgentPoolManager()
        self._dispatcher = dispatcher or AgentDispatcher(
            llm_client=llm_client,
            agent_pool=self._agent_pool,
        )
        self._router = TaskRouter(llm_client=llm_client, use_llm_fallback=True)
        self._event_store = EventStore(get_db_session)
        self._compiled_graph = self._build_and_compile_graph()

    @classmethod
    def create(cls) -> "OrchestratorExecutor":
        """Factory: build from application settings."""
        from aadap.integrations.llm_client import AzureOpenAIClient
        from aadap.core.config import get_settings

        settings = get_settings()
        if not settings.azure_openai_api_key:
            raise RuntimeError("OrchestratorExecutor requires LLM configuration.")

        llm = AzureOpenAIClient.from_settings()
        return cls(llm_client=llm)

    def _build_and_compile_graph(self) -> CompiledGraph:
        """Build and compile the LangGraph StateGraph."""
        graph = StateGraph(OrchestratorState)

        for task_state in TaskState:
            node_fn = self._create_node(task_state)
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
            router_fn = self._create_router(task_state, targets)

            graph.add_conditional_edges(
                task_state.value,
                router_fn,
                targets | {END: END},
            )

        checkpointer = MemorySaver()
        return graph.compile(checkpointer=checkpointer)

    def _create_node(self, state: TaskState) -> Callable:
        """Create a node function that executes the appropriate action for the state."""

        async def node_fn(graph_state: OrchestratorState) -> OrchestratorState:
            task_id_str = graph_state.get("task_id", "")
            task_id = uuid.UUID(task_id_str) if task_id_str else None

            logger.info(
                "orchestrator.node_enter",
                node=state.value,
                task_id=task_id_str,
            )

            new_state = {
                **graph_state,
                "previous_state": graph_state.get("current_state"),
                "current_state": state.value,
            }

            if state == TaskState.AGENT_ASSIGNMENT and task_id:
                routing = await self._execute_routing(task_id, graph_state)
                if routing:
                    new_state["routing_decision"] = {
                        "agent_type": routing.agent_type,
                        "confidence": routing.confidence,
                        "routing_method": routing.routing_method,
                        "reasoning": routing.reasoning,
                    }

            elif state == TaskState.IN_DEVELOPMENT and task_id:
                result = await self._execute_development(task_id, graph_state)
                if result:
                    new_state["agent_result"] = {
                        "success": result.success,
                        "output": result.output,
                        "error": result.error,
                        "tokens_used": result.tokens_used,
                    }
                    if not result.success:
                        new_state["error"] = result.error

            elif state == TaskState.IN_VALIDATION and task_id:
                result = await self._execute_validation(task_id, graph_state)
                if result:
                    new_state["agent_result"] = {
                        "success": result.success,
                        "output": result.output,
                        "error": result.error,
                    }

            elif state == TaskState.IN_OPTIMIZATION and task_id:
                result = await self._execute_optimization(task_id, graph_state)
                if result:
                    new_state["agent_result"] = {
                        "success": result.success,
                        "output": result.output,
                    }

            await self._persist_transition(
                task_id=task_id,
                from_state=TaskState(graph_state.get("previous_state", "SUBMITTED")),
                to_state=state,
                metadata=new_state,
            )

            return new_state

        node_fn.__name__ = f"node_{state.lower()}"
        node_fn.__doc__ = f"Execute {state.value} state logic."
        return node_fn

    def _create_router(
        self,
        from_state: TaskState,
        targets: dict[str, str],
    ) -> Callable:
        """Create a router function for conditional edges."""

        def router_fn(graph_state: OrchestratorState) -> str:
            current = graph_state.get("current_state", "")
            error = graph_state.get("error")

            if from_state in TERMINAL_STATES:
                return END

            if error and from_state == TaskState.IN_DEVELOPMENT:
                return TaskState.DEV_FAILED.value

            if error and from_state == TaskState.IN_VALIDATION:
                return TaskState.VALIDATION_FAILED.value

            if current in targets:
                return current

            if targets:
                return list(targets.keys())[0]

            return END

        router_fn.__name__ = f"route_{from_state.lower()}"
        return router_fn

    async def _execute_routing(
        self,
        task_id: uuid.UUID,
        graph_state: OrchestratorState,
    ) -> RoutingDecision | None:
        """Execute routing decision for task."""
        try:
            metadata = graph_state.get("metadata", {})
            decision = self._router.route(
                task_id=task_id,
                title=metadata.get("title", ""),
                description=metadata.get("description", ""),
                metadata=metadata,
                environment=metadata.get("environment", "SANDBOX"),
            )
            logger.info(
                "orchestrator.routing_complete",
                task_id=str(task_id),
                agent_type=decision.agent_type,
                confidence=decision.confidence,
            )
            return decision
        except Exception as exc:
            logger.error(
                "orchestrator.routing_failed",
                task_id=str(task_id),
                error=str(exc),
            )
            return None

    async def _execute_development(
        self,
        task_id: uuid.UUID,
        graph_state: OrchestratorState,
    ) -> AgentResult | None:
        """Execute development agent for code generation."""
        routing_dict = graph_state.get("routing_decision", {})
        agent_type = routing_dict.get("agent_type", "developer")
        metadata = graph_state.get("metadata", {})

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

        return await self._dispatcher.dispatch_and_execute(
            agent_type=agent_type,
            context=context,
        )

    async def _execute_validation(
        self,
        task_id: uuid.UUID,
        graph_state: OrchestratorState,
    ) -> AgentResult | None:
        """Execute validation agent."""
        metadata = graph_state.get("metadata", {})
        dev_result = graph_state.get("agent_result", {})
        code = dev_result.get("output", {}).get("code", "")

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

        return await self._dispatcher.dispatch_and_execute(
            agent_type="validation",
            context=context,
        )

    async def _execute_optimization(
        self,
        task_id: uuid.UUID,
        graph_state: OrchestratorState,
    ) -> AgentResult | None:
        """Execute optimization agent."""
        metadata = graph_state.get("metadata", {})
        dev_result = graph_state.get("agent_result", {})
        code = dev_result.get("output", {}).get("code", "")

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

        return await self._dispatcher.dispatch_and_execute(
            agent_type="optimization",
            context=context,
        )

    async def _persist_transition(
        self,
        task_id: uuid.UUID | None,
        from_state: TaskState,
        to_state: TaskState,
        metadata: dict[str, Any],
    ) -> None:
        """Persist state transition to event store."""
        if not task_id:
            return

        try:
            await self._event_store.record_transition(
                task_id=task_id,
                from_state=from_state,
                to_state=to_state,
                triggered_by="orchestrator_executor",
                reason=f"Graph transition: {from_state.value} → {to_state.value}",
            )
        except Exception as exc:
            logger.error(
                "orchestrator.persist_failed",
                task_id=str(task_id),
                error=str(exc),
            )

    async def run_workflow(
        self,
        task_id: uuid.UUID,
        initial_metadata: dict[str, Any] | None = None,
    ) -> WorkflowResult:
        """
        Execute a complete workflow from current state to terminal state.

        This is the main entry point for orchestrated task execution.
        """
        logger.info("orchestrator.workflow_start", task_id=str(task_id))

        try:
            current_state = await self._event_store.replay(task_id)

            initial_state: OrchestratorState = {
                "task_id": str(task_id),
                "current_state": current_state.value,
                "previous_state": None,
                "triggered_by": "run_workflow",
                "reason": "Initiating workflow execution",
                "metadata": initial_metadata or {},
                "routing_decision": None,
                "agent_result": None,
                "error": None,
            }

            config = {
                "configurable": {
                    "thread_id": str(task_id),
                }
            }

            final_state = await self._compiled_graph.ainvoke(initial_state, config)

            final_task_state = TaskState(final_state.get("current_state", "COMPLETED"))
            agent_result_dict = final_state.get("agent_result")
            routing_dict = final_state.get("routing_decision")

            result = WorkflowResult(
                task_id=task_id,
                final_state=final_task_state,
                success=final_task_state in {TaskState.COMPLETED},
                metadata=final_state.get("metadata", {}),
            )

            if agent_result_dict:
                result.agent_result = AgentResult(
                    success=agent_result_dict.get("success", False),
                    output=agent_result_dict.get("output"),
                    error=agent_result_dict.get("error"),
                    tokens_used=agent_result_dict.get("tokens_used", 0),
                )

            if routing_dict:
                result.routing_decision = RoutingDecision(
                    agent_type=routing_dict.get("agent_type", "developer"),
                    confidence=routing_dict.get("confidence", 0.0),
                    routing_method=routing_dict.get("routing_method", "fallback"),
                    reasoning=routing_dict.get("reasoning"),
                )

            logger.info(
                "orchestrator.workflow_complete",
                task_id=str(task_id),
                final_state=final_task_state.value,
                success=result.success,
            )

            return result

        except Exception as exc:
            logger.error(
                "orchestrator.workflow_failed",
                task_id=str(task_id),
                error=str(exc),
            )
            return WorkflowResult(
                task_id=task_id,
                final_state=TaskState.CANCELLED,
                success=False,
                error=str(exc),
            )

    async def run_to_state(
        self,
        task_id: uuid.UUID,
        target_state: TaskState,
        initial_metadata: dict[str, Any] | None = None,
    ) -> WorkflowResult:
        """
        Execute workflow until reaching a specific target state.

        Useful for partial execution (e.g., just code generation).
        """
        logger.info(
            "orchestrator.run_to_state_start",
            task_id=str(task_id),
            target=target_state.value,
        )

        try:
            current_state = await self._event_store.replay(task_id)

            if current_state == target_state:
                return WorkflowResult(
                    task_id=task_id,
                    final_state=current_state,
                    success=True,
                )

            initial_state: OrchestratorState = {
                "task_id": str(task_id),
                "current_state": current_state.value,
                "previous_state": None,
                "metadata": initial_metadata or {},
                "routing_decision": None,
                "agent_result": None,
                "error": None,
            }

            config = {
                "configurable": {
                    "thread_id": str(task_id),
                }
            }

            for event in self._compiled_graph.astream(initial_state, config):
                for node_name, node_state in event.items():
                    current = TaskState(node_state.get("current_state", ""))
                    if current == target_state:
                        return WorkflowResult(
                            task_id=task_id,
                            final_state=current,
                            success=True,
                            metadata=node_state.get("metadata", {}),
                        )

            final_state = await self._event_store.replay(task_id)
            return WorkflowResult(
                task_id=task_id,
                final_state=final_state,
                success=final_state == target_state,
            )

        except Exception as exc:
            logger.error(
                "orchestrator.run_to_state_failed",
                task_id=str(task_id),
                error=str(exc),
            )
            return WorkflowResult(
                task_id=task_id,
                final_state=TaskState.CANCELLED,
                success=False,
                error=str(exc),
            )

    @property
    def compiled_graph(self):
        """Return the compiled LangGraph for inspection."""
        return self._compiled_graph

    @property
    def router(self) -> TaskRouter:
        """Return the task router."""
        return self._router

    @property
    def dispatcher(self) -> AgentDispatcher:
        """Return the agent dispatcher."""
        return self._dispatcher


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langgraph.pregel import Pregel as CompiledGraph
else:
    CompiledGraph = Any
