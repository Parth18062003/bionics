"""
AADAP — BaseAgent Lifecycle Tests
====================================
Validates:
- Lifecycle state transitions (IDLE → ACCEPTING → EXECUTING → COMPLETED/FAILED → IDLE)
- Stateless worker contract (reset after execution)
- Guard: cannot execute without accepting
- Guard: cannot accept while executing
"""

from __future__ import annotations

import uuid

import pytest

from aadap.agents.base import (
    AgentContext,
    AgentLifecycleError,
    AgentResult,
    AgentState,
    BaseAgent,
)


# ── Concrete test agent ─────────────────────────────────────────────────


class SuccessAgent(BaseAgent):
    """Agent that always succeeds."""

    async def _do_execute(self, context: AgentContext) -> AgentResult:
        return AgentResult(success=True, output="done", tokens_used=42)


class FailingAgent(BaseAgent):
    """Agent that always returns a failed result."""

    async def _do_execute(self, context: AgentContext) -> AgentResult:
        return AgentResult(success=False, error="intentional failure", tokens_used=10)


class ExplodingAgent(BaseAgent):
    """Agent that raises an exception during execution."""

    async def _do_execute(self, context: AgentContext) -> AgentResult:
        raise RuntimeError("boom")


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def context() -> AgentContext:
    return AgentContext(
        task_id=uuid.uuid4(),
        task_data={"instruction": "test"},
        token_budget=50_000,
        allowed_tools={"read_file"},
    )


@pytest.fixture
def agent() -> SuccessAgent:
    return SuccessAgent(
        agent_id="test-1",
        agent_type="developer",
        allowed_tools={"read_file", "write_file"},
    )


# ── Tests ────────────────────────────────────────────────────────────────


class TestAgentLifecycle:
    """Lifecycle transition tests."""

    async def test_initial_state_is_idle(self, agent: SuccessAgent):
        assert agent.state == AgentState.IDLE

    async def test_accept_transitions_to_accepting(
        self, agent: SuccessAgent, context: AgentContext
    ):
        result = await agent.accept_task(context)
        assert result is True
        assert agent.state == AgentState.ACCEPTING

    async def test_execute_transitions_to_completed_on_success(
        self, agent: SuccessAgent, context: AgentContext
    ):
        await agent.accept_task(context)
        result = await agent.execute(context)
        assert result.success is True
        assert result.output == "done"
        assert result.tokens_used == 42
        # After execution, agent resets to IDLE (stateless worker)
        assert agent.state == AgentState.IDLE

    async def test_execute_transitions_to_failed_on_failure(
        self, context: AgentContext
    ):
        agent = FailingAgent(
            agent_id="fail-1", agent_type="developer"
        )
        await agent.accept_task(context)
        result = await agent.execute(context)
        assert result.success is False
        assert result.error == "intentional failure"
        # Resets to IDLE even after failure
        assert agent.state == AgentState.IDLE

    async def test_execute_handles_exceptions(
        self, context: AgentContext
    ):
        agent = ExplodingAgent(
            agent_id="explode-1", agent_type="developer"
        )
        await agent.accept_task(context)
        result = await agent.execute(context)
        assert result.success is False
        assert "boom" in result.error
        # Still resets to IDLE
        assert agent.state == AgentState.IDLE


class TestLifecycleGuards:
    """Guards against invalid lifecycle transitions."""

    async def test_cannot_execute_without_accepting(
        self, agent: SuccessAgent, context: AgentContext
    ):
        with pytest.raises(AgentLifecycleError, match="cannot execute"):
            await agent.execute(context)

    async def test_cannot_accept_while_not_idle(
        self, agent: SuccessAgent, context: AgentContext
    ):
        await agent.accept_task(context)
        with pytest.raises(AgentLifecycleError, match="cannot accept_task"):
            await agent.accept_task(context)


class TestStatelessWorker:
    """Agents must be stateless between tasks."""

    async def test_agent_resets_after_success(
        self, agent: SuccessAgent, context: AgentContext
    ):
        await agent.accept_task(context)
        await agent.execute(context)
        # Agent is back to IDLE, ready for another task
        assert agent.state == AgentState.IDLE
        # Can accept again
        result = await agent.accept_task(context)
        assert result is True

    async def test_agent_resets_after_failure(
        self, context: AgentContext
    ):
        agent = FailingAgent(agent_id="f-1", agent_type="dev")
        await agent.accept_task(context)
        await agent.execute(context)
        assert agent.state == AgentState.IDLE

    async def test_agent_resets_after_exception(
        self, context: AgentContext
    ):
        agent = ExplodingAgent(agent_id="e-1", agent_type="dev")
        await agent.accept_task(context)
        await agent.execute(context)
        assert agent.state == AgentState.IDLE


class TestAgentProperties:
    """Property accessors."""

    def test_agent_id(self, agent: SuccessAgent):
        assert agent.agent_id == "test-1"

    def test_agent_type(self, agent: SuccessAgent):
        assert agent.agent_type == "developer"

    def test_allowed_tools_frozen(self, agent: SuccessAgent):
        tools = agent.allowed_tools
        assert isinstance(tools, frozenset)
        assert "read_file" in tools
        assert "write_file" in tools
