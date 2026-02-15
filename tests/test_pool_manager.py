"""
AADAP — Agent Pool Manager Tests
====================================
Validates:
- Register and retrieve agents
- Acquire returns idle agent of matching type
- Release returns agent to idle
- Acquire raises when no idle agents available
- Unregister removes agent
- Health check all reports status of every pooled agent
- Pool capacity enforcement
"""

from __future__ import annotations

import uuid

import pytest

from aadap.agents.base import AgentContext, AgentResult, AgentState, BaseAgent
from aadap.agents.pool_manager import (
    AgentNotFoundError,
    AgentPoolManager,
    NoAvailableAgentError,
    PoolCapacityError,
)


# ── Test agent ───────────────────────────────────────────────────────────


class StubAgent(BaseAgent):
    """Minimal agent for pool testing."""

    async def _do_execute(self, context: AgentContext) -> AgentResult:
        return AgentResult(success=True, output="stub")


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def pool() -> AgentPoolManager:
    return AgentPoolManager(max_pool_size=5)


@pytest.fixture
def agent_dev() -> StubAgent:
    return StubAgent(agent_id="dev-1", agent_type="developer")


@pytest.fixture
def agent_dev2() -> StubAgent:
    return StubAgent(agent_id="dev-2", agent_type="developer")


@pytest.fixture
def agent_val() -> StubAgent:
    return StubAgent(agent_id="val-1", agent_type="validator")


# ── Tests ────────────────────────────────────────────────────────────────


class TestRegistration:
    """Register, get, unregister agents."""

    def test_register_and_get(
        self, pool: AgentPoolManager, agent_dev: StubAgent
    ):
        pool.register_agent(agent_dev)
        retrieved = pool.get_agent("dev-1")
        assert retrieved.agent_id == "dev-1"

    def test_register_duplicate_raises(
        self, pool: AgentPoolManager, agent_dev: StubAgent
    ):
        pool.register_agent(agent_dev)
        with pytest.raises(ValueError, match="already registered"):
            pool.register_agent(agent_dev)

    def test_unregister(
        self, pool: AgentPoolManager, agent_dev: StubAgent
    ):
        pool.register_agent(agent_dev)
        pool.unregister_agent("dev-1")
        with pytest.raises(AgentNotFoundError):
            pool.get_agent("dev-1")

    def test_unregister_unknown_raises(self, pool: AgentPoolManager):
        with pytest.raises(AgentNotFoundError):
            pool.unregister_agent("nonexistent")

    def test_get_unknown_raises(self, pool: AgentPoolManager):
        with pytest.raises(AgentNotFoundError):
            pool.get_agent("nonexistent")

    def test_pool_size(
        self, pool: AgentPoolManager, agent_dev: StubAgent, agent_val: StubAgent
    ):
        assert pool.size == 0
        pool.register_agent(agent_dev)
        assert pool.size == 1
        pool.register_agent(agent_val)
        assert pool.size == 2


class TestPoolCapacity:
    """Pool size limits."""

    def test_capacity_enforced(self):
        pool = AgentPoolManager(max_pool_size=2)
        pool.register_agent(StubAgent(agent_id="a1", agent_type="dev"))
        pool.register_agent(StubAgent(agent_id="a2", agent_type="dev"))
        with pytest.raises(PoolCapacityError, match="maximum capacity"):
            pool.register_agent(StubAgent(agent_id="a3", agent_type="dev"))


class TestAcquireRelease:
    """Acquire and release agent lifecycle."""

    def test_acquire_idle_agent(
        self, pool: AgentPoolManager, agent_dev: StubAgent
    ):
        pool.register_agent(agent_dev)
        acquired = pool.acquire_agent("developer")
        assert acquired.agent_id == "dev-1"

    def test_acquire_no_idle_raises(
        self, pool: AgentPoolManager
    ):
        with pytest.raises(NoAvailableAgentError, match="developer"):
            pool.acquire_agent("developer")

    async def test_acquire_after_busy_raises(
        self, pool: AgentPoolManager, agent_dev: StubAgent
    ):
        pool.register_agent(agent_dev)
        ctx = AgentContext(
            task_id=uuid.uuid4(),
            task_data={"x": 1},
            allowed_tools=set(),
        )
        await agent_dev.accept_task(ctx)
        # Agent is now ACCEPTING, not IDLE
        with pytest.raises(NoAvailableAgentError):
            pool.acquire_agent("developer")

    def test_release_resets_to_idle(
        self, pool: AgentPoolManager, agent_dev: StubAgent
    ):
        pool.register_agent(agent_dev)
        pool.release_agent("dev-1")
        assert agent_dev.state == AgentState.IDLE

    def test_release_unknown_raises(self, pool: AgentPoolManager):
        with pytest.raises(AgentNotFoundError):
            pool.release_agent("nonexistent")


class TestAvailableAgents:
    """get_available_agents filtering."""

    def test_filter_by_type(
        self,
        pool: AgentPoolManager,
        agent_dev: StubAgent,
        agent_val: StubAgent,
    ):
        pool.register_agent(agent_dev)
        pool.register_agent(agent_val)
        devs = pool.get_available_agents("developer")
        assert len(devs) == 1
        assert devs[0].agent_type == "developer"

    def test_all_types(
        self,
        pool: AgentPoolManager,
        agent_dev: StubAgent,
        agent_val: StubAgent,
    ):
        pool.register_agent(agent_dev)
        pool.register_agent(agent_val)
        all_agents = pool.get_available_agents()
        assert len(all_agents) == 2


class TestPoolHealthCheck:
    """Batch health check on the pool."""

    async def test_health_check_all(
        self,
        pool: AgentPoolManager,
        agent_dev: StubAgent,
        agent_val: StubAgent,
    ):
        pool.register_agent(agent_dev)
        pool.register_agent(agent_val)
        statuses = await pool.health_check_all(timeout_seconds=2.0)
        assert len(statuses) == 2
        assert "dev-1" in statuses
        assert "val-1" in statuses
        assert all(s.is_healthy for s in statuses.values())

    async def test_health_check_empty_pool(
        self, pool: AgentPoolManager
    ):
        statuses = await pool.health_check_all()
        assert statuses == {}


class TestListAgents:
    """list_agents returns all agents."""

    def test_list_agents(
        self,
        pool: AgentPoolManager,
        agent_dev: StubAgent,
        agent_val: StubAgent,
    ):
        pool.register_agent(agent_dev)
        pool.register_agent(agent_val)
        agents = pool.list_agents()
        assert len(agents) == 2
