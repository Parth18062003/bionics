"""
AADAP — Agent Health Check Tests
====================================
Validates:
- Healthy agent returns is_healthy=True
- Timeout produces is_healthy=False with error
- Batch health check processes all agents
- Latency measurement is recorded
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from aadap.agents.base import AgentContext, AgentResult, AgentState, BaseAgent
from aadap.agents.health import AgentHealthChecker, HealthStatus


# ── Test agents ──────────────────────────────────────────────────────────


class HealthyAgent(BaseAgent):
    """Agent that always passes health checks."""

    async def _do_execute(self, context: AgentContext) -> AgentResult:
        return AgentResult(success=True, output="ok")


class SlowHealthAgent(BaseAgent):
    """Agent whose health check takes too long."""

    async def health_check(self) -> HealthStatus:
        await asyncio.sleep(10)  # Will be timed out
        return HealthStatus(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            state=self.state.value,
            is_healthy=True,
            last_check=__import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ),
        )

    async def _do_execute(self, context: AgentContext) -> AgentResult:
        return AgentResult(success=True, output="ok")


class ErrorHealthAgent(BaseAgent):
    """Agent whose health check raises an exception."""

    async def health_check(self) -> HealthStatus:
        raise ConnectionError("LLM unreachable")

    async def _do_execute(self, context: AgentContext) -> AgentResult:
        return AgentResult(success=True, output="ok")


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def checker() -> AgentHealthChecker:
    return AgentHealthChecker()


@pytest.fixture
def healthy_agent() -> HealthyAgent:
    return HealthyAgent(agent_id="h-1", agent_type="dev")


@pytest.fixture
def slow_agent() -> SlowHealthAgent:
    return SlowHealthAgent(agent_id="slow-1", agent_type="dev")


@pytest.fixture
def error_agent() -> ErrorHealthAgent:
    return ErrorHealthAgent(agent_id="err-1", agent_type="dev")


# ── Tests ────────────────────────────────────────────────────────────────


class TestHealthCheck:
    """Single agent health checks."""

    async def test_healthy_agent(
        self, checker: AgentHealthChecker, healthy_agent: HealthyAgent
    ):
        status = await checker.check(healthy_agent, timeout_seconds=2.0)
        assert status.is_healthy is True
        assert status.agent_id == "h-1"
        assert status.agent_type == "dev"
        assert status.error is None

    async def test_timeout_produces_unhealthy(
        self, checker: AgentHealthChecker, slow_agent: SlowHealthAgent
    ):
        status = await checker.check(slow_agent, timeout_seconds=0.1)
        assert status.is_healthy is False
        assert "timed out" in status.error

    async def test_error_produces_unhealthy(
        self, checker: AgentHealthChecker, error_agent: ErrorHealthAgent
    ):
        status = await checker.check(error_agent, timeout_seconds=2.0)
        assert status.is_healthy is False
        assert "LLM unreachable" in status.error

    async def test_latency_recorded(
        self, checker: AgentHealthChecker, healthy_agent: HealthyAgent
    ):
        status = await checker.check(healthy_agent, timeout_seconds=2.0)
        assert status.latency_ms >= 0


class TestBatchHealthCheck:
    """Batch health checks."""

    async def test_check_all(
        self,
        checker: AgentHealthChecker,
        healthy_agent: HealthyAgent,
        error_agent: ErrorHealthAgent,
    ):
        statuses = await checker.check_all(
            [healthy_agent, error_agent], timeout_seconds=2.0
        )
        assert len(statuses) == 2
        healthy = [s for s in statuses if s.is_healthy]
        unhealthy = [s for s in statuses if not s.is_healthy]
        assert len(healthy) == 1
        assert len(unhealthy) == 1

    async def test_check_all_empty(self, checker: AgentHealthChecker):
        statuses = await checker.check_all([], timeout_seconds=2.0)
        assert statuses == []
