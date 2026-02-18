"""
AADAP — Marketplace API Routes
==================================
REST endpoints for the Agent Marketplace.

Architecture layer: L6 (Presentation).

Usage:
    GET  /api/v1/marketplace/agents           — List available agents
    GET  /api/v1/marketplace/agents/{agent_id} — Get agent details
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from aadap.core.logging import get_logger
from aadap.services.marketplace import get_agent_by_id, get_agent_catalog

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/marketplace", tags=["marketplace"])


# ── Response Schemas ────────────────────────────────────────────────────


class AgentResponse(BaseModel):
    """Agent catalog entry returned by the API."""

    id: str
    name: str
    description: str
    platform: str
    languages: list[str]
    capabilities: list[str]
    icon: str
    status: str
    config_defaults: dict


# ── Endpoints ───────────────────────────────────────────────────────────


@router.get(
    "/agents",
    response_model=list[AgentResponse],
    summary="List available agents",
    description="Returns the full agent marketplace catalog.",
)
async def list_agents() -> list[AgentResponse]:
    """Return all agents in the marketplace."""
    catalog = get_agent_catalog()
    logger.info("api.marketplace.list", count=len(catalog))
    return [AgentResponse(**entry) for entry in catalog]


@router.get(
    "/agents/{agent_id}",
    response_model=AgentResponse,
    summary="Get agent details",
    description="Returns details for a specific agent by ID.",
)
async def get_agent(agent_id: str) -> AgentResponse:
    """Get a single agent by ID."""
    entry = get_agent_by_id(agent_id)
    if entry is None:
        raise HTTPException(
            status_code=404, detail=f"Agent '{agent_id}' not found.")
    return AgentResponse(**entry)
