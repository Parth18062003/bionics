"""
AADAP — Notification Service
===============================
Dispatches notifications for approval lifecycle events.

Architecture layer: L5 (Orchestration) — Safety Architecture.
Enforces:
- INV-06: complete audit trail (notifications logged)

Usage:
    service = NotificationService()
    service.on_approval_requested(record)
    service.on_approved(record)

Design: Default channel is LOG.  Email/Webhook channels are
        stubbed for infrastructure-phase implementation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Callable

from aadap.core.logging import get_logger
from aadap.safety.approval_engine import ApprovalRecord, ApprovalStatus
from aadap.safety.routing import EscalationRecord

logger = get_logger(__name__)


# ── Notification Types ──────────────────────────────────────────────────

class NotificationChannel(StrEnum):
    """Supported notification channels."""

    LOG = "LOG"
    EMAIL = "EMAIL"
    WEBHOOK = "WEBHOOK"


class NotificationEventType(StrEnum):
    """Types of notification events."""

    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_APPROVED = "approval.approved"
    APPROVAL_REJECTED = "approval.rejected"
    APPROVAL_EXPIRED = "approval.expired"
    APPROVAL_ESCALATED = "approval.escalated"


# ── Data Objects ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class NotificationEvent:
    """A notification to be dispatched."""

    event_type: NotificationEventType
    recipient: str
    subject: str
    body: str
    metadata: dict[str, Any] = field(default_factory=dict)
    channel: NotificationChannel = NotificationChannel.LOG
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ── Notification Service ───────────────────────────────────────────────

class NotificationService:
    """
    Dispatches notifications for approval lifecycle events.

    Default: all notifications are logged (LOG channel).
    Email and webhook channels are stubbed for future implementation.
    """

    def __init__(self) -> None:
        self._history: list[NotificationEvent] = []
        self._handlers: dict[
            NotificationChannel, Callable[[NotificationEvent], None]
        ] = {
            NotificationChannel.LOG: self._handle_log,
            NotificationChannel.EMAIL: self._handle_email,
            NotificationChannel.WEBHOOK: self._handle_webhook,
        }

    @property
    def history(self) -> list[NotificationEvent]:
        """Return all dispatched notifications."""
        return list(self._history)

    def notify(self, event: NotificationEvent) -> None:
        """
        Dispatch a notification event.

        Parameters
        ----------
        event
            The notification to dispatch.
        """
        handler = self._handlers.get(event.channel, self._handle_log)
        handler(event)
        self._history.append(event)

    # ── Convenience hooks ───────────────────────────────────────────

    def on_approval_requested(self, record: ApprovalRecord) -> None:
        """Notify when an approval is requested."""
        self.notify(NotificationEvent(
            event_type=NotificationEventType.APPROVAL_REQUESTED,
            recipient=record.requested_by,
            subject=f"Approval Required: {record.operation_type} in {record.environment}",
            body=(
                f"Task {record.task_id} requires approval for "
                f"{record.operation_type} in {record.environment}. "
                f"Risk level: {record.risk_level.value}."
            ),
            metadata={
                "approval_id": str(record.id),
                "task_id": str(record.task_id),
                "risk_level": record.risk_level.value,
            },
        ))

    def on_approved(self, record: ApprovalRecord) -> None:
        """Notify when an approval is granted."""
        self.notify(NotificationEvent(
            event_type=NotificationEventType.APPROVAL_APPROVED,
            recipient=record.requested_by,
            subject=f"Approved: {record.operation_type} in {record.environment}",
            body=(
                f"Task {record.task_id} has been approved by "
                f"{record.decided_by}. Reason: {record.decision_reason or 'N/A'}."
            ),
            metadata={
                "approval_id": str(record.id),
                "task_id": str(record.task_id),
                "decided_by": record.decided_by,
            },
        ))

    def on_rejected(self, record: ApprovalRecord) -> None:
        """Notify when an approval is rejected — execution halted."""
        self.notify(NotificationEvent(
            event_type=NotificationEventType.APPROVAL_REJECTED,
            recipient=record.requested_by,
            subject=f"REJECTED: {record.operation_type} in {record.environment}",
            body=(
                f"Task {record.task_id} has been REJECTED by "
                f"{record.decided_by}. Reason: {record.decision_reason or 'N/A'}. "
                f"Execution is halted."
            ),
            metadata={
                "approval_id": str(record.id),
                "task_id": str(record.task_id),
                "decided_by": record.decided_by,
            },
        ))

    def on_expired(self, record: ApprovalRecord) -> None:
        """Notify when an approval expires."""
        self.notify(NotificationEvent(
            event_type=NotificationEventType.APPROVAL_EXPIRED,
            recipient=record.requested_by,
            subject=f"Expired: {record.operation_type} in {record.environment}",
            body=(
                f"Approval for task {record.task_id} has expired. "
                f"Escalation may be required."
            ),
            metadata={
                "approval_id": str(record.id),
                "task_id": str(record.task_id),
            },
        ))

    def on_escalated(self, escalation: EscalationRecord) -> None:
        """Notify when an approval is escalated."""
        for target in escalation.escalated_to:
            self.notify(NotificationEvent(
                event_type=NotificationEventType.APPROVAL_ESCALATED,
                recipient=target,
                subject=f"ESCALATION: Approval {escalation.approval_id}",
                body=(
                    f"Approval {escalation.approval_id} has been escalated. "
                    f"Reason: {escalation.reason}."
                ),
                metadata={
                    "escalation_id": str(escalation.id),
                    "approval_id": str(escalation.approval_id),
                    "reason": escalation.reason,
                },
            ))

    # ── Channel handlers ────────────────────────────────────────────

    def _handle_log(self, event: NotificationEvent) -> None:
        """Log the notification (default channel)."""
        logger.info(
            "notification.dispatched",
            event_type=event.event_type.value,
            recipient=event.recipient,
            subject=event.subject,
            channel=NotificationChannel.LOG.value,
        )

    def _handle_email(self, event: NotificationEvent) -> None:
        """Email notification (stub — deferred to infrastructure phase)."""
        logger.info(
            "notification.email_stub",
            event_type=event.event_type.value,
            recipient=event.recipient,
            subject=event.subject,
            channel=NotificationChannel.EMAIL.value,
        )

    def _handle_webhook(self, event: NotificationEvent) -> None:
        """Webhook notification (stub — deferred to infrastructure phase)."""
        logger.info(
            "notification.webhook_stub",
            event_type=event.event_type.value,
            recipient=event.recipient,
            subject=event.subject,
            channel=NotificationChannel.WEBHOOK.value,
        )
