"""
AADAP — Artifact API Routes
===============================
REST endpoints for artifact viewing.

Architecture layer: L6 (Presentation).
Phase 7 contract: Artifact viewer.

Usage:
    GET /api/v1/tasks/{task_id}/artifacts              — List artifacts
    GET /api/v1/tasks/{task_id}/artifacts/{artifact_id} — Get artifact detail
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aadap.api.deps import get_session
from aadap.core.logging import get_logger
from aadap.db.models import Artifact

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/tasks/{task_id}/artifacts", tags=["artifacts"])


# ── Response Schemas ────────────────────────────────────────────────────


class ArtifactSummaryResponse(BaseModel):
    """Artifact summary (no content body)."""

    id: str
    task_id: str
    artifact_type: str
    name: str
    content_hash: str | None
    storage_uri: str | None
    created_at: str


class ArtifactDetailResponse(BaseModel):
    """Full artifact detail including content."""

    id: str
    task_id: str
    artifact_type: str
    name: str
    content: str | None
    content_hash: str | None
    storage_uri: str | None
    metadata: dict | None
    created_at: str


# ── Endpoints ───────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=list[ArtifactSummaryResponse],
    summary="List artifacts for a task",
)
async def list_artifacts(
    task_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> list[ArtifactSummaryResponse]:
    """Return all artifacts for the given task."""
    result = await session.execute(
        select(Artifact)
        .where(Artifact.task_id == task_id)
        .order_by(Artifact.created_at)
    )
    artifacts = result.scalars().all()

    return [
        ArtifactSummaryResponse(
            id=str(a.id),
            task_id=str(a.task_id),
            artifact_type=a.artifact_type,
            name=a.name,
            content_hash=a.content_hash,
            storage_uri=a.storage_uri,
            created_at=a.created_at.isoformat() if a.created_at else "",
        )
        for a in artifacts
    ]


@router.get(
    "/{artifact_id}",
    response_model=ArtifactDetailResponse,
    summary="Get artifact detail",
)
async def get_artifact(
    task_id: uuid.UUID,
    artifact_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ArtifactDetailResponse:
    """Get full artifact detail including content."""
    result = await session.execute(
        select(Artifact).where(
            Artifact.id == artifact_id,
            Artifact.task_id == task_id,
        )
    )
    artifact = result.scalar_one_or_none()
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found.")

    return ArtifactDetailResponse(
        id=str(artifact.id),
        task_id=str(artifact.task_id),
        artifact_type=artifact.artifact_type,
        name=artifact.name,
        content=artifact.content,
        content_hash=artifact.content_hash,
        storage_uri=artifact.storage_uri,
        metadata=artifact.metadata_,
        created_at=artifact.created_at.isoformat() if artifact.created_at else "",
    )
