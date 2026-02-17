"""
AADAP — Approval API Routes
===============================
REST endpoints for the approval workflow.

Architecture layer: L6 (Presentation).
Phase 7 contract: Approval UI.

Invariant enforcement:
- INV-01: No destructive op executes without explicit human approval
         (approval status is enforced by ``ApprovalEngine.enforce_approval``)
- INV-09: DecisionExplanation artifact checked before approval transitions
- INV-06: All approval decisions are audit-logged

Usage:
    GET    /api/v1/approvals                      — List pending
    GET    /api/v1/approvals/{approval_id}        — Detail
    POST   /api/v1/approvals/{approval_id}/approve — Approve
    POST   /api/v1/approvals/{approval_id}/reject  — Reject
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from aadap.api.deps import get_correlation_id, get_current_user
from aadap.core.logging import get_logger
from aadap.safety.approval_engine import (
    ApprovalEngine,
    ApprovalRecord,
    ApprovalRejectedError,
    ApprovalRequiredError,
    ApprovalStatus,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])

# Module-level engine instance (in production, backed by DB)
_approval_engine = ApprovalEngine()


def get_approval_engine() -> ApprovalEngine:
    """Return the module-level ApprovalEngine. Swappable in tests."""
    return _approval_engine


# ── Request / Response Schemas ──────────────────────────────────────────


class ApprovalResponse(BaseModel):
    """Approval record returned by the API."""

    id: str
    task_id: str
    operation_type: str
    environment: str
    status: str
    requested_by: str
    decided_by: str | None
    decision_reason: str | None
    risk_level: str
    created_at: str
    decided_at: str | None


class ApprovalDecisionRequest(BaseModel):
    """Request body for approve/reject actions."""

    reason: str | None = Field(
        None, description="Optional reason for the decision."
    )


# ── Endpoints ───────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=list[ApprovalResponse],
    summary="List pending approvals",
)
async def list_pending_approvals(
    engine: ApprovalEngine = Depends(get_approval_engine),
) -> list[ApprovalResponse]:
    """Return all pending approval requests."""
    return [_record_to_response(r) for r in engine.pending_approvals]


@router.get(
    "/{approval_id}",
    response_model=ApprovalResponse,
    summary="Get approval detail",
)
async def get_approval(
    approval_id: uuid.UUID,
    engine: ApprovalEngine = Depends(get_approval_engine),
) -> ApprovalResponse:
    """Get a single approval record by ID."""
    try:
        record = engine.get_record(approval_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Approval not found.")
    return _record_to_response(record)


@router.post(
    "/{approval_id}/approve",
    response_model=ApprovalResponse,
    summary="Approve a pending request",
    description="Approves a pending request. INV-01 enforced — destructive ops require this.",
)
async def approve(
    approval_id: uuid.UUID,
    body: ApprovalDecisionRequest,
    engine: ApprovalEngine = Depends(get_approval_engine),
    current_user: str = Depends(get_current_user),
    correlation_id: str | None = Depends(get_correlation_id),
) -> ApprovalResponse:
    """
    Approve a pending approval request.

    INV-01: This is the only path to unblock destructive operations.
    """
    try:
        record = engine.approve(
            approval_id=approval_id,
            decided_by=current_user,
            reason=body.reason,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Approval not found.")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    logger.info(
        "api.approval.approved",
        approval_id=str(approval_id),
        decided_by=current_user,
        correlation_id=correlation_id,
    )
    return _record_to_response(record)


@router.post(
    "/{approval_id}/reject",
    response_model=ApprovalResponse,
    summary="Reject a pending request",
    description="Rejects a pending request. Halts execution (INV-01).",
)
async def reject(
    approval_id: uuid.UUID,
    body: ApprovalDecisionRequest,
    engine: ApprovalEngine = Depends(get_approval_engine),
    current_user: str = Depends(get_current_user),
    correlation_id: str | None = Depends(get_correlation_id),
) -> ApprovalResponse:
    """
    Reject a pending approval request.

    The associated task execution is halted upon rejection.
    """
    try:
        record = engine.reject(
            approval_id=approval_id,
            decided_by=current_user,
            reason=body.reason,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Approval not found.")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    logger.info(
        "api.approval.rejected",
        approval_id=str(approval_id),
        decided_by=current_user,
        correlation_id=correlation_id,
    )
    return _record_to_response(record)


# ── Helpers ─────────────────────────────────────────────────────────────


def _record_to_response(record: ApprovalRecord) -> ApprovalResponse:
    """Convert an ApprovalRecord to an API response."""
    return ApprovalResponse(
        id=str(record.id),
        task_id=str(record.task_id),
        operation_type=record.operation_type,
        environment=record.environment,
        status=record.status.value if isinstance(record.status, ApprovalStatus) else record.status,
        requested_by=record.requested_by,
        decided_by=record.decided_by,
        decision_reason=record.decision_reason,
        risk_level=record.risk_level.value if hasattr(record.risk_level, "value") else str(record.risk_level),
        created_at=record.created_at.isoformat() if record.created_at else "",
        decided_at=record.decided_at.isoformat() if record.decided_at else None,
    )
