"""
AADAP — Artifact API Routes
===============================
REST endpoints for artifact viewing and version management.

Architecture layer: L6 (Presentation).
Phase 7 contract: Artifact viewer.
Phase 4 contract: Code Editor version management.

Usage:
    GET /api/v1/tasks/{task_id}/artifacts              — List artifacts
    GET /api/v1/tasks/{task_id}/artifacts/{artifact_id} — Get artifact detail
    GET /api/v1/tasks/{task_id}/artifacts/{artifact_id}/versions — List versions
    GET /api/v1/tasks/{task_id}/artifacts/{artifact_id}/versions/{version} — Get version
    POST /api/v1/tasks/{task_id}/artifacts/{artifact_id}/versions — Create version
    GET /api/v1/tasks/{task_id}/artifacts/{artifact_id}/diff — Get diff
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
    version: int
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
    version: int
    parent_id: str | None
    edit_message: str | None
    metadata: dict | None
    created_at: str


class ArtifactVersionSummary(BaseModel):
    """Summary of a single artifact version."""

    id: str
    version: int
    created_at: str
    content_hash: str | None
    edit_message: str | None


class ArtifactVersionCreateRequest(BaseModel):
    """Request body for creating a new artifact version."""

    content: str
    edit_message: str | None = Field(None, description="Optional message describing changes")


class DiffLine(BaseModel):
    """A single line in a diff comparison."""

    old_line: int | None = Field(None, description="Line number in original (None if added)")
    new_line: int | None = Field(None, description="Line number in new (None if removed)")
    content: str = Field(description="Line content")
    type: str = Field(description="unchanged | added | removed")


class DiffResponse(BaseModel):
    """Response containing diff between two artifact versions."""

    from_version: int
    to_version: int
    from_content: str | None
    to_content: str | None
    diff: list[DiffLine]
    stats: dict[str, int] = Field(description="Count of added, removed, unchanged lines")


# ── Helper Functions ─────────────────────────────────────────────────────


def _compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _get_root_artifact_id(artifact: Artifact) -> uuid.UUID:
    """
    Traverse parent chain to find the root artifact ID.
    The root is the original artifact with no parent.
    """
    # For now, we return the artifact's own ID since we can't
    # traverse the chain synchronously. The version lineage is
    # tracked via parent_id, but the root can be computed by
    # following the chain.
    # In practice, for version listing, we query by finding
    # artifacts that share the same lineage root.
    current_id = artifact.id
    return current_id


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
            version=a.version,
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
        version=artifact.version,
        parent_id=str(artifact.parent_id) if artifact.parent_id else None,
        edit_message=artifact.edit_message,
        metadata=artifact.metadata_,
        created_at=artifact.created_at.isoformat() if artifact.created_at else "",
    )


# ── Version Management Endpoints (EDIT-01, EDIT-03, EDIT-04) ────────────


@router.get(
    "/{artifact_id}/versions",
    response_model=list[ArtifactVersionSummary],
    summary="List all versions of an artifact",
)
async def list_artifact_versions(
    task_id: uuid.UUID,
    artifact_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> list[ArtifactVersionSummary]:
    """
    Return all versions of an artifact lineage.

    Finds the root of the artifact's version lineage and returns all
    artifacts that share that root (same original artifact).
    """
    # First, get the artifact to find its lineage
    result = await session.execute(
        select(Artifact).where(
            Artifact.id == artifact_id,
            Artifact.task_id == task_id,
        )
    )
    artifact = result.scalar_one_or_none()
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found.")

    # Find the root of the lineage by traversing parent chain
    # Start with current artifact, follow parent_id until we reach the root
    visited = {artifact.id}
    current = artifact
    while current.parent_id is not None:
        if current.parent_id in visited:
            # Cycle detected, break
            break
        result = await session.execute(
            select(Artifact).where(Artifact.id == current.parent_id)
        )
        parent = result.scalar_one_or_none()
        if parent is None:
            break
        visited.add(parent.id)
        current = parent

    root_id = current.id

    # Now find all artifacts in this lineage:
    # 1. The root itself (id = root_id)
    # 2. All artifacts that have the root as an ancestor
    #
    # For simplicity, we query for all artifacts where:
    # - id = root_id OR parent_id is in the lineage
    #
    # A more efficient approach would be a recursive CTE, but for now
    # we'll collect all versions by iterating through children

    lineage_ids = {root_id}
    to_process = [root_id]

    while to_process:
        current_id = to_process.pop()
        result = await session.execute(
            select(Artifact).where(Artifact.parent_id == current_id)
        )
        children = result.scalars().all()
        for child in children:
            if child.id not in lineage_ids:
                lineage_ids.add(child.id)
                to_process.append(child.id)

    # Fetch all artifacts in the lineage
    result = await session.execute(
        select(Artifact)
        .where(Artifact.id.in_(lineage_ids))
        .order_by(Artifact.version)
    )
    versions = result.scalars().all()

    return [
        ArtifactVersionSummary(
            id=str(v.id),
            version=v.version,
            created_at=v.created_at.isoformat() if v.created_at else "",
            content_hash=v.content_hash,
            edit_message=v.edit_message,
        )
        for v in versions
    ]


@router.get(
    "/{artifact_id}/versions/{version}",
    response_model=ArtifactDetailResponse,
    summary="Get specific version of an artifact",
)
async def get_artifact_version(
    task_id: uuid.UUID,
    artifact_id: uuid.UUID,
    version: int,
    session: AsyncSession = Depends(get_session),
) -> ArtifactDetailResponse:
    """Get a specific version of an artifact by version number."""
    # First verify the artifact exists and belongs to this task
    result = await session.execute(
        select(Artifact).where(
            Artifact.id == artifact_id,
            Artifact.task_id == task_id,
        )
    )
    artifact = result.scalar_one_or_none()
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found.")

    # Find the root of the lineage (same logic as list_artifact_versions)
    visited = {artifact.id}
    current = artifact
    while current.parent_id is not None:
        if current.parent_id in visited:
            break
        result = await session.execute(
            select(Artifact).where(Artifact.id == current.parent_id)
        )
        parent = result.scalar_one_or_none()
        if parent is None:
            break
        visited.add(parent.id)
        current = parent

    root_id = current.id

    # Collect all lineage IDs
    lineage_ids = {root_id}
    to_process = [root_id]

    while to_process:
        current_id = to_process.pop()
        result = await session.execute(
            select(Artifact).where(Artifact.parent_id == current_id)
        )
        children = result.scalars().all()
        for child in children:
            if child.id not in lineage_ids:
                lineage_ids.add(child.id)
                to_process.append(child.id)

    # Find the artifact with the requested version in this lineage
    result = await session.execute(
        select(Artifact).where(
            Artifact.id.in_(lineage_ids),
            Artifact.version == version,
        )
    )
    version_artifact = result.scalar_one_or_none()

    if version_artifact is None:
        raise HTTPException(
            status_code=404,
            detail=f"Version {version} not found in artifact lineage.",
        )

    return ArtifactDetailResponse(
        id=str(version_artifact.id),
        task_id=str(version_artifact.task_id),
        artifact_type=version_artifact.artifact_type,
        name=version_artifact.name,
        content=version_artifact.content,
        content_hash=version_artifact.content_hash,
        storage_uri=version_artifact.storage_uri,
        version=version_artifact.version,
        parent_id=str(version_artifact.parent_id) if version_artifact.parent_id else None,
        edit_message=version_artifact.edit_message,
        metadata=version_artifact.metadata_,
        created_at=version_artifact.created_at.isoformat() if version_artifact.created_at else "",
    )


@router.post(
    "/{artifact_id}/versions",
    response_model=ArtifactDetailResponse,
    status_code=201,
    summary="Create a new version of an artifact",
)
async def create_artifact_version(
    task_id: uuid.UUID,
    artifact_id: uuid.UUID,
    request: ArtifactVersionCreateRequest,
    session: AsyncSession = Depends(get_session),
) -> ArtifactDetailResponse:
    """
    Save edited content as a new version.

    Creates a new Artifact with incremented version number,
    copying metadata from the parent and linking via parent_id.
    """
    # Get the parent artifact
    result = await session.execute(
        select(Artifact).where(
            Artifact.id == artifact_id,
            Artifact.task_id == task_id,
        )
    )
    parent = result.scalar_one_or_none()
    if parent is None:
        raise HTTPException(status_code=404, detail="Artifact not found.")

    # Find the max version in the lineage
    # First find the root
    visited = {parent.id}
    current = parent
    while current.parent_id is not None:
        if current.parent_id in visited:
            break
        result = await session.execute(
            select(Artifact).where(Artifact.id == current.parent_id)
        )
        p = result.scalar_one_or_none()
        if p is None:
            break
        visited.add(p.id)
        current = p

    root_id = current.id

    # Collect all lineage IDs
    lineage_ids = {root_id}
    to_process = [root_id]
    max_version = current.version

    while to_process:
        current_id = to_process.pop()
        result = await session.execute(
            select(Artifact).where(Artifact.parent_id == current_id)
        )
        children = result.scalars().all()
        for child in children:
            if child.id not in lineage_ids:
                lineage_ids.add(child.id)
                to_process.append(child.id)
                if child.version > max_version:
                    max_version = child.version

    # Create the new version
    new_version = max_version + 1
    content_hash = _compute_content_hash(request.content)

    new_artifact = Artifact(
        task_id=parent.task_id,
        artifact_type=parent.artifact_type,
        name=parent.name,
        content=request.content,
        content_hash=content_hash,
        version=new_version,
        parent_id=parent.id,
        edit_message=request.edit_message,
        storage_uri=None,  # New versions don't inherit storage_uri
        metadata_=parent.metadata_,
    )

    session.add(new_artifact)
    await session.commit()
    await session.refresh(new_artifact)

    logger.info(
        "Created artifact version",
        extra={
            "artifact_id": str(new_artifact.id),
            "parent_id": str(parent.id),
            "version": new_version,
            "task_id": str(task_id),
        },
    )

    return ArtifactDetailResponse(
        id=str(new_artifact.id),
        task_id=str(new_artifact.task_id),
        artifact_type=new_artifact.artifact_type,
        name=new_artifact.name,
        content=new_artifact.content,
        content_hash=new_artifact.content_hash,
        storage_uri=new_artifact.storage_uri,
        version=new_artifact.version,
        parent_id=str(new_artifact.parent_id) if new_artifact.parent_id else None,
        edit_message=new_artifact.edit_message,
        metadata=new_artifact.metadata_,
        created_at=new_artifact.created_at.isoformat() if new_artifact.created_at else "",
    )
