"""
AADAP — Approval API Tests
=============================
Tests for Phase 7 approval workflow endpoints.

Validates:
- Listing pending approvals
- Approving and rejecting requests
- INV-01 enforcement (destructive ops require approval)
"""

from __future__ import annotations

import uuid

import pytest

from aadap.safety.approval_engine import (
    ApprovalEngine,
    ApprovalRecord,
    ApprovalStatus,
    OperationRequest,
    OperationType,
)


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def approval_engine():
    """Fresh ApprovalEngine for each test."""
    return ApprovalEngine()


@pytest.fixture
def pending_approval(approval_engine):
    """Create a pending approval for a destructive operation."""
    operation = OperationRequest(
        task_id=uuid.uuid4(),
        operation_type=OperationType.DESTRUCTIVE,
        environment="PRODUCTION",
        code="DROP TABLE users;",
        requested_by="agent:developer",
    )
    return approval_engine.request_approval(operation)


# ── List Approvals ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_pending_approvals(client, approval_engine, pending_approval, monkeypatch):
    """GET /api/v1/approvals should return pending approvals."""
    import aadap.api.routes.approvals as approvals_mod
    monkeypatch.setattr(approvals_mod, "_approval_engine", approval_engine)

    response = await client.get("/api/v1/approvals")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["status"] == "PENDING"
    assert data[0]["operation_type"] == "destructive"
    assert data[0]["environment"] == "PRODUCTION"


@pytest.mark.asyncio
async def test_list_approvals_empty(client, monkeypatch):
    """GET /api/v1/approvals with no pending returns empty list."""
    import aadap.api.routes.approvals as approvals_mod
    monkeypatch.setattr(approvals_mod, "_approval_engine", ApprovalEngine())

    response = await client.get("/api/v1/approvals")

    assert response.status_code == 200
    assert response.json() == []


# ── Get Approval ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_approval_detail(client, approval_engine, pending_approval, monkeypatch):
    """GET /api/v1/approvals/{id} should return detail."""
    import aadap.api.routes.approvals as approvals_mod
    monkeypatch.setattr(approvals_mod, "_approval_engine", approval_engine)

    response = await client.get(
        f"/api/v1/approvals/{pending_approval.id}"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(pending_approval.id)
    assert data["status"] == "PENDING"


@pytest.mark.asyncio
async def test_get_approval_not_found(client, monkeypatch):
    """GET /api/v1/approvals/{bad_id} should return 404."""
    import aadap.api.routes.approvals as approvals_mod
    monkeypatch.setattr(approvals_mod, "_approval_engine", ApprovalEngine())

    response = await client.get(
        f"/api/v1/approvals/{uuid.uuid4()}"
    )

    assert response.status_code == 404


# ── Approve ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_approve_pending(client, approval_engine, pending_approval, monkeypatch):
    """POST /api/v1/approvals/{id}/approve should approve a PENDING request."""
    import aadap.api.routes.approvals as approvals_mod
    monkeypatch.setattr(approvals_mod, "_approval_engine", approval_engine)

    response = await client.post(
        f"/api/v1/approvals/{pending_approval.id}/approve",
        json={"reason": "Reviewed and safe."},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "APPROVED"
    assert data["decided_by"] == "system"
    assert data["decision_reason"] == "Reviewed and safe."


@pytest.mark.asyncio
async def test_approve_already_approved(client, approval_engine, pending_approval, monkeypatch):
    """Approving an already-approved request should return 422."""
    import aadap.api.routes.approvals as approvals_mod
    monkeypatch.setattr(approvals_mod, "_approval_engine", approval_engine)

    # First approve
    approval_engine.approve(pending_approval.id, "admin", "OK")

    response = await client.post(
        f"/api/v1/approvals/{pending_approval.id}/approve",
        json={"reason": "Double approve"},
    )

    assert response.status_code == 422


# ── Reject ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reject_pending(client, approval_engine, pending_approval, monkeypatch):
    """POST /api/v1/approvals/{id}/reject should reject a PENDING request."""
    import aadap.api.routes.approvals as approvals_mod
    monkeypatch.setattr(approvals_mod, "_approval_engine", approval_engine)

    response = await client.post(
        f"/api/v1/approvals/{pending_approval.id}/reject",
        json={"reason": "Too risky."},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "REJECTED"
    assert data["decision_reason"] == "Too risky."


# ── INV-01: Destructive Ops Require Approval ───────────────────────────


@pytest.mark.asyncio
async def test_inv01_destructive_ops_pend(approval_engine):
    """
    INV-01: Destructive operations in PRODUCTION must be PENDING,
    never auto-approved.
    """
    operation = OperationRequest(
        task_id=uuid.uuid4(),
        operation_type=OperationType.DESTRUCTIVE,
        environment="PRODUCTION",
        code="DROP TABLE sensitive_data;",
        requested_by="agent:developer",
    )
    record = approval_engine.request_approval(operation)
    assert record.status == ApprovalStatus.PENDING, (
        "INV-01 VIOLATION: Destructive production op was auto-approved!"
    )


@pytest.mark.asyncio
async def test_sandbox_read_auto_approved(approval_engine):
    """Sandbox read-only operations are auto-approved per policy (not bypass)."""
    operation = OperationRequest(
        task_id=uuid.uuid4(),
        operation_type=OperationType.READ_ONLY,
        environment="SANDBOX",
        code="SELECT * FROM table;",
        requested_by="agent:developer",
    )
    record = approval_engine.request_approval(operation)
    assert record.status == ApprovalStatus.APPROVED
    assert record.decided_by == "system:autonomy_policy"
