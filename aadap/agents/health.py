"""
AADAP — Agent Health Check Protocol
=======================================
Timeout-enforced health checking for agent instances.

Architecture layer: L4 (Agent Layer).

Usage:
    checker = AgentHealthChecker()
    status = await checker.check(agent, timeout_seconds=5.0)
    statuses = await checker.check_all(agents, timeout_seconds=5.0)
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from aadap.core.logging import get_logger

if TYPE_CHECKING:
    from aadap.agents.base import BaseAgent

logger = get_logger(__name__)


# ── Health Status ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class HealthStatus:
    """Snapshot of an agent's health at a point in time."""

    agent_id: str
    agent_type: str
    state: str
    is_healthy: bool
    last_check: datetime
    error: str | None = None
    latency_ms: float = 0.0


# ── Health Checker ──────────────────────────────────────────────────────


DEFAULT_TIMEOUT_SECONDS = 5.0


class AgentHealthChecker:
    """
    Runs health checks on agents with timeout enforcement.

    If an agent's ``health_check()`` does not complete within the
    configured timeout, the agent is reported as unhealthy.
    """

    async def check(
        self,
        agent: BaseAgent,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> HealthStatus:
        """
        Run a health check on a single agent.

        Parameters
        ----------
        agent
            The agent instance to check.
        timeout_seconds
            Maximum time to wait for the health check response.

        Returns
        -------
        HealthStatus
            Always returns a status — never raises.
        """
        start = time.monotonic()
        try:
            status = await asyncio.wait_for(
                agent.health_check(),
                timeout=timeout_seconds,
            )
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.debug(
                "health_check.passed",
                agent_id=agent.agent_id,
                latency_ms=round(elapsed_ms, 2),
            )
            return status
        except asyncio.TimeoutError:
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.warning(
                "health_check.timeout",
                agent_id=agent.agent_id,
                timeout_seconds=timeout_seconds,
            )
            return HealthStatus(
                agent_id=agent.agent_id,
                agent_type=agent.agent_type,
                state=agent.state.value,
                is_healthy=False,
                last_check=datetime.now(timezone.utc),
                error=f"Health check timed out after {timeout_seconds}s",
                latency_ms=round(elapsed_ms, 2),
            )
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.error(
                "health_check.error",
                agent_id=agent.agent_id,
                error=str(exc),
            )
            return HealthStatus(
                agent_id=agent.agent_id,
                agent_type=agent.agent_type,
                state=agent.state.value,
                is_healthy=False,
                last_check=datetime.now(timezone.utc),
                error=str(exc),
                latency_ms=round(elapsed_ms, 2),
            )

    async def check_all(
        self,
        agents: list[BaseAgent],
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> list[HealthStatus]:
        """
        Run health checks on multiple agents concurrently.

        Returns a list of ``HealthStatus`` — one per agent, in the
        same order as the input list.
        """
        tasks = [
            self.check(agent, timeout_seconds) for agent in agents
        ]
        return list(await asyncio.gather(*tasks))
