"""
AADAP — SQLAlchemy Models
==========================
Core entity tables as defined in DATA_AND_STATE.md.

Entities: Task, StateTransition, Artifact, ApprovalRequest, Execution, AuditEvent.

Design decisions:
- JSONB ``metadata`` columns for forward-compatible extensibility (Risk R6).
- pgvector extension created for Phase 6 readiness (Risk R2).
- All timestamps are UTC with timezone.
- StateTransition is append-only / immutable (event sourcing).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ── Authoritative Task States (ARCHITECTURE.md §Task State Machine) ────
# 25 authoritative states.  START / END are implicit non-states.
TASK_STATES: list[str] = [
    "SUBMITTED",
    "PARSING",
    "PARSED",
    "PARSE_FAILED",
    "PLANNING",
    "PLANNED",
    "AGENT_ASSIGNMENT",
    "AGENT_ASSIGNED",
    "IN_DEVELOPMENT",
    "CODE_GENERATED",
    "DEV_FAILED",
    "IN_VALIDATION",
    "VALIDATION_PASSED",
    "VALIDATION_FAILED",
    "OPTIMIZATION_PENDING",
    "IN_OPTIMIZATION",
    "OPTIMIZED",
    "APPROVAL_PENDING",
    "IN_REVIEW",
    "APPROVED",
    "REJECTED",
    "DEPLOYING",
    "DEPLOYED",
    "COMPLETED",
    "CANCELLED",
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Shared declarative base for all AADAP models."""
    pass


# ── Task ────────────────────────────────────────────────────────────────

class Task(Base):
    """
    Primary work unit.  Lifecycle governed by the 25-state machine.

    Owner: Phase 2 (Orchestration Engine) consumes; Phase 1 defines schema.
    """

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_state: Mapped[str] = mapped_column(
        String(64), nullable=False, default="SUBMITTED"
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    environment: Mapped[str] = mapped_column(
        String(32), nullable=False, default="SANDBOX"
    )
    created_by: Mapped[str | None] = mapped_column(String(256), nullable=True)
    token_budget: Mapped[int] = mapped_column(
        Integer, nullable=False, default=50_000,
        comment="INV-04: Token budget per task (default 50,000)",
    )
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="INV-03: bounded self-correction, max 3",
    )
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True, default=dict,
        comment="Forward-compatible extensible fields",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    transitions: Mapped[list["StateTransition"]] = relationship(
        back_populates="task", order_by="StateTransition.sequence_num"
    )
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="task")
    approval_requests: Mapped[list["ApprovalRequest"]] = relationship(
        back_populates="task"
    )
    executions: Mapped[list["Execution"]] = relationship(back_populates="task")

    __table_args__ = (
        Index("ix_tasks_current_state", "current_state"),
        Index("ix_tasks_priority", "priority"),
        Index("ix_tasks_created_at", "created_at"),
    )


# ── StateTransition (Event Sourcing) ────────────────────────────────────

class StateTransition(Base):
    """
    Immutable event record.  Append-only — enforces INV-02.

    Each row captures a single state change.  The full task history
    can be replayed by reading transitions in sequence_num order.
    """

    __tablename__ = "state_transitions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    from_state: Mapped[str] = mapped_column(String(64), nullable=False)
    to_state: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence_num: Mapped[int] = mapped_column(Integer, nullable=False)
    triggered_by: Mapped[str | None] = mapped_column(
        String(256), nullable=True, comment="agent id, user email, or system"
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    task: Mapped["Task"] = relationship(back_populates="transitions")

    __table_args__ = (
        Index("ix_st_task_id_seq", "task_id", "sequence_num", unique=True),
        Index("ix_st_created_at", "created_at"),
    )


# ── Artifact ────────────────────────────────────────────────────────────

class Artifact(Base):
    """
    Code, config, or document produced during task execution.

    INV-09: Approval-required transitions must produce a
    DecisionExplanation artifact.
    """

    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    artifact_type: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="e.g. code, config, decision_explanation, report",
    )
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="SHA-256 of content for integrity"
    )
    storage_uri: Mapped[str | None] = mapped_column(
        String(1024), nullable=True,
        comment="Blob storage URI for large artifacts (Tier 3)",
    )
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    task: Mapped["Task"] = relationship(back_populates="artifacts")

    __table_args__ = (
        Index("ix_artifacts_task_id", "task_id"),
        Index("ix_artifacts_type", "artifact_type"),
    )


# ── ApprovalRequest ─────────────────────────────────────────────────────

class ApprovalRequest(Base):
    """
    Human-in-the-loop decision point.

    INV-01: No destructive op without approval.
    INV-09: Must include a DecisionExplanation artifact reference.
    """

    __tablename__ = "approval_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    operation_type: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="e.g. destructive, schema_change, write"
    )
    environment: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING",
        comment="PENDING | APPROVED | REJECTED | EXPIRED",
    )
    requested_by: Mapped[str | None] = mapped_column(String(256), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(256), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id"), nullable=True,
        comment="INV-09: DecisionExplanation artifact",
    )
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    task: Mapped["Task"] = relationship(back_populates="approval_requests")

    __table_args__ = (
        Index("ix_approvals_task_id", "task_id"),
        Index("ix_approvals_status", "status"),
    )


# ── Execution ───────────────────────────────────────────────────────────

class Execution(Base):
    """
    Record of sandbox or production code execution.

    INV-05: Sandbox isolated from production data.
    """

    __tablename__ = "executions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    environment: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="SANDBOX or PRODUCTION"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING",
        comment="PENDING | RUNNING | SUCCESS | FAILED",
    )
    code_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id"), nullable=True
    )
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True, default=dict
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    task: Mapped["Task"] = relationship(back_populates="executions")

    __table_args__ = (
        Index("ix_executions_task_id", "task_id"),
        Index("ix_executions_status", "status"),
    )


# ── AuditEvent ──────────────────────────────────────────────────────────

class AuditEvent(Base):
    """
    Full audit trail entry — INV-06.

    Covers all actions and decisions across the platform.
    """

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    correlation_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="Links to HTTP request correlation ID"
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="e.g. task.created, state.transition, approval.requested",
    )
    actor: Mapped[str | None] = mapped_column(
        String(256), nullable=True, comment="user, agent, or system"
    )
    action: Mapped[str] = mapped_column(String(256), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        Index("ix_audit_correlation_id", "correlation_id"),
        Index("ix_audit_task_id", "task_id"),
        Index("ix_audit_event_type", "event_type"),
        Index("ix_audit_created_at", "created_at"),
    )
