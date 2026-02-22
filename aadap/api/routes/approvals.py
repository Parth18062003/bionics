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

import inspect
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from aadap.api.deps import get_correlation_id, get_current_user, get_session
from aadap.core.logging import get_logger
from aadap.db.models import ApprovalRequest
from aadap.orchestrator.graph import transition as orchestrator_transition
from aadap.orchestrator.state_machine import InvalidTransitionError
from aadap.safety.approval_engine import (
    ApprovalEngine,
    ApprovalRecord,
    ApprovalRejectedError,
    ApprovalRequiredError,
    ApprovalStatus,
    get_approval_engine as get_shared_approval_engine,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])

# Module-level engine instance (shared with execution service)
_approval_engine = get_shared_approval_engine()


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
    pending = await engine.pending_approvals
    return [_record_to_response(r) for r in pending]


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
        record = await engine.get_record(approval_id)
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
    session: AsyncSession = Depends(get_session),
) -> ApprovalResponse:
    """
    Approve a pending approval request.

    INV-01: This is the only path to unblock destructive operations.
    """
    try:
        record = await engine.approve(
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

    persisted = await _sync_approval_row(
        session=session,
        approval_id=approval_id,
        status="APPROVED",
        decided_by=current_user,
        reason=body.reason,
    )
    if persisted:
        await _advance_task_for_decision(
            task_id=record.task_id,
            approved=True,
            decided_by=current_user,
            reason=body.reason,
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
    session: AsyncSession = Depends(get_session),
) -> ApprovalResponse:
    """
    Reject a pending approval request.

    The associated task execution is halted upon rejection.
    """
    try:
        record = await engine.reject(
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

    persisted = await _sync_approval_row(
        session=session,
        approval_id=approval_id,
        status="REJECTED",
        decided_by=current_user,
        reason=body.reason,
    )
    if persisted:
        await _advance_task_for_decision(
            task_id=record.task_id,
            approved=False,
            decided_by=current_user,
            reason=body.reason,
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
        status=record.status.value if isinstance(
            record.status, ApprovalStatus) else record.status,
        requested_by=record.requested_by,
        decided_by=record.decided_by,
        decision_reason=record.decision_reason,
        risk_level=record.risk_level.value if hasattr(
            record.risk_level, "value") else str(record.risk_level),
        created_at=record.created_at.isoformat() if record.created_at else "",
        decided_at=record.decided_at.isoformat() if record.decided_at else None,
    )


async def _sync_approval_row(
    session: AsyncSession,
    approval_id: uuid.UUID,
    status: str,
    decided_by: str,
    reason: str | None,
) -> bool:
    """Update persisted approval row when present (no-op if not persisted)."""
    result = await session.execute(
        select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
    )
    row_getter = getattr(result, "scalar_one_or_none", None)
    row = row_getter() if callable(row_getter) else None
    if inspect.isawaitable(row):
        row = await row
    if not isinstance(row, ApprovalRequest):
        return False

    await session.execute(
        update(ApprovalRequest)
        .where(ApprovalRequest.id == approval_id)
        .values(
            status=status,
            decided_by=decided_by,
            decision_reason=reason,
        )
    )
    return True


async def _advance_task_for_decision(
    task_id: uuid.UUID,
    approved: bool,
    decided_by: str,
    reason: str | None,
) -> None:
    """Apply approval decision side-effects in task state machine."""
    try:
        await orchestrator_transition(
            task_id=task_id,
            next_state="IN_REVIEW",
            triggered_by=decided_by,
            reason=reason or "Approval decision review step",
        )
    except InvalidTransitionError:
        pass

    final_state = "APPROVED" if approved else "REJECTED"
    try:
        await orchestrator_transition(
            task_id=task_id,
            next_state=final_state,
            triggered_by=decided_by,
            reason=reason or f"Decision: {final_state}",
        )
    except InvalidTransitionError:
        pass
