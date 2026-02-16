"""
AADAP — Notification Service Tests
=====================================
Phase 5 tests for the notification service.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from aadap.safety.approval_engine import ApprovalRecord, ApprovalStatus
from aadap.safety.routing import EscalationRecord
from aadap.safety.static_analysis import RiskLevel
from aadap.services.notifications import (
    NotificationChannel,
    NotificationEvent,
    NotificationEventType,
    NotificationService,
)


@pytest.fixture
def service() -> NotificationService:
    return NotificationService()


def _make_approval_record(
    status: ApprovalStatus = ApprovalStatus.PENDING,
    decided_by: str | None = None,
    decision_reason: str | None = None,
) -> ApprovalRecord:
    return ApprovalRecord(
        id=uuid.uuid4(),
        task_id=uuid.uuid4(),
        operation_type="write",
        environment="PRODUCTION",
        status=status,
        requested_by="developer@test.com",
        decided_by=decided_by,
        decision_reason=decision_reason,
        risk_level=RiskLevel.HIGH,
    )


# ── Notification Dispatch ──────────────────────────────────────────────


class TestNotificationDispatch:
    def test_notify_records_event(self, service: NotificationService) -> None:
        event = NotificationEvent(
            event_type=NotificationEventType.APPROVAL_REQUESTED,
            recipient="admin@test.com",
            subject="Test",
            body="Test body",
        )
        service.notify(event)
        assert len(service.history) == 1
        assert service.history[0].event_type == NotificationEventType.APPROVAL_REQUESTED

    def test_default_channel_is_log(self, service: NotificationService) -> None:
        event = NotificationEvent(
            event_type=NotificationEventType.APPROVAL_REQUESTED,
            recipient="admin@test.com",
            subject="Test",
            body="Test body",
        )
        assert event.channel == NotificationChannel.LOG


# ── Convenience Hooks ──────────────────────────────────────────────────


class TestApprovalHooks:
    def test_on_approval_requested(self, service: NotificationService) -> None:
        record = _make_approval_record()
        service.on_approval_requested(record)

        assert len(service.history) == 1
        event = service.history[0]
        assert event.event_type == NotificationEventType.APPROVAL_REQUESTED
        assert event.recipient == record.requested_by
        assert "Approval Required" in event.subject

    def test_on_approved(self, service: NotificationService) -> None:
        record = _make_approval_record(
            status=ApprovalStatus.APPROVED,
            decided_by="admin",
            decision_reason="Looks good",
        )
        service.on_approved(record)

        assert len(service.history) == 1
        event = service.history[0]
        assert event.event_type == NotificationEventType.APPROVAL_APPROVED
        assert "admin" in event.body
        assert "Looks good" in event.body

    def test_on_rejected(self, service: NotificationService) -> None:
        record = _make_approval_record(
            status=ApprovalStatus.REJECTED,
            decided_by="admin",
            decision_reason="Too risky",
        )
        service.on_rejected(record)

        assert len(service.history) == 1
        event = service.history[0]
        assert event.event_type == NotificationEventType.APPROVAL_REJECTED
        assert "REJECTED" in event.subject
        assert "halted" in event.body.lower()

    def test_on_expired(self, service: NotificationService) -> None:
        record = _make_approval_record(status=ApprovalStatus.EXPIRED)
        service.on_expired(record)

        assert len(service.history) == 1
        event = service.history[0]
        assert event.event_type == NotificationEventType.APPROVAL_EXPIRED

    def test_on_escalated(self, service: NotificationService) -> None:
        escalation = EscalationRecord(
            id=uuid.uuid4(),
            approval_id=uuid.uuid4(),
            reason="Timeout after 60 minutes",
            escalated_to=("security_admin", "platform_admin"),
        )
        service.on_escalated(escalation)

        # Should notify each escalation target
        assert len(service.history) == 2
        recipients = {e.recipient for e in service.history}
        assert "security_admin" in recipients
        assert "platform_admin" in recipients
        assert all(
            e.event_type == NotificationEventType.APPROVAL_ESCALATED
            for e in service.history
        )


# ── Event Metadata ─────────────────────────────────────────────────────


class TestEventMetadata:
    def test_approval_requested_metadata(
        self, service: NotificationService
    ) -> None:
        record = _make_approval_record()
        service.on_approval_requested(record)

        event = service.history[0]
        assert "approval_id" in event.metadata
        assert "task_id" in event.metadata
        assert "risk_level" in event.metadata

    def test_escalated_metadata(self, service: NotificationService) -> None:
        escalation = EscalationRecord(
            id=uuid.uuid4(),
            approval_id=uuid.uuid4(),
            reason="Critical risk",
            escalated_to=("admin",),
        )
        service.on_escalated(escalation)

        event = service.history[0]
        assert "escalation_id" in event.metadata
        assert "approval_id" in event.metadata
