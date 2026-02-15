"""
AADAP — Model & Schema Validation Tests
=========================================
Validates the SQLAlchemy models align with DATA_AND_STATE.md entities
and embed the correct invariant defaults.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from aadap.db.models import (
    TASK_STATES,
    Artifact,
    ApprovalRequest,
    AuditEvent,
    Base,
    Execution,
    StateTransition,
    Task,
)


# ── Authoritative State Set ─────────────────────────────────────────────

def test_exactly_25_authoritative_states():
    """ARCHITECTURE.md mandates exactly 25 states."""
    assert len(TASK_STATES) == 25


def test_no_duplicate_states():
    """Each state name must be unique."""
    assert len(TASK_STATES) == len(set(TASK_STATES))


def test_start_end_not_in_states():
    """START and END are implicit non-states, not in the authoritative set."""
    assert "START" not in TASK_STATES
    assert "END" not in TASK_STATES


def test_submitted_is_first_state():
    """SUBMITTED is the initial state."""
    assert TASK_STATES[0] == "SUBMITTED"


def test_key_states_present():
    """Critical lifecycle states exist."""
    required = [
        "SUBMITTED", "PARSING", "PARSED", "PLANNING", "PLANNED",
        "AGENT_ASSIGNED", "IN_DEVELOPMENT", "CODE_GENERATED",
        "IN_VALIDATION", "VALIDATION_PASSED", "APPROVAL_PENDING",
        "APPROVED", "DEPLOYING", "DEPLOYED", "COMPLETED", "CANCELLED",
    ]
    for state in required:
        assert state in TASK_STATES, f"Missing state: {state}"


# ── Task Model ──────────────────────────────────────────────────────────

def test_task_default_state():
    """New tasks default to SUBMITTED (schema-level default)."""
    col = Task.__table__.c.current_state
    assert col.default.arg == "SUBMITTED"


def test_task_default_token_budget():
    """INV-04: Default token budget is 50,000 (schema-level default)."""
    col = Task.__table__.c.token_budget
    assert col.default.arg == 50_000


def test_task_default_retry_count():
    """INV-03: Retry count starts at 0 (schema-level default)."""
    col = Task.__table__.c.retry_count
    assert col.default.arg == 0


def test_task_default_environment():
    """Default environment is SANDBOX (schema-level default)."""
    col = Task.__table__.c.environment
    assert col.default.arg == "SANDBOX"


# ── Core Entities Exist ─────────────────────────────────────────────────

def test_all_six_entities_have_tables():
    """DATA_AND_STATE.md defines exactly 6 core entities."""
    table_names = set(Base.metadata.tables.keys())
    required = {
        "tasks",
        "state_transitions",
        "artifacts",
        "approval_requests",
        "executions",
        "audit_events",
    }
    assert required.issubset(table_names)


def test_state_transition_has_sequence_num():
    """StateTransition supports ordered replay via sequence_num."""
    cols = {c.name for c in StateTransition.__table__.columns}
    assert "sequence_num" in cols


def test_artifact_has_content_hash():
    """Artifacts have integrity hashing."""
    cols = {c.name for c in Artifact.__table__.columns}
    assert "content_hash" in cols


def test_approval_has_explanation_artifact_fk():
    """INV-09: ApprovalRequest links to DecisionExplanation artifact."""
    cols = {c.name for c in ApprovalRequest.__table__.columns}
    assert "explanation_artifact_id" in cols


def test_audit_event_has_correlation_id():
    """AuditEvent supports correlation ID for cross-request tracing."""
    cols = {c.name for c in AuditEvent.__table__.columns}
    assert "correlation_id" in cols


def test_execution_tracks_environment():
    """INV-05: Execution records sandbox vs production."""
    cols = {c.name for c in Execution.__table__.columns}
    assert "environment" in cols
