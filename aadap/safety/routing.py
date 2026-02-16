"""
AADAP — Approval Routing & Escalation
========================================
Determines whether operations should be auto-approved, require human
approval, or escalated based on the Autonomy Policy Matrix and
safety analysis results.

Architecture layer: L5 (Orchestration) — Safety Architecture.
Enforces:
- Autonomy Policy Matrix (SYSTEM_CONSTITUTION.md)
- Timeout escalation

Usage:
    router = ApprovalRouter()
    decision = router.route(operation)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from aadap.core.logging import get_logger
from aadap.safety.approval_engine import (
    ApprovalEngine,
    ApprovalRecord,
    ApprovalStatus,
    OperationRequest,
    _requires_approval,
)
from aadap.safety.static_analysis import RiskLevel

logger = get_logger(__name__)


# ── Routing Action ──────────────────────────────────────────────────────

class RoutingAction(StrEnum):
    """Routing decisions for approval workflow."""

    AUTO_APPROVE = "AUTO_APPROVE"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    ESCALATE = "ESCALATE"


# ── Data Objects ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RoutingDecision:
    """Result of the approval routing logic."""

    action: RoutingAction
    approvers: tuple[str, ...] = ()
    reason: str = ""


@dataclass(frozen=True)
class EscalationRecord:
    """Record of an approval escalation."""

    id: uuid.UUID
    approval_id: uuid.UUID
    reason: str
    escalated_to: tuple[str, ...]
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ── Approval Router ────────────────────────────────────────────────────

class ApprovalRouter:
    """
    Routes approval decisions based on the Autonomy Policy Matrix
    and risk analysis.

    Responsible for determining who should approve and when
    escalation is needed.
    """

    # Default approver groups by risk level
    _DEFAULT_APPROVERS: dict[RiskLevel, tuple[str, ...]] = {
        RiskLevel.NONE: ("team_lead",),
        RiskLevel.LOW: ("team_lead",),
        RiskLevel.MEDIUM: ("team_lead",),
        RiskLevel.HIGH: ("team_lead", "security_admin"),
        RiskLevel.CRITICAL: ("team_lead", "security_admin", "platform_admin"),
    }

    _ESCALATION_TARGETS: tuple[str, ...] = (
        "security_admin",
        "platform_admin",
    )

    def __init__(self) -> None:
        self._escalations: dict[uuid.UUID, EscalationRecord] = {}

    def route(self, operation: OperationRequest) -> RoutingDecision:
        """
        Determine the routing action for an operation.

        Parameters
        ----------
        operation
            The operation to route.

        Returns
        -------
        RoutingDecision
            The routing decision with action and approvers.
        """
        needs_approval = _requires_approval(
            operation.operation_type, operation.environment
        )

        # If the safety pipeline flagged it, require approval
        if (
            operation.pipeline_result is not None
            and operation.pipeline_result.requires_approval
        ):
            needs_approval = True

        if not needs_approval:
            logger.info(
                "approval_router.auto_approve",
                task_id=str(operation.task_id),
                operation_type=operation.operation_type,
                environment=operation.environment,
            )
            return RoutingDecision(
                action=RoutingAction.AUTO_APPROVE,
                reason=(
                    f"Auto-approve per policy: {operation.operation_type} "
                    f"in {operation.environment}"
                ),
            )

        # Determine approvers by risk level
        risk = RiskLevel.NONE
        if operation.pipeline_result is not None:
            risk = operation.pipeline_result.overall_risk

        approvers = self._DEFAULT_APPROVERS.get(risk, ("team_lead",))

        # CRITICAL risk: escalate immediately
        if risk == RiskLevel.CRITICAL:
            logger.warning(
                "approval_router.escalate_critical",
                task_id=str(operation.task_id),
                risk_level=risk.value,
            )
            return RoutingDecision(
                action=RoutingAction.ESCALATE,
                approvers=approvers,
                reason=(
                    f"CRITICAL risk detected: immediate escalation required "
                    f"for {operation.operation_type} in {operation.environment}"
                ),
            )

        logger.info(
            "approval_router.require_approval",
            task_id=str(operation.task_id),
            operation_type=operation.operation_type,
            environment=operation.environment,
            risk_level=risk.value,
            approvers=list(approvers),
        )
        return RoutingDecision(
            action=RoutingAction.REQUIRE_APPROVAL,
            approvers=approvers,
            reason=(
                f"Approval required: {operation.operation_type} "
                f"in {operation.environment} (risk: {risk.value})"
            ),
        )

    def escalate(
        self,
        approval_id: uuid.UUID,
        reason: str,
    ) -> EscalationRecord:
        """
        Escalate a pending approval.

        Parameters
        ----------
        approval_id
            The approval to escalate.
        reason
            Reason for escalation (e.g., timeout, critical risk).

        Returns
        -------
        EscalationRecord
            The escalation record.
        """
        record = EscalationRecord(
            id=uuid.uuid4(),
            approval_id=approval_id,
            reason=reason,
            escalated_to=self._ESCALATION_TARGETS,
        )
        self._escalations[record.id] = record

        logger.warning(
            "approval_router.escalated",
            escalation_id=str(record.id),
            approval_id=str(approval_id),
            reason=reason,
            escalated_to=list(self._ESCALATION_TARGETS),
        )
        return record

    def get_escalation(self, escalation_id: uuid.UUID) -> EscalationRecord:
        """Retrieve an escalation record."""
        record = self._escalations.get(escalation_id)
        if record is None:
            raise KeyError(f"Escalation record {escalation_id} not found.")
        return record
