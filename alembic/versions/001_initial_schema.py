"""Initial schema - Core entities

Revision ID: 001
Revises: None
Create Date: 2026-02-16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Extensions ─────────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
    # op.execute("CREATE EXTENSION IF NOT EXISTS \"vector\"")

    # ── Tasks ────────────────────────────────────────────────────────
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("current_state", sa.String(64), nullable=False,
                  server_default="SUBMITTED"),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column("environment", sa.String(32), nullable=False,
                  server_default="SANDBOX"),
        sa.Column("created_by", sa.String(256), nullable=True),
        sa.Column("token_budget", sa.Integer, nullable=False,
                  server_default="50000",
                  comment="INV-04: Token budget per task"),
        sa.Column("tokens_used", sa.Integer, nullable=False,
                  server_default="0"),
        sa.Column("retry_count", sa.Integer, nullable=False,
                  server_default="0",
                  comment="INV-03: bounded self-correction, max 3"),
        sa.Column("metadata", postgresql.JSONB, nullable=True,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_tasks_current_state", "tasks", ["current_state"])
    op.create_index("ix_tasks_priority", "tasks", ["priority"])
    op.create_index("ix_tasks_created_at", "tasks", ["created_at"])

    # ── State Transitions (event sourcing) ───────────────────────────
    op.create_table(
        "state_transitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("task_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_state", sa.String(64), nullable=False),
        sa.Column("to_state", sa.String(64), nullable=False),
        sa.Column("sequence_num", sa.Integer, nullable=False),
        sa.Column("triggered_by", sa.String(256), nullable=True,
                  comment="agent id, user email, or system"),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_st_task_id_seq", "state_transitions",
                    ["task_id", "sequence_num"], unique=True)
    op.create_index("ix_st_created_at", "state_transitions", ["created_at"])

    # ── Artifacts ────────────────────────────────────────────────────
    op.create_table(
        "artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("task_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("artifact_type", sa.String(64), nullable=False,
                  comment="e.g. code, config, decision_explanation"),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("content_hash", sa.String(128), nullable=True,
                  comment="SHA-256 of content"),
        sa.Column("storage_uri", sa.String(1024), nullable=True,
                  comment="Blob URI for Tier 3 archive"),
        sa.Column("metadata", postgresql.JSONB, nullable=True,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_artifacts_task_id", "artifacts", ["task_id"])
    op.create_index("ix_artifacts_type", "artifacts", ["artifact_type"])

    # ── Approval Requests ────────────────────────────────────────────
    op.create_table(
        "approval_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("task_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("operation_type", sa.String(64), nullable=False,
                  comment="e.g. destructive, schema_change, write"),
        sa.Column("environment", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False,
                  server_default="PENDING"),
        sa.Column("requested_by", sa.String(256), nullable=True),
        sa.Column("decided_by", sa.String(256), nullable=True),
        sa.Column("decision_reason", sa.Text, nullable=True),
        sa.Column("explanation_artifact_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("artifacts.id"), nullable=True,
                  comment="INV-09: DecisionExplanation artifact"),
        sa.Column("metadata", postgresql.JSONB, nullable=True,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_approvals_task_id", "approval_requests", ["task_id"])
    op.create_index("ix_approvals_status", "approval_requests", ["status"])

    # ── Executions ───────────────────────────────────────────────────
    op.create_table(
        "executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("task_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("environment", sa.String(32), nullable=False,
                  comment="SANDBOX or PRODUCTION"),
        sa.Column("status", sa.String(32), nullable=False,
                  server_default="PENDING"),
        sa.Column("code_artifact_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("artifacts.id"), nullable=True),
        sa.Column("output", sa.Text, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_executions_task_id", "executions", ["task_id"])
    op.create_index("ix_executions_status", "executions", ["status"])

    # ── Audit Events ─────────────────────────────────────────────────
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("correlation_id", sa.String(64), nullable=True,
                  comment="Links to HTTP request correlation ID"),
        sa.Column("task_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(128), nullable=False,
                  comment="e.g. task.created, state.transition"),
        sa.Column("actor", sa.String(256), nullable=True,
                  comment="user, agent, or system"),
        sa.Column("action", sa.String(256), nullable=False),
        sa.Column("resource_type", sa.String(128), nullable=True),
        sa.Column("resource_id", sa.String(256), nullable=True),
        sa.Column("details", postgresql.JSONB, nullable=True,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_audit_correlation_id", "audit_events",
                    ["correlation_id"])
    op.create_index("ix_audit_task_id", "audit_events", ["task_id"])
    op.create_index("ix_audit_event_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_created_at", "audit_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("executions")
    op.drop_table("approval_requests")
    op.drop_table("artifacts")
    op.drop_table("state_transitions")
    op.drop_table("tasks")
    # op.execute("DROP EXTENSION IF EXISTS \"vector\"")
    op.execute("DROP EXTENSION IF EXISTS \"uuid-ossp\"")
