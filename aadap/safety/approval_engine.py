"""
AADAP — Gate 4: Approval Engine
==================================
Approval lifecycle state machine with enforcement of INV-01.

Architecture layer: L5 (Orchestration) — Safety Architecture.
Enforces:
- INV-01: No destructive op executes without explicit human approval
- No safety gate bypass
- Sandbox auto-approval is policy, not bypass
- Persistence: All approval records stored in database

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
from typing import Any, Callable

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from aadap.core.logging import get_logger
from aadap.db.models import ApprovalRequest
from aadap.db.session import get_db_session
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
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc))
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
    expire, and escalate. All records are persisted to database.

    Contract: Sandbox auto-approval is policy, not bypass.
    The safety pipeline (Gates 1–3) is always run first.
    """

    def __init__(self, session_factory: Callable[..., Any] | None = None) -> None:
        """
        Initialize the approval engine.

        Parameters
        ----------
        session_factory
            Async context manager that yields an AsyncSession.
            Defaults to get_db_session.
        """
        self._session_factory = session_factory or get_db_session
        # In-memory cache for fallback when database is unavailable
        self._memory_cache: dict[uuid.UUID, ApprovalRecord] = {}

    @property
    async def pending_approvals(self) -> list[ApprovalRecord]:
        """Return all pending approval records from database."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(ApprovalRequest).where(
                    ApprovalRequest.status == ApprovalStatus.PENDING.value
                )
            )
            requests = result.scalars().all()
            return [self._to_record(r) for r in requests]

    def _to_record(self, req: ApprovalRequest) -> ApprovalRecord:
        """Convert database model to ApprovalRecord."""
        return ApprovalRecord(
            id=req.id,
            task_id=req.task_id,
            operation_type=req.operation_type,
            environment=req.environment,
            status=ApprovalStatus(req.status),
            requested_by=req.requested_by or "",
            decided_by=req.decided_by,
            decision_reason=req.decision_reason,
            risk_level=RiskLevel(req.risk_level) if req.risk_level else RiskLevel.NONE,
            created_at=req.created_at,
            decided_at=req.decided_at,
            metadata=req.metadata_ or {},
        )

    async def request_approval_async(
        self,
        operation: OperationRequest,
    ) -> ApprovalRecord:
        """
        Create an approval request for the given operation.

        Checks the Autonomy Policy Matrix. If approval is not required,
        auto-approves (sandbox auto-approval is policy, not bypass).

        Persists to database asynchronously.

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

        # Persist to database
        await self._persist_record(record)

        return record

    def request_approval(
        self,
        operation: OperationRequest,
    ) -> ApprovalRecord:
        """
        Sync wrapper for request_approval_async.

        Creates an approval request for the given operation. This method
        handles the async execution internally for backwards compatibility.
        """
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # We're in an async context, but this sync method was called
            # Run in a new thread to avoid blocking
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self.request_approval_async(operation)
                )
                return future.result()
        else:
            # We're in a sync context, run async
            return asyncio.run(self.request_approval_async(operation))

    async def _persist_record(self, record: ApprovalRecord) -> None:
        """Persist an approval record to the database and memory cache."""
        # Always store in memory cache for fallback
        self._memory_cache[record.id] = record

        try:
            async with self._session_factory() as session:
                approval = ApprovalRequest(
                    id=record.id,
                    task_id=record.task_id,
                    operation_type=record.operation_type,
                    environment=record.environment,
                    status=record.status.value,
                    requested_by=record.requested_by,
                    decided_by=record.decided_by,
                    decision_reason=record.decision_reason,
                    risk_level=record.risk_level.value,
                    created_at=record.created_at,
                    decided_at=record.decided_at,
                    metadata_=record.metadata,
                )
                session.add(approval)
        except RuntimeError as e:
            if "Database not initialized" in str(e):
                logger.debug(
                    "approval_engine.using_memory_cache",
                    approval_id=str(record.id),
                )
            else:
                raise

    async def approve(
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
        # Get current record (from cache or database)
        record = await self._get_record(approval_id)

        if record.status != ApprovalStatus.PENDING:
            raise ValueError(
                f"Cannot approve: approval {approval_id} is in "
                f"status {record.status.value}, expected PENDING."
            )

        now = datetime.now(timezone.utc)
        updated_record = ApprovalRecord(
            id=record.id,
            task_id=record.task_id,
            operation_type=record.operation_type,
            environment=record.environment,
            status=ApprovalStatus.APPROVED,
            requested_by=record.requested_by,
            decided_by=decided_by,
            decision_reason=reason,
            risk_level=record.risk_level,
            created_at=record.created_at,
            decided_at=now,
            metadata=record.metadata,
        )

        # Update memory cache
        self._memory_cache[approval_id] = updated_record

        # Try to update database
        try:
            async with self._session_factory() as session:
                await session.execute(
                    update(ApprovalRequest)
                    .where(ApprovalRequest.id == approval_id)
                    .values(
                        status=ApprovalStatus.APPROVED.value,
                        decided_by=decided_by,
                        decision_reason=reason,
                        decided_at=now,
                    )
                )
        except RuntimeError as e:
            if "Database not initialized" not in str(e):
                raise

        logger.info(
            "approval_engine.approved",
            approval_id=str(approval_id),
            decided_by=decided_by,
            reason=reason,
        )

        return updated_record

    async def reject(
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
        # Get current record (from cache or database)
        record = await self._get_record(approval_id)

        if record.status != ApprovalStatus.PENDING:
            raise ValueError(
                f"Cannot reject: approval {approval_id} is in "
                f"status {record.status.value}, expected PENDING."
            )

        now = datetime.now(timezone.utc)
        updated_record = ApprovalRecord(
            id=record.id,
            task_id=record.task_id,
            operation_type=record.operation_type,
            environment=record.environment,
            status=ApprovalStatus.REJECTED,
            requested_by=record.requested_by,
            decided_by=decided_by,
            decision_reason=reason,
            risk_level=record.risk_level,
            created_at=record.created_at,
            decided_at=now,
            metadata=record.metadata,
        )

        # Update memory cache
        self._memory_cache[approval_id] = updated_record

        # Try to update database
        try:
            async with self._session_factory() as session:
                await session.execute(
                    update(ApprovalRequest)
                    .where(ApprovalRequest.id == approval_id)
                    .values(
                        status=ApprovalStatus.REJECTED.value,
                        decided_by=decided_by,
                        decision_reason=reason,
                        decided_at=now,
                    )
                )
        except RuntimeError as e:
            if "Database not initialized" not in str(e):
                raise

        logger.info(
            "approval_engine.rejected",
            approval_id=str(approval_id),
            decided_by=decided_by,
            reason=reason,
        )

        return updated_record

    async def check_expired(
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
        # Get current record (from cache or database)
        record = await self._get_record(approval_id)

        if record.status != ApprovalStatus.PENDING:
            return None

        elapsed = (datetime.now(timezone.utc) - record.created_at).total_seconds()
        if elapsed >= timeout_minutes * 60:
            now = datetime.now(timezone.utc)
            updated_record = ApprovalRecord(
                id=record.id,
                task_id=record.task_id,
                operation_type=record.operation_type,
                environment=record.environment,
                status=ApprovalStatus.EXPIRED,
                requested_by=record.requested_by,
                decision_reason=f"Expired after {timeout_minutes} minutes without decision.",
                risk_level=record.risk_level,
                created_at=record.created_at,
                decided_at=now,
                metadata=record.metadata,
            )

            # Update memory cache
            self._memory_cache[approval_id] = updated_record

            # Try to update database
            try:
                async with self._session_factory() as session:
                    await session.execute(
                        update(ApprovalRequest)
                        .where(ApprovalRequest.id == approval_id)
                        .values(
                            status=ApprovalStatus.EXPIRED.value,
                            decided_at=now,
                            decision_reason=(
                                f"Expired after {timeout_minutes} minutes without decision."
                            ),
                        )
                    )
            except RuntimeError as e:
                if "Database not initialized" not in str(e):
                    raise

            logger.warning(
                "approval_engine.expired",
                approval_id=str(approval_id),
                elapsed_seconds=int(elapsed),
                timeout_minutes=timeout_minutes,
            )

            return updated_record

        return None

    async def get_record(self, approval_id: uuid.UUID) -> ApprovalRecord:
        """Public accessor for a record from database."""
        return await self._get_record(approval_id)

    async def enforce_approval(self, approval_id: uuid.UUID) -> None:
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
        record = await self._get_record(approval_id)

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

    async def _get_record(self, approval_id: uuid.UUID) -> ApprovalRecord:
        """Retrieve a record from memory cache or database."""
        # Check memory cache first
        if approval_id in self._memory_cache:
            return self._memory_cache[approval_id]

        try:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
                )
                req = result.scalar_one_or_none()
                if req is None:
                    raise KeyError(f"Approval record {approval_id} not found.")
                record = self._to_record(req)
                # Cache for future lookups
                self._memory_cache[approval_id] = record
                return record
        except RuntimeError as e:
            if "Database not initialized" in str(e):
                raise KeyError(f"Approval record {approval_id} not found (database not initialized).")
            raise

    # ── Sync wrappers for backwards compatibility ───────────────────────────

    def approve_sync(
        self,
        approval_id: uuid.UUID,
        decided_by: str,
        reason: str | None = None,
    ) -> ApprovalRecord:
        """Sync wrapper for approve()."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self.approve(approval_id, decided_by, reason)
                )
                return future.result()
        else:
            return asyncio.run(self.approve(approval_id, decided_by, reason))

    def reject_sync(
        self,
        approval_id: uuid.UUID,
        decided_by: str,
        reason: str | None = None,
    ) -> ApprovalRecord:
        """Sync wrapper for reject()."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self.reject(approval_id, decided_by, reason)
                )
                return future.result()
        else:
            return asyncio.run(self.reject(approval_id, decided_by, reason))

    def check_expired_sync(
        self,
        approval_id: uuid.UUID,
        timeout_minutes: int = 60,
    ) -> ApprovalRecord | None:
        """Sync wrapper for check_expired()."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self.check_expired(approval_id, timeout_minutes)
                )
                return future.result()
        else:
            return asyncio.run(self.check_expired(approval_id, timeout_minutes))

    def get_record_sync(self, approval_id: uuid.UUID) -> ApprovalRecord:
        """Sync wrapper for get_record()."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self.get_record(approval_id)
                )
                return future.result()
        else:
            return asyncio.run(self.get_record(approval_id))

    def enforce_approval_sync(self, approval_id: uuid.UUID) -> None:
        """Sync wrapper for enforce_approval()."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self.enforce_approval(approval_id)
                )
                return future.result()
        else:
            return asyncio.run(self.enforce_approval(approval_id))


# Module-level singleton for backwards compatibility
_GLOBAL_APPROVAL_ENGINE: ApprovalEngine | None = None


def get_approval_engine() -> ApprovalEngine:
    """Return the shared process-level approval engine instance."""
    global _GLOBAL_APPROVAL_ENGINE
    if _GLOBAL_APPROVAL_ENGINE is None:
        _GLOBAL_APPROVAL_ENGINE = ApprovalEngine()
    return _GLOBAL_APPROVAL_ENGINE
