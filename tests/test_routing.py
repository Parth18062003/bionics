"""
AADAP — Approval Routing & Escalation Tests
===============================================
Phase 5 tests for routing and escalation logic.
"""

from __future__ import annotations

import uuid

import pytest

from aadap.safety.approval_engine import OperationRequest
from aadap.safety.routing import (
    ApprovalRouter,
    EscalationRecord,
    RoutingAction,
    RoutingDecision,
)
from aadap.safety.semantic_analysis import PipelineResult, SafetyPipeline
from aadap.safety.static_analysis import RiskLevel, RiskResult


@pytest.fixture
def router() -> ApprovalRouter:
    return ApprovalRouter()


@pytest.fixture
def pipeline() -> SafetyPipeline:
    return SafetyPipeline()


def _make_operation(
    operation_type: str = "write",
    environment: str = "PRODUCTION",
    pipeline_result: PipelineResult | None = None,
) -> OperationRequest:
    return OperationRequest(
        task_id=uuid.uuid4(),
        operation_type=operation_type,
        environment=environment,
        code="SELECT 1;",
        requested_by="developer@test.com",
        pipeline_result=pipeline_result,
    )


# ── Routing Decisions ──────────────────────────────────────────────────


class TestRoutingDecisions:
    def test_sandbox_read_auto_approve(self, router: ApprovalRouter) -> None:
        op = _make_operation(
            operation_type="read_only", environment="SANDBOX"
        )
        decision = router.route(op)
        assert decision.action == RoutingAction.AUTO_APPROVE

    def test_sandbox_write_auto_approve(self, router: ApprovalRouter) -> None:
        op = _make_operation(
            operation_type="write", environment="SANDBOX"
        )
        decision = router.route(op)
        assert decision.action == RoutingAction.AUTO_APPROVE

    def test_production_read_auto_approve(self, router: ApprovalRouter) -> None:
        op = _make_operation(
            operation_type="read_only", environment="PRODUCTION"
        )
        decision = router.route(op)
        assert decision.action == RoutingAction.AUTO_APPROVE

    def test_production_write_requires_approval(
        self, router: ApprovalRouter
    ) -> None:
        op = _make_operation(
            operation_type="write", environment="PRODUCTION"
        )
        decision = router.route(op)
        assert decision.action == RoutingAction.REQUIRE_APPROVAL
        assert len(decision.approvers) > 0

    def test_destructive_requires_approval(
        self, router: ApprovalRouter
    ) -> None:
        op = _make_operation(
            operation_type="destructive", environment="SANDBOX"
        )
        decision = router.route(op)
        assert decision.action == RoutingAction.REQUIRE_APPROVAL

    def test_schema_change_requires_approval(
        self, router: ApprovalRouter
    ) -> None:
        op = _make_operation(
            operation_type="schema_change", environment="SANDBOX"
        )
        decision = router.route(op)
        assert decision.action == RoutingAction.REQUIRE_APPROVAL

    def test_permission_change_requires_approval(
        self, router: ApprovalRouter
    ) -> None:
        op = _make_operation(
            operation_type="permission_change", environment="PRODUCTION"
        )
        decision = router.route(op)
        assert decision.action == RoutingAction.REQUIRE_APPROVAL


# ── Risk-Based Approvers ───────────────────────────────────────────────


class TestRiskBasedApprovers:
    def test_high_risk_includes_security_admin(
        self, router: ApprovalRouter, pipeline: SafetyPipeline
    ) -> None:
        result = pipeline.evaluate("DELETE FROM users WHERE 1=1;", "sql")
        op = _make_operation(
            operation_type="write",
            environment="PRODUCTION",
            pipeline_result=result,
        )
        decision = router.route(op)
        assert "security_admin" in decision.approvers

    def test_critical_risk_escalates(
        self, router: ApprovalRouter, pipeline: SafetyPipeline
    ) -> None:
        result = pipeline.evaluate("DROP TABLE users;", "sql")
        op = _make_operation(
            operation_type="destructive",
            environment="PRODUCTION",
            pipeline_result=result,
        )
        decision = router.route(op)
        assert decision.action == RoutingAction.ESCALATE
        assert "platform_admin" in decision.approvers


# ── Escalation ─────────────────────────────────────────────────────────


class TestEscalation:
    def test_escalate_creates_record(self, router: ApprovalRouter) -> None:
        approval_id = uuid.uuid4()
        record = router.escalate(approval_id, reason="Timeout after 60 minutes")
        assert isinstance(record, EscalationRecord)
        assert record.approval_id == approval_id
        assert "Timeout" in record.reason
        assert len(record.escalated_to) > 0

    def test_escalation_lookup(self, router: ApprovalRouter) -> None:
        approval_id = uuid.uuid4()
        record = router.escalate(approval_id, reason="Test")
        fetched = router.get_escalation(record.id)
        assert fetched.id == record.id

    def test_escalation_not_found(self, router: ApprovalRouter) -> None:
        with pytest.raises(KeyError):
            router.get_escalation(uuid.uuid4())

    def test_routing_decision_has_reason(self, router: ApprovalRouter) -> None:
        op = _make_operation(
            operation_type="write", environment="PRODUCTION"
        )
        decision = router.route(op)
        assert len(decision.reason) > 0
