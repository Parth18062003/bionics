"""
AADAP — Base Agent Abstraction
=================================
Governed, stateless agent framework with explicit lifecycle management.

Architecture layer: L4 (Agent Layer).
Source of truth: PHASE_3_CONTRACTS.md, ARCHITECTURE.md §Trust Boundaries.

Design decisions:
- Agents are untrusted, stateless workers (ARCHITECTURE.md)
- No agent bypasses the orchestrator (PHASE_3_CONTRACTS §Invariants)
- Tool access must be explicitly granted
- Token budget enforced per task (INV-04)
- Lifecycle transitions are explicit and guarded

Usage:
    class MyAgent(BaseAgent):
        async def _do_execute(self, context):
            return AgentResult(success=True, output="done", tokens_used=42)

    agent = MyAgent(agent_id="dev-1", agent_type="developer",
                    allowed_tools={"read_file", "write_file"})
    if await agent.accept_task(context):
        result = await agent.execute(context)
"""

from __future__ import annotations

import abc
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from aadap.agents.health import HealthStatus
from aadap.agents.token_tracker import TokenTracker
from aadap.agents.tools.registry import ToolRegistry
from aadap.core.logging import get_logger

logger = get_logger(__name__)


# ── Agent Lifecycle States ──────────────────────────────────────────────


class AgentState(StrEnum):
    """Agent lifecycle states."""

    IDLE = "IDLE"
    ACCEPTING = "ACCEPTING"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TERMINATED = "TERMINATED"


# ── Data Objects ────────────────────────────────────────────────────────


@dataclass
class AgentContext:
    """
    Immutable context passed from the orchestrator to an agent.

    The orchestrator is authoritative — agents receive context,
    they do not construct it.
    """

    task_id: uuid.UUID
    task_data: dict[str, Any]
    token_budget: int = 50_000  # INV-04 default
    allowed_tools: set[str] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Result returned by an agent after execution."""

    success: bool
    output: Any = None
    tokens_used: int = 0
    error: str | None = None
    artifacts: list[dict[str, Any]] = field(default_factory=list)


# ── Exceptions ──────────────────────────────────────────────────────────


class AgentLifecycleError(Exception):
    """Raised on invalid agent lifecycle transitions."""

    def __init__(self, agent_id: str, current: AgentState, attempted: str) -> None:
        self.agent_id = agent_id
        self.current_state = current
        self.attempted_action = attempted
        super().__init__(
            f"Agent '{agent_id}' cannot {attempted} in state {current.value}."
        )


# ── Base Agent ──────────────────────────────────────────────────────────


class BaseAgent(abc.ABC):
    """
    Abstract base for all AADAP agents.

    Agents are stateless workers.  They receive a task context from the
    orchestrator, execute, and return a result.  Between tasks, the
    agent resets to ``IDLE``.

    Invariants:
    - No agent bypasses orchestrator
    - Tool access must be explicitly granted
    - Token budget enforced per task (INV-04)
    """

    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        allowed_tools: set[str] | None = None,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        self._agent_id = agent_id
        self._agent_type = agent_type
        self._allowed_tools: set[str] = allowed_tools or set()
        self._tool_registry = tool_registry
        self._state = AgentState.IDLE
        self._current_context: AgentContext | None = None
        self._token_tracker: TokenTracker | None = None

        logger.info(
            "agent.created",
            agent_id=agent_id,
            agent_type=agent_type,
            allowed_tools=sorted(self._allowed_tools),
        )

    # ── Properties ──────────────────────────────────────────────────────

    @property
    def agent_id(self) -> str:
        return self._agent_id

    @property
    def agent_type(self) -> str:
        return self._agent_type

    @property
    def state(self) -> AgentState:
        return self._state

    @property
    def allowed_tools(self) -> frozenset[str]:
        return frozenset(self._allowed_tools)

    # ── Lifecycle: accept_task ──────────────────────────────────────────

    async def accept_task(self, context: AgentContext) -> bool:
        """
        Validate and accept a task from the orchestrator.

        Transitions: IDLE → ACCEPTING.

        Raises ``AgentLifecycleError`` if not in IDLE state.
        Returns ``True`` if the agent accepts the task.
        """
        if self._state != AgentState.IDLE:
            raise AgentLifecycleError(
                self._agent_id, self._state, "accept_task"
            )

        self._state = AgentState.ACCEPTING
        self._current_context = context
        self._token_tracker = TokenTracker(
            task_id=context.task_id,
            _budget=context.token_budget,
        )

        # Merge context allowed_tools with agent's base allowed_tools
        effective_tools = self._allowed_tools & context.allowed_tools
        if context.allowed_tools:
            # If context specifies tools, intersect for least-privilege
            self._current_context = AgentContext(
                task_id=context.task_id,
                task_data=context.task_data,
                token_budget=context.token_budget,
                allowed_tools=effective_tools,
                metadata=context.metadata,
            )

        logger.info(
            "agent.task_accepted",
            agent_id=self._agent_id,
            task_id=str(context.task_id),
            token_budget=context.token_budget,
        )
        return True

    # ── Lifecycle: execute ──────────────────────────────────────────────

    async def execute(self, context: AgentContext) -> AgentResult:
        """
        Execute the accepted task.

        Transitions: ACCEPTING → EXECUTING → COMPLETED | FAILED.

        Raises ``AgentLifecycleError`` if not in ACCEPTING state.
        Delegates to ``_do_execute()`` which subclasses implement.
        After execution (success or failure), resets to IDLE for reuse.
        """
        if self._state != AgentState.ACCEPTING:
            raise AgentLifecycleError(
                self._agent_id, self._state, "execute"
            )

        self._state = AgentState.EXECUTING

        logger.info(
            "agent.executing",
            agent_id=self._agent_id,
            task_id=str(context.task_id),
        )

        try:
            result = await self._do_execute(context)

            if result.success:
                self._state = AgentState.COMPLETED
                logger.info(
                    "agent.completed",
                    agent_id=self._agent_id,
                    task_id=str(context.task_id),
                    tokens_used=result.tokens_used,
                )
            else:
                self._state = AgentState.FAILED
                logger.warning(
                    "agent.failed",
                    agent_id=self._agent_id,
                    task_id=str(context.task_id),
                    error=result.error,
                )

            return result
        except Exception as exc:
            self._state = AgentState.FAILED
            logger.error(
                "agent.exception",
                agent_id=self._agent_id,
                task_id=str(context.task_id),
                error=str(exc),
            )
            return AgentResult(
                success=False,
                error=str(exc),
                tokens_used=(
                    self._token_tracker.used if self._token_tracker else 0
                ),
            )
        finally:
            # Stateless: reset for next task
            self._reset()

    # ── Lifecycle: health_check ─────────────────────────────────────────

    async def health_check(self) -> HealthStatus:
        """
        Return current health status.

        Default implementation: agent is healthy if not TERMINATED.
        Subclasses may override for deeper checks (e.g. LLM reachability).
        """
        return HealthStatus(
            agent_id=self._agent_id,
            agent_type=self._agent_type,
            state=self._state.value,
            is_healthy=self._state != AgentState.TERMINATED,
            last_check=datetime.now(timezone.utc),
        )

    # ── Tool access ─────────────────────────────────────────────────────

    def register_tools(self) -> None:
        """
        Register tools with the agent.

        Default: no-op. Subclasses override to register domain tools.
        This is intentionally empty - base agents have no default tools.
        """
        pass  # Intentional no-op: subclasses override to register tools

    def use_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """
        Execute a tool from the registry, enforcing permissions.

        Raises ``ToolPermissionDeniedError`` if not allowed.
        Raises ``ToolNotFoundError`` if tool not registered.
        Raises ``RuntimeError`` if no tool registry is configured.
        """
        if self._tool_registry is None:
            raise RuntimeError(
                f"Agent '{self._agent_id}' has no tool registry configured."
            )

        effective_tools = (
            self._current_context.allowed_tools
            if self._current_context
            else self._allowed_tools
        )

        return self._tool_registry.execute_tool(
            allowed_tools=effective_tools,
            tool_name=tool_name,
            agent_id=self._agent_id,
            **kwargs,
        )

    # ── Abstract ────────────────────────────────────────────────────────

    @abc.abstractmethod
    async def _do_execute(self, context: AgentContext) -> AgentResult:
        """
        Subclass implementation of task execution.

        This is where domain-specific agent logic goes.
        Must return an ``AgentResult``.
        """
        ...

    # ── Internal ────────────────────────────────────────────────────────

    def _reset(self) -> None:
        """Reset agent to IDLE for reuse (stateless worker contract)."""
        self._state = AgentState.IDLE
        self._current_context = None
        self._token_tracker = None
