/**
 * AADAP — Shared TypeScript Types
 * ================================
 * Mirrors backend Pydantic models for type-safe API consumption.
 * Trust boundary: UI ↔ API (no direct backend imports).
 */

// ── Task Types ─────────────────────────────────────────────────────────

export interface Task {
    id: string;
    title: string;
    description: string | null;
    current_state: string;
    priority: number;
    environment: string;
    created_by: string | null;
    token_budget: number;
    tokens_used: number;
    retry_count: number;
    created_at: string;
    updated_at: string;
}

export interface TaskListResponse {
    tasks: Task[];
    total: number;
    page: number;
    page_size: number;
}

export interface TaskCreateRequest {
    title: string;
    description?: string;
    priority?: number;
    environment?: string;
}

export interface TransitionRequest {
    next_state: string;
    reason?: string;
}

export interface TransitionResponse {
    task_id: string;
    from_state: string;
    to_state: string;
    triggered_by: string | null;
    reason: string | null;
}

// ── Event Types ────────────────────────────────────────────────────────

export interface TaskEvent {
    id: string;
    from_state: string;
    to_state: string;
    sequence_num: number;
    triggered_by: string | null;
    reason: string | null;
    created_at: string;
}

// ── Approval Types ─────────────────────────────────────────────────────

export interface Approval {
    id: string;
    task_id: string;
    operation_type: string;
    environment: string;
    status: string;
    requested_by: string;
    decided_by: string | null;
    decision_reason: string | null;
    risk_level: string;
    created_at: string;
    decided_at: string | null;
}

export interface ApprovalDecisionRequest {
    reason?: string;
}

// ── Artifact Types ─────────────────────────────────────────────────────

export interface ArtifactSummary {
    id: string;
    task_id: string;
    artifact_type: string;
    name: string;
    content_hash: string | null;
    storage_uri: string | null;
    created_at: string;
}

export interface ArtifactDetail extends ArtifactSummary {
    content: string | null;
    metadata: Record<string, unknown> | null;
}

// ── Health Types ───────────────────────────────────────────────────────

export interface HealthResponse {
    status: string;
    checks: Record<string, string>;
}

// ── State Metadata ─────────────────────────────────────────────────────

export const STATE_COLORS: Record<string, string> = {
    SUBMITTED: '#6366f1',
    VALIDATING: '#8b5cf6',
    PLANNING: '#a78bfa',
    READY: '#22d3ee',
    ASSIGNED: '#06b6d4',
    EXECUTING: '#f59e0b',
    AWAITING_REVIEW: '#f97316',
    REVIEWING: '#fb923c',
    APPROVED: '#10b981',
    REJECTED: '#ef4444',
    SELF_CORRECTING: '#eab308',
    RE_EXECUTING: '#d97706',
    ESCALATED: '#dc2626',
    HUMAN_REVIEW: '#e11d48',
    PAUSED: '#64748b',
    RESUMING: '#94a3b8',
    CHECKPOINTED: '#475569',
    FINALIZING: '#059669',
    COMPLETE: '#16a34a',
    FAILED: '#dc2626',
    CANCELLED: '#6b7280',
    TIMED_OUT: '#9333ea',
    ARCHIVING: '#78716c',
    ARCHIVED: '#a8a29e',
};

export const STATE_LABELS: Record<string, string> = {
    SUBMITTED: 'Submitted',
    VALIDATING: 'Validating',
    PLANNING: 'Planning',
    READY: 'Ready',
    ASSIGNED: 'Assigned',
    EXECUTING: 'Executing',
    AWAITING_REVIEW: 'Awaiting Review',
    REVIEWING: 'Reviewing',
    APPROVED: 'Approved',
    REJECTED: 'Rejected',
    SELF_CORRECTING: 'Self-Correcting',
    RE_EXECUTING: 'Re-Executing',
    ESCALATED: 'Escalated',
    HUMAN_REVIEW: 'Human Review',
    PAUSED: 'Paused',
    RESUMING: 'Resuming',
    CHECKPOINTED: 'Checkpointed',
    FINALIZING: 'Finalizing',
    COMPLETE: 'Complete',
    FAILED: 'Failed',
    CANCELLED: 'Cancelled',
    TIMED_OUT: 'Timed Out',
    ARCHIVING: 'Archiving',
    ARCHIVED: 'Archived',
};
