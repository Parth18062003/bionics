"""
AADAP — Agent Dispatcher
===========================
Dispatches tasks to appropriate agents based on routing decisions.

Architecture layer: L5 (Orchestration).

This module provides the glue between:
- TaskRouter (routing decisions)
- AgentPoolManager (agent lifecycle)
- BaseAgent implementations (actual execution)

Usage:
    dispatcher = AgentDispatcher(llm_client=llm, agent_pool=pool)
    result = await dispatcher.dispatch_and_execute("developer", context)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from aadap.agents.base import AgentContext, AgentResult, BaseAgent
from aadap.agents.pool_manager import AgentPoolManager, NoAvailableAgentError
from aadap.core.logging import get_logger
from aadap.integrations.llm_client import BaseLLMClient

logger = get_logger(__name__)


@dataclass
class DispatchResult:
    """Result of a dispatch operation."""

    success: bool
    agent_id: str | None = None
    agent_type: str | None = None
    agent_result: AgentResult | None = None
    error: str | None = None


class AgentDispatcher:
    """
    Dispatches tasks to agents based on routing decisions.

    Responsibilities:
    1. Map agent_type strings to concrete agent classes
    2. Acquire agents from the pool (or create on-demand)
    3. Execute the agent with the provided context
    4. Return results to the orchestrator
    """

    def __init__(
        self,
        llm_client: BaseLLMClient,
        agent_pool: AgentPoolManager | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._agent_pool = agent_pool or AgentPoolManager()
        self._agent_factories: dict[str, callable] = {}
        self._register_default_factories()

    def _register_default_factories(self) -> None:
        """Register factory functions for known agent types."""

        self._agent_factories["developer"] = self._create_developer_agent
        self._agent_factories["validation"] = self._create_validation_agent
        self._agent_factories["optimization"] = self._create_optimization_agent
        self._agent_factories["ingestion"] = self._create_ingestion_agent
        self._agent_factories["etl_pipeline"] = self._create_etl_pipeline_agent
        self._agent_factories["job_scheduler"] = self._create_job_scheduler_agent
        self._agent_factories["catalog"] = self._create_catalog_agent
        self._agent_factories["fabric"] = self._create_fabric_agent

    def register_factory(self, agent_type: str, factory: callable) -> None:
        """Register a custom factory for an agent type."""
        self._agent_factories[agent_type] = factory
        logger.info(
            "dispatcher.factory_registered",
            agent_type=agent_type,
        )

    def _create_developer_agent(self, agent_id: str) -> BaseAgent:
        """Create a DeveloperAgent instance."""
        from aadap.agents.developer_agent import DeveloperAgent
        return DeveloperAgent(
            agent_id=agent_id,
            llm_client=self._llm_client,
        )

    def _create_validation_agent(self, agent_id: str) -> BaseAgent:
        """Create a ValidationAgent instance."""
        from aadap.agents.validation_agent import ValidationAgent
        return ValidationAgent(
            agent_id=agent_id,
            llm_client=self._llm_client,
        )

    def _create_optimization_agent(self, agent_id: str) -> BaseAgent:
        """Create an OptimizationAgent instance."""
        from aadap.agents.optimization_agent import OptimizationAgent
        return OptimizationAgent(
            agent_id=agent_id,
            llm_client=self._llm_client,
        )

    def _create_ingestion_agent(self, agent_id: str) -> BaseAgent:
        """Create an IngestionAgent instance."""
        from aadap.agents.ingestion_agent import IngestionAgent
        return IngestionAgent(
            agent_id=agent_id,
            llm_client=self._llm_client,
            platform_adapter=None,
        )

    def _create_etl_pipeline_agent(self, agent_id: str) -> BaseAgent:
        """Create an ETLPipelineAgent instance."""
        from aadap.agents.etl_pipeline_agent import ETLPipelineAgent
        return ETLPipelineAgent(
            agent_id=agent_id,
            llm_client=self._llm_client,
            platform_adapter=None,
        )

    def _create_job_scheduler_agent(self, agent_id: str) -> BaseAgent:
        """Create a JobSchedulerAgent instance."""
        from aadap.agents.job_scheduler_agent import JobSchedulerAgent
        return JobSchedulerAgent(
            agent_id=agent_id,
            llm_client=self._llm_client,
            platform_adapter=None,
        )

    def _create_catalog_agent(self, agent_id: str) -> BaseAgent:
        """Create a CatalogAgent instance."""
        from aadap.agents.catalog_agent import CatalogAgent
        return CatalogAgent(
            agent_id=agent_id,
            llm_client=self._llm_client,
            platform_adapter=None,
        )

    def _create_fabric_agent(self, agent_id: str) -> BaseAgent:
        """Create a FabricAgent instance."""
        from aadap.agents.fabric_agent import FabricAgent
        return FabricAgent(
            agent_id=agent_id,
            llm_client=self._llm_client,
        )

    def _create_agent_id(self, agent_type: str) -> str:
        """Generate a unique agent ID."""
        return f"{agent_type}-{uuid.uuid4().hex[:8]}"

    async def acquire_or_create_agent(
        self,
        agent_type: str,
    ) -> BaseAgent:
        """
        Acquire an idle agent from the pool or create a new one.

        Raises NoAvailableAgentError if pool is full and no idle agent exists.
        """
        try:
            agent = self._agent_pool.acquire_agent(agent_type)
            logger.info(
                "dispatcher.agent_acquired",
                agent_id=agent.agent_id,
                agent_type=agent_type,
                source="pool",
            )
            return agent
        except NoAvailableAgentError:
            pass

        factory = self._agent_factories.get(agent_type)
        if not factory:
            raise ValueError(f"No factory registered for agent type: {agent_type}")

        agent_id = self._create_agent_id(agent_type)
        agent = factory(agent_id)

        self._agent_pool.register_agent(agent)

        logger.info(
            "dispatcher.agent_created",
            agent_id=agent.agent_id,
            agent_type=agent_type,
            source="factory",
        )
        return agent

    async def dispatch_and_execute(
        self,
        agent_type: str,
        context: AgentContext,
    ) -> AgentResult:
        """
        Dispatch a task to an agent and execute it.

        This is the main entry point for agent execution.

        Parameters
        ----------
        agent_type
            The type of agent to dispatch to (e.g., "developer", "validation")
        context
            The agent context containing task data

        Returns
        -------
        AgentResult
            The result of the agent execution
        """
        logger.info(
            "dispatcher.dispatch_start",
            task_id=str(context.task_id),
            agent_type=agent_type,
        )

        try:
            agent = await self.acquire_or_create_agent(agent_type)

            accepted = await agent.accept_task(context)
            if not accepted:
                return AgentResult(
                    success=False,
                    error=f"Agent {agent.agent_id} rejected the task",
                )

            result = await agent.execute(context)

            logger.info(
                "dispatcher.dispatch_complete",
                task_id=str(context.task_id),
                agent_id=agent.agent_id,
                agent_type=agent_type,
                success=result.success,
                tokens_used=result.tokens_used,
            )

            return result

        except ValueError as exc:
            logger.error(
                "dispatcher.unknown_agent_type",
                task_id=str(context.task_id),
                agent_type=agent_type,
                error=str(exc),
            )
            return AgentResult(
                success=False,
                error=f"Unknown agent type: {agent_type}",
            )

        except Exception as exc:
            logger.error(
                "dispatcher.dispatch_failed",
                task_id=str(context.task_id),
                agent_type=agent_type,
                error=str(exc),
            )
            return AgentResult(
                success=False,
                error=f"Dispatch failed: {exc}",
            )

    async def dispatch_batch(
        self,
        dispatches: list[tuple[str, AgentContext]],
    ) -> list[AgentResult]:
        """
        Dispatch multiple tasks in parallel.

        Parameters
        ----------
        dispatches
            List of (agent_type, context) tuples

        Returns
        -------
        list[AgentResult]
            Results in the same order as inputs
        """
        import asyncio

        tasks = [
            self.dispatch_and_execute(agent_type, context)
            for agent_type, context in dispatches
        ]

        return await asyncio.gather(*tasks)

    @property
    def agent_pool(self) -> AgentPoolManager:
        """Return the agent pool manager."""
        return self._agent_pool

    def get_available_agent_types(self) -> list[str]:
        """Return list of registered agent types."""
        return list(self._agent_factories.keys())
