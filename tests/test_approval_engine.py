"""
AADAP — Gate 4: Approval Engine Tests
========================================
Phase 5 required tests: Approval enforcement, rejection halts, timeout escalation.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from aadap.safety.approval_engine import (
    ApprovalEngine,
    ApprovalExpiredError,
    ApprovalRecord,
    ApprovalRejectedError,
    ApprovalRequiredError,
    ApprovalStatus,
    OperationRequest,
)
from aadap.safety.semantic_analysis import PipelineResult, SafetyPipeline
from aadap.safety.static_analysis import RiskLevel


@pytest.fixture
def engine() -> ApprovalEngine:
    return ApprovalEngine()


@pytest.fixture
def pipeline() -> SafetyPipeline:
    return SafetyPipeline()


def _make_operation(
    operation_type: str = "write",
    environment: str = "PRODUCTION",
    code: str = "UPDATE users SET active = false;",
    pipeline_result: PipelineResult | None = None,
) -> OperationRequest:
    return OperationRequest(
        task_id=uuid.uuid4(),
        operation_type=operation_type,
        environment=environment,
        code=code,
        requested_by="developer@test.com",
        pipeline_result=pipeline_result,
    )


# ── Approval Enforcement (INV-01) ──────────────────────────────────────


class TestApprovalEnforcement:
    """Definition of Done: Production write requires approval."""

    def test_production_write_requires_approval(
        self, engine: ApprovalEngine
    ) -> None:
        """INV-01: Production write must create a PENDING request."""
        op = _make_operation(
            operation_type="write", environment="PRODUCTION"
        )
        record = engine.request_approval(op)
        assert record.status == ApprovalStatus.PENDING
        assert record.operation_type == "write"
        assert record.environment == "PRODUCTION"

    def test_production_destructive_requires_approval(
        self, engine: ApprovalEngine
    ) -> None:
        op = _make_operation(
            operation_type="destructive", environment="PRODUCTION"
        )
        record = engine.request_approval(op)
        assert record.status == ApprovalStatus.PENDING

    def test_sandbox_destructive_requires_approval(
        self, engine: ApprovalEngine
    ) -> None:
        """Even sandbox destructive ops require approval (Autonomy Matrix)."""
        op = _make_operation(
            operation_type="destructive", environment="SANDBOX"
        )
        record = engine.request_approval(op)
        assert record.status == ApprovalStatus.PENDING

    def test_schema_change_requires_approval(
        self, engine: ApprovalEngine
    ) -> None:
        op = _make_operation(
            operation_type="schema_change", environment="SANDBOX"
        )
        record = engine.request_approval(op)
        assert record.status == ApprovalStatus.PENDING

    def test_permission_change_requires_approval(
        self, engine: ApprovalEngine
    ) -> None:
        op = _make_operation(
            operation_type="permission_change", environment="SANDBOX"
        )
        record = engine.request_approval(op)
        assert record.status == ApprovalStatus.PENDING

    def test_enforce_pending_raises(self, engine: ApprovalEngine) -> None:
        """Cannot execute while approval is pending."""
        op = _make_operation(
            operation_type="write", environment="PRODUCTION"
        )
        record = engine.request_approval(op)
        with pytest.raises(ApprovalRequiredError):
            engine.enforce_approval_sync(record.id)


# ── Auto-Approval (Policy, Not Bypass) ──────────────────────────────────


class TestAutoApproval:
    """Sandbox auto-approval is policy, not bypass."""

    def test_sandbox_read_auto_approved(
        self, engine: ApprovalEngine
    ) -> None:
        op = _make_operation(
            operation_type="read_only", environment="SANDBOX"
        )
        record = engine.request_approval(op)
        assert record.status == ApprovalStatus.APPROVED
        assert record.decided_by == "system:autonomy_policy"

    def test_sandbox_write_auto_approved(
        self, engine: ApprovalEngine
    ) -> None:
        op = _make_operation(
            operation_type="write", environment="SANDBOX"
        )
        record = engine.request_approval(op)
        assert record.status == ApprovalStatus.APPROVED

    def test_production_read_auto_approved(
        self, engine: ApprovalEngine
    ) -> None:
        op = _make_operation(
            operation_type="read_only", environment="PRODUCTION"
        )
        record = engine.request_approval(op)
        assert record.status == ApprovalStatus.APPROVED

    def test_auto_approved_still_recorded(
        self, engine: ApprovalEngine
    ) -> None:
        """Auto-approvals must be tracked for audit (INV-06)."""
        op = _make_operation(
            operation_type="read_only", environment="SANDBOX"
        )
        record = engine.request_approval(op)
        assert record.decided_at is not None
        assert record.decision_reason is not None

    def test_pipeline_override_auto_approval(
        self, engine: ApprovalEngine, pipeline: SafetyPipeline
    ) -> None:
        """If safety pipeline flags HIGH/CRITICAL, override auto-approval."""
        pipeline_result = pipeline.evaluate("DROP TABLE users;", "sql")
        op = _make_operation(
            operation_type="write",
            environment="SANDBOX",
            code="DROP TABLE users;",
            pipeline_result=pipeline_result,
        )
        record = engine.request_approval(op)
        # Pipeline flagged CRITICAL → must not auto-approve
        assert record.status == ApprovalStatus.PENDING


# ── Rejection Halts Execution ──────────────────────────────────────────


class TestRejection:
    """Definition of Done: Rejection halts execution."""

    def test_rejection_halts_execution(self, engine: ApprovalEngine) -> None:
        """INV-01: Rejected operation must raise ApprovalRejectedError."""
        op = _make_operation(
            operation_type="write", environment="PRODUCTION"
        )
        record = engine.request_approval(op)

        rejected_record = engine.reject_sync(record.id, decided_by="admin", reason="Unsafe operation")
        assert rejected_record.status == ApprovalStatus.REJECTED

        with pytest.raises(ApprovalRejectedError) as exc_info:
            engine.enforce_approval_sync(record.id)
        assert "Unsafe operation" in str(exc_info.value)

    def test_reject_non_pending_raises(self, engine: ApprovalEngine) -> None:
        op = _make_operation(
            operation_type="read_only", environment="SANDBOX"
        )
        record = engine.request_approval(op)  # auto-approved
        with pytest.raises(ValueError, match="expected PENDING"):
            engine.reject_sync(record.id, decided_by="admin")


# ── Approval Flow ──────────────────────────────────────────────────────


class TestApprovalFlow:
    def test_approve_then_enforce(self, engine: ApprovalEngine) -> None:
        op = _make_operation(
            operation_type="write", environment="PRODUCTION"
        )
        record = engine.request_approval(op)
        approved_record = engine.approve_sync(record.id, decided_by="admin", reason="Reviewed safe")

        assert approved_record.status == ApprovalStatus.APPROVED
        assert approved_record.decided_by == "admin"
        assert approved_record.decided_at is not None

        # enforce_approval should not raise
        engine.enforce_approval_sync(record.id)

    def test_approve_non_pending_raises(self, engine: ApprovalEngine) -> None:
        op = _make_operation(
            operation_type="read_only", environment="SANDBOX"
        )
        record = engine.request_approval(op)  # auto-approved
        with pytest.raises(ValueError, match="expected PENDING"):
            engine.approve_sync(record.id, decided_by="admin")


# ── Timeout Escalation ──────────────────────────────────────────────────


class TestTimeoutEscalation:
    """Phase 5 required test: Timeout escalation."""

    def test_not_expired_within_timeout(
        self, engine: ApprovalEngine
    ) -> None:
        op = _make_operation(
            operation_type="write", environment="PRODUCTION"
        )
        record = engine.request_approval(op)
        result = engine.check_expired_sync(record.id, timeout_minutes=60)
        assert result is None

    def test_expired_after_timeout(self, engine: ApprovalEngine) -> None:
        op = _make_operation(
            operation_type="write", environment="PRODUCTION"
        )
        record = engine.request_approval(op)

        # Simulate time passage
        record.created_at = datetime.now(timezone.utc) - timedelta(minutes=61)

        expired = engine.check_expired_sync(record.id, timeout_minutes=60)
        assert expired is not None
        assert expired.status == ApprovalStatus.EXPIRED

    def test_enforce_expired_raises(self, engine: ApprovalEngine) -> None:
        op = _make_operation(
            operation_type="write", environment="PRODUCTION"
        )
        record = engine.request_approval(op)
        record.created_at = datetime.now(timezone.utc) - timedelta(minutes=61)
        engine.check_expired_sync(record.id, timeout_minutes=60)

        with pytest.raises(ApprovalExpiredError):
            engine.enforce_approval_sync(record.id)


# ── Pending Approvals ──────────────────────────────────────────────────


class TestPendingApprovals:
    def test_pending_approvals_list(self, engine: ApprovalEngine) -> None:
        op1 = _make_operation(
            operation_type="write", environment="PRODUCTION"
        )
        op2 = _make_operation(
            operation_type="destructive", environment="PRODUCTION"
        )
        engine.request_approval(op1)
        engine.request_approval(op2)
        # Note: pending_approvals property is async, use sync access via memory cache
        # For tests, we verify the records exist in memory
        assert engine._memory_cache  # Records should be in cache

    def test_record_lookup(self, engine: ApprovalEngine) -> None:
        op = _make_operation(
            operation_type="write", environment="PRODUCTION"
        )
        record = engine.request_approval(op)
        fetched = engine.get_record_sync(record.id)
        assert fetched.id == record.id

    def test_record_not_found(self, engine: ApprovalEngine) -> None:
        with pytest.raises(KeyError):
            engine.get_record_sync(uuid.uuid4())
