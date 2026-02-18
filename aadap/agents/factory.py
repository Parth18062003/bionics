"""
AADAP — Agent Factory
========================
Convenience wiring to create agents, register them in a pool,
and configure their tool sets.

Architecture layer: L4 (Agent Layer).
Phase 7: adds Fabric agent instantiation alongside Databricks.

Usage:
    from aadap.agents.factory import create_fabric_agent, wire_pool

    # Single agent:
    agent, tools = create_fabric_agent(llm_client, fabric_client)

    # Full pool:
    pool = wire_pool(llm_client, fabric_client=fabric_client)
    agent = pool.acquire_agent("fabric")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aadap.agents.developer_agent import DeveloperAgent
from aadap.agents.fabric_agent import FabricAgent
from aadap.agents.pool_manager import AgentPoolManager
from aadap.agents.tools.fabric_tools import (
    FABRIC_TOOL_NAMES,
    register_fabric_tools,
)
from aadap.agents.tools.registry import ToolRegistry
from aadap.core.logging import get_logger

if TYPE_CHECKING:
    from aadap.integrations.fabric_client import BaseFabricClient
    from aadap.integrations.llm_client import BaseLLMClient

logger = get_logger(__name__)


def create_fabric_agent(
    llm_client: BaseLLMClient,
    fabric_client: BaseFabricClient,
    *,
    agent_id: str = "fabric-default",
    model: str = "gpt-4o",
    language: str = "python",
    token_budget: int | None = None,
    registry: ToolRegistry | None = None,
) -> tuple[FabricAgent, ToolRegistry]:
    """
    Create a :class:`FabricAgent` with its tools registered.

    Parameters
    ----------
    llm_client
        LLM backend (real or mock).
    fabric_client
        Fabric execution backend (real or mock).
    agent_id
        Unique agent identifier.
    model
        LLM deployment name.
    language
        Default target language (python / scala / sql).
    token_budget
        Optional token budget override.
    registry
        Existing :class:`ToolRegistry`; a new one is created if ``None``.

    Returns
    -------
    tuple[FabricAgent, ToolRegistry]
        The configured agent and its tool registry.
    """
    kwargs: dict = {}
    if token_budget is not None:
        kwargs["token_budget"] = token_budget

    agent = FabricAgent(
        agent_id=agent_id,
        llm_client=llm_client,
        model=model,
        default_language=language,
        fabric_client=fabric_client,
        **kwargs,
    )

    if registry is None:
        registry = ToolRegistry()
    register_fabric_tools(registry, fabric_client)

    logger.info(
        "factory.fabric_agent_created",
        agent_id=agent_id,
        language=language,
        tools=sorted(FABRIC_TOOL_NAMES),
    )
    return agent, registry


def create_developer_agent(
    llm_client: BaseLLMClient,
    *,
    agent_id: str = "developer-default",
    model: str = "gpt-4o",
    token_budget: int | None = None,
) -> DeveloperAgent:
    """
    Create a :class:`DeveloperAgent` (Databricks Python).

    Parameters
    ----------
    llm_client
        LLM backend.
    agent_id
        Unique agent identifier.
    model
        LLM deployment name.
    token_budget
        Optional token budget override.

    Returns
    -------
    DeveloperAgent
    """
    kwargs: dict = {}
    if token_budget is not None:
        kwargs["token_budget"] = token_budget

    agent = DeveloperAgent(
        agent_id=agent_id,
        llm_client=llm_client,
        model=model,
        **kwargs,
    )
    logger.info("factory.developer_agent_created", agent_id=agent_id)
    return agent


def wire_pool(
    llm_client: BaseLLMClient,
    *,
    fabric_client: BaseFabricClient | None = None,
    max_pool_size: int = 50,
    fabric_languages: list[str] | None = None,
) -> AgentPoolManager:
    """
    Create a pool pre-populated with standard agents.

    Registers:
    - 1 DeveloperAgent  (``agent_type="developer"``)
    - 1 FabricAgent per language in *fabric_languages*
      (defaults to ``["python", "scala", "sql"]``)

    Parameters
    ----------
    llm_client
        LLM backend (shared by all agents).
    fabric_client
        Optional Fabric backend — Fabric agents are skipped if ``None``.
    max_pool_size
        Upper bound on pool membership.
    fabric_languages
        Languages for which to create Fabric agents.

    Returns
    -------
    AgentPoolManager
        Pool with agents registered and ready for ``acquire_agent()``.
    """
    pool = AgentPoolManager(max_pool_size=max_pool_size)

    # ── Databricks developer agent ──
    dev = create_developer_agent(llm_client, agent_id="dev-pool-1")
    pool.register_agent(dev)

    # ── Fabric agents (one per language) ──
    if fabric_client is not None:
        if fabric_languages is None:
            fabric_languages = ["python", "scala", "sql"]

        shared_registry = ToolRegistry()
        register_fabric_tools(shared_registry, fabric_client)

        for lang in fabric_languages:
            agent_id = f"fabric-{lang}-pool-1"
            agent = FabricAgent(
                agent_id=agent_id,
                llm_client=llm_client,
                default_language=lang,
                fabric_client=fabric_client,
            )
            pool.register_agent(agent)
            logger.info(
                "factory.pool_fabric_agent",
                agent_id=agent_id,
                language=lang,
            )

    logger.info(
        "factory.pool_wired",
        pool_size=pool.size,
        max_pool_size=max_pool_size,
    )
    return pool
