"""
AADAP — Agent Pool Manager
==============================
Manages a pool of agent instances with lifecycle tracking.

Architecture layer: L4 (Agent Layer).

Usage:
    pool = AgentPoolManager(max_pool_size=20)
    pool.register_agent(my_agent)
    agent = pool.acquire_agent("developer")
    # ... use agent ...
    pool.release_agent(agent.agent_id)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aadap.agents.health import AgentHealthChecker, HealthStatus
from aadap.core.logging import get_logger

if TYPE_CHECKING:
    from aadap.agents.base import AgentState, BaseAgent

logger = get_logger(__name__)


# ── Exceptions ──────────────────────────────────────────────────────────


class AgentNotFoundError(Exception):
    """Raised when the requested agent is not in the pool."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        super().__init__(f"Agent '{agent_id}' is not in the pool.")


class NoAvailableAgentError(Exception):
    """Raised when no idle agent of the requested type is available."""

    def __init__(self, agent_type: str) -> None:
        self.agent_type = agent_type
        super().__init__(
            f"No idle agent of type '{agent_type}' available in the pool."
        )


class PoolCapacityError(Exception):
    """Raised when the pool is at maximum capacity."""

    def __init__(self, max_size: int) -> None:
        self.max_size = max_size
        super().__init__(f"Agent pool is at maximum capacity ({max_size}).")


# ── Pool Manager ────────────────────────────────────────────────────────

DEFAULT_MAX_POOL_SIZE = 50


class AgentPoolManager:
    """
    Manages a bounded pool of agent instances.

    Agents are registered, acquired for task execution, and released
    back to the pool.  Pool size is capped to prevent unbounded growth.
    """

    def __init__(self, max_pool_size: int = DEFAULT_MAX_POOL_SIZE) -> None:
        self._agents: dict[str, BaseAgent] = {}
        self._max_pool_size = max_pool_size
        self._health_checker = AgentHealthChecker()

    @property
    def size(self) -> int:
        """Current number of agents in the pool."""
        return len(self._agents)

    @property
    def max_pool_size(self) -> int:
        return self._max_pool_size

    def register_agent(self, agent: BaseAgent) -> None:
        """
        Add an agent to the pool.

        Raises ``PoolCapacityError`` if the pool is full.
        Raises ``ValueError`` if an agent with the same ID already exists.
        """
        if len(self._agents) >= self._max_pool_size:
            raise PoolCapacityError(self._max_pool_size)
        if agent.agent_id in self._agents:
            raise ValueError(
                f"Agent '{agent.agent_id}' is already registered in the pool."
            )
        self._agents[agent.agent_id] = agent
        logger.info(
            "pool.agent_registered",
            agent_id=agent.agent_id,
            agent_type=agent.agent_type,
            pool_size=len(self._agents),
        )

    def unregister_agent(self, agent_id: str) -> None:
        """
        Remove an agent from the pool.

        Raises ``AgentNotFoundError`` if not found.
        """
        if agent_id not in self._agents:
            raise AgentNotFoundError(agent_id)
        del self._agents[agent_id]
        logger.info(
            "pool.agent_unregistered",
            agent_id=agent_id,
            pool_size=len(self._agents),
        )

    def get_agent(self, agent_id: str) -> BaseAgent:
        """
        Retrieve an agent by ID.

        Raises ``AgentNotFoundError`` if not found.
        """
        agent = self._agents.get(agent_id)
        if agent is None:
            raise AgentNotFoundError(agent_id)
        return agent

    def get_available_agents(self, agent_type: str | None = None) -> list[BaseAgent]:
        """
        Return all agents in IDLE state, optionally filtered by type.
        """
        from aadap.agents.base import AgentState

        result = [
            a for a in self._agents.values()
            if a.state == AgentState.IDLE
        ]
        if agent_type is not None:
            result = [a for a in result if a.agent_type == agent_type]
        return result

    def acquire_agent(self, agent_type: str) -> BaseAgent:
        """
        Acquire an idle agent of the given type from the pool.

        Raises ``NoAvailableAgentError`` if none available.
        """
        available = self.get_available_agents(agent_type)
        if not available:
            raise NoAvailableAgentError(agent_type)
        agent = available[0]
        logger.info(
            "pool.agent_acquired",
            agent_id=agent.agent_id,
            agent_type=agent_type,
        )
        return agent

    def release_agent(self, agent_id: str) -> None:
        """
        Release an agent back to IDLE.

        This is a safety net — ``BaseAgent.execute()`` already resets
        to IDLE after completion.  Calling this on an already-IDLE
        agent is a no-op.

        Raises ``AgentNotFoundError`` if not found.
        """
        agent = self.get_agent(agent_id)
        agent._reset()
        logger.info(
            "pool.agent_released",
            agent_id=agent_id,
        )

    async def health_check_all(
        self, timeout_seconds: float = 5.0,
    ) -> dict[str, HealthStatus]:
        """
        Run health checks on every agent in the pool.

        Returns a dict mapping agent_id → HealthStatus.
        """
        agents = list(self._agents.values())
        statuses = await self._health_checker.check_all(agents, timeout_seconds)
        return {s.agent_id: s for s in statuses}

    def list_agents(self) -> list[BaseAgent]:
        """Return all agents in the pool."""
        return list(self._agents.values())
