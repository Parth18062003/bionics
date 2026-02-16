"""
AADAP — Gate 4: Approval Engine
==================================
Approval lifecycle state machine with enforcement of INV-01.

Architecture layer: L5 (Orchestration) — Safety Architecture.
Enforces:
- INV-01: No destructive op executes without explicit human approval
- No safety gate bypass
- Sandbox auto-approval is policy, not bypass

Usage:
    engine = ApprovalEngine()
    record = engine.request_approval(operation)
    engine.approve(record.id, decided_by="admin", reason="Reviewed safe")
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from aadap.core.logging import get_logger
from aadap.safety.semantic_analysis import PipelineResult
from aadap.safety.static_analysis import RiskLevel

logger = get_logger(__name__)


# ── Approval Status ─────────────────────────────────────────────────────

class ApprovalStatus(StrEnum):
    """Approval lifecycle states."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    ESCALATED = "ESCALATED"


# ── Operation Types ─────────────────────────────────────────────────────

class OperationType(StrEnum):
    """Categorization of operations for autonomy policy enforcement."""

    READ_ONLY = "read_only"
    WRITE = "write"
    DESTRUCTIVE = "destructive"
    SCHEMA_CHANGE = "schema_change"
    PERMISSION_CHANGE = "permission_change"


# ── Data Objects ────────────────────────────────────────────────────────

@dataclass
class OperationRequest:
    """A request for an operation that may require approval."""

    task_id: uuid.UUID
    operation_type: str
    environment: str  # "SANDBOX" or "PRODUCTION"
    code: str
    requested_by: str
    pipeline_result: PipelineResult | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ApprovalRecord:
    """Record of an approval decision."""

    id: uuid.UUID
    task_id: uuid.UUID
    operation_type: str
    environment: str
    status: ApprovalStatus
    requested_by: str
    decided_by: str | None = None
    decision_reason: str | None = None
    risk_level: RiskLevel = RiskLevel.NONE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    decided_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Exceptions ──────────────────────────────────────────────────────────

class ApprovalRequiredError(Exception):
    """Raised when an operation requires approval but none has been granted."""

    def __init__(self, operation_type: str, environment: str) -> None:
        self.operation_type = operation_type
        self.environment = environment
        super().__init__(
            f"INV-01: Operation '{operation_type}' in '{environment}' "
            f"requires human approval before execution."
        )


class ApprovalRejectedError(Exception):
    """Raised when an approved operation has been rejected — halts execution."""

    def __init__(self, approval_id: uuid.UUID, reason: str | None) -> None:
        self.approval_id = approval_id
        self.reason = reason
        super().__init__(
            f"Operation rejected (approval {approval_id}): "
            f"{reason or 'No reason given'}. Execution halted."
        )


class ApprovalExpiredError(Exception):
    """Raised when an approval has expired."""

    def __init__(self, approval_id: uuid.UUID) -> None:
        self.approval_id = approval_id
        super().__init__(
            f"Approval {approval_id} has expired. Escalation required."
        )


# ── Autonomy Policy Matrix ─────────────────────────────────────────────
# Source: SYSTEM_CONSTITUTION.md
#
# | Environment | Operation          | Approval Required |
# |-------------|--------------------|--------------------|
# | SANDBOX     | Read-only          | NO                 |
# | SANDBOX     | Write (non-destr.) | NO                 |
# | SANDBOX     | Destructive        | YES                |
# | PRODUCTION  | Read-only          | NO                 |
# | PRODUCTION  | Write              | YES                |
# | PRODUCTION  | Destructive        | YES                |
# | ANY         | Schema change      | YES                |
# | ANY         | Permission change  | YES                |

def _requires_approval(operation_type: str, environment: str) -> bool:
    """
    Check the Autonomy Policy Matrix to determine if approval is required.

    This is the authoritative policy check — not a bypass.
    """
    env = environment.upper()
    op = operation_type.lower()

    # Schema/permission changes always require approval
    if op in ("schema_change", "permission_change"):
        return True

    # Destructive operations always require approval
    if op == "destructive":
        return True

    # Production writes require approval
    if env == "PRODUCTION" and op == "write":
        return True

    # Sandbox reads and non-destructive writes: no approval needed
    # Production reads: no approval needed
    return False


# ── Approval Engine ─────────────────────────────────────────────────────

class ApprovalEngine:
    """
    Gate 4: Human approval lifecycle management.

    Manages the full approval workflow: request, approve, reject,
    expire, and escalate.

    Contract: Sandbox auto-approval is policy, not bypass.
    The safety pipeline (Gates 1–3) is always run first.
    """

    def __init__(self) -> None:
        self._records: dict[uuid.UUID, ApprovalRecord] = {}

    @property
    def pending_approvals(self) -> list[ApprovalRecord]:
        """Return all pending approval records."""
        return [
            r for r in self._records.values()
            if r.status == ApprovalStatus.PENDING
        ]

    def request_approval(
        self,
        operation: OperationRequest,
    ) -> ApprovalRecord:
        """
        Create an approval request for the given operation.

        Checks the Autonomy Policy Matrix. If approval is not required,
        auto-approves (sandbox auto-approval is policy, not bypass).

        Parameters
        ----------
        operation
            The operation to request approval for.

        Returns
        -------
        ApprovalRecord
            The new approval record (PENDING or auto-APPROVED).
        """
        needs_approval = _requires_approval(
            operation.operation_type, operation.environment
        )

        # If the safety pipeline flagged it, always require approval
        if (
            operation.pipeline_result is not None
            and operation.pipeline_result.requires_approval
        ):
            needs_approval = True

        risk_level = RiskLevel.NONE
        if operation.pipeline_result is not None:
            risk_level = operation.pipeline_result.overall_risk

        record = ApprovalRecord(
            id=uuid.uuid4(),
            task_id=operation.task_id,
            operation_type=operation.operation_type,
            environment=operation.environment,
            status=ApprovalStatus.PENDING,
            requested_by=operation.requested_by,
            risk_level=risk_level,
            metadata=operation.metadata,
        )

        if not needs_approval:
            # Auto-approve per policy (still tracked — INV-06 audit)
            record.status = ApprovalStatus.APPROVED
            record.decided_by = "system:autonomy_policy"
            record.decision_reason = (
                f"Auto-approved per Autonomy Policy Matrix: "
                f"{operation.operation_type} in {operation.environment}"
            )
            record.decided_at = datetime.now(timezone.utc)

            logger.info(
                "approval_engine.auto_approved",
                approval_id=str(record.id),
                task_id=str(operation.task_id),
                operation_type=operation.operation_type,
                environment=operation.environment,
            )
        else:
            logger.info(
                "approval_engine.approval_requested",
                approval_id=str(record.id),
                task_id=str(operation.task_id),
                operation_type=operation.operation_type,
                environment=operation.environment,
                risk_level=risk_level.value,
            )

        self._records[record.id] = record
        return record

    def approve(
        self,
        approval_id: uuid.UUID,
        decided_by: str,
        reason: str | None = None,
    ) -> ApprovalRecord:
        """
        Approve a pending approval request.

        Parameters
        ----------
        approval_id
            ID of the approval to approve.
        decided_by
            Identity of the approver.
        reason
            Optional reason for approval.

        Returns
        -------
        ApprovalRecord
            Updated record.

        Raises
        ------
        ValueError
            If the approval is not in PENDING status.
        KeyError
            If the approval ID is not found.
        """
        record = self._get_record(approval_id)
        if record.status != ApprovalStatus.PENDING:
            raise ValueError(
                f"Cannot approve: approval {approval_id} is in "
                f"status {record.status.value}, expected PENDING."
            )

        record.status = ApprovalStatus.APPROVED
        record.decided_by = decided_by
        record.decision_reason = reason
        record.decided_at = datetime.now(timezone.utc)

        logger.info(
            "approval_engine.approved",
            approval_id=str(approval_id),
            decided_by=decided_by,
            reason=reason,
        )
        return record

    def reject(
        self,
        approval_id: uuid.UUID,
        decided_by: str,
        reason: str | None = None,
    ) -> ApprovalRecord:
        """
        Reject a pending approval — halts execution (INV-01).

        Parameters
        ----------
        approval_id
            ID of the approval to reject.
        decided_by
            Identity of the rejector.
        reason
            Optional reason for rejection.

        Returns
        -------
        ApprovalRecord
            Updated record.

        Raises
        ------
        ValueError
            If the approval is not in PENDING status.
        """
        record = self._get_record(approval_id)
        if record.status != ApprovalStatus.PENDING:
            raise ValueError(
                f"Cannot reject: approval {approval_id} is in "
                f"status {record.status.value}, expected PENDING."
            )

        record.status = ApprovalStatus.REJECTED
        record.decided_by = decided_by
        record.decision_reason = reason
        record.decided_at = datetime.now(timezone.utc)

        logger.info(
            "approval_engine.rejected",
            approval_id=str(approval_id),
            decided_by=decided_by,
            reason=reason,
        )
        return record

    def check_expired(
        self,
        approval_id: uuid.UUID,
        timeout_minutes: int = 60,
    ) -> ApprovalRecord | None:
        """
        Check if a pending approval has expired.

        If expired, marks the record as EXPIRED.

        Returns
        -------
        ApprovalRecord or None
            The expired record, or ``None`` if not expired.
        """
        record = self._get_record(approval_id)
        if record.status != ApprovalStatus.PENDING:
            return None

        elapsed = (datetime.now(timezone.utc) - record.created_at).total_seconds()
        if elapsed >= timeout_minutes * 60:
            record.status = ApprovalStatus.EXPIRED
            record.decided_at = datetime.now(timezone.utc)
            record.decision_reason = (
                f"Expired after {timeout_minutes} minutes without decision."
            )

            logger.warning(
                "approval_engine.expired",
                approval_id=str(approval_id),
                elapsed_seconds=int(elapsed),
                timeout_minutes=timeout_minutes,
            )
            return record

        return None

    def get_record(self, approval_id: uuid.UUID) -> ApprovalRecord:
        """Public accessor for a record."""
        return self._get_record(approval_id)

    def enforce_approval(self, approval_id: uuid.UUID) -> None:
        """
        Enforce that the given approval has been granted.

        Raises
        ------
        ApprovalRequiredError
            If the approval is still PENDING.
        ApprovalRejectedError
            If the approval was rejected (halts execution).
        ApprovalExpiredError
            If the approval has expired.
        """
        record = self._get_record(approval_id)

        if record.status == ApprovalStatus.APPROVED:
            return  # Proceed

        if record.status == ApprovalStatus.REJECTED:
            raise ApprovalRejectedError(approval_id, record.decision_reason)

        if record.status == ApprovalStatus.EXPIRED:
            raise ApprovalExpiredError(approval_id)

        if record.status == ApprovalStatus.PENDING:
            raise ApprovalRequiredError(
                record.operation_type, record.environment
            )

        # ESCALATED — also blocks
        raise ApprovalRequiredError(
            record.operation_type, record.environment
        )

    def _get_record(self, approval_id: uuid.UUID) -> ApprovalRecord:
        """Retrieve a record or raise KeyError."""
        record = self._records.get(approval_id)
        if record is None:
            raise KeyError(f"Approval record {approval_id} not found.")
        return record
