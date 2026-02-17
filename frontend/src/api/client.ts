/**
 * AADAP — API Client
 * ====================
 * Type-safe REST client for the AADAP backend API.
 *
 * Trust boundary: All UI data flows through this client.
 * Invariant: UI cannot bypass API — this is the only data access layer.
 *
 * Features:
 * - Correlation ID injection on every request
 * - Type-safe request/response handling
 * - Centralized error handling
 */

import type {
    Task,
    TaskListResponse,
    TaskCreateRequest,
    TransitionRequest,
    TransitionResponse,
    TaskEvent,
    Approval,
    ApprovalDecisionRequest,
    ArtifactSummary,
    ArtifactDetail,
    HealthResponse,
} from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Generate a correlation ID for tracing.
 */
function generateCorrelationId(): string {
    return crypto.randomUUID();
}

/**
 * Core fetch wrapper with correlation ID injection and error handling.
 */
async function apiFetch<T>(
    path: string,
    options: RequestInit = {},
    correlationId?: string
): Promise<T> {
    const cid = correlationId || generateCorrelationId();
    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        'X-Correlation-ID': cid,
        ...(options.headers as Record<string, string> || {}),
    };

    const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers,
    });

    if (!response.ok) {
        const errorBody = await response.text();
        let detail = errorBody;
        try {
            const parsed = JSON.parse(errorBody);
            detail = parsed.detail || errorBody;
        } catch {
            // Use raw text
        }
        throw new ApiError(response.status, detail, cid);
    }

    return response.json() as Promise<T>;
}

/**
 * Structured API error with status, detail, and correlation ID.
 */
export class ApiError extends Error {
    constructor(
        public status: number,
        public detail: string,
        public correlationId: string
    ) {
        super(`API Error ${status}: ${detail}`);
        this.name = 'ApiError';
    }
}

// ── Task API ───────────────────────────────────────────────────────────

export async function createTask(data: TaskCreateRequest): Promise<Task> {
    return apiFetch<Task>('/api/v1/tasks', {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

export async function listTasks(
    page = 1,
    pageSize = 20,
    state?: string
): Promise<TaskListResponse> {
    const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
    });
    if (state) params.set('state', state);
    return apiFetch<TaskListResponse>(`/api/v1/tasks?${params}`);
}

export async function getTask(taskId: string): Promise<Task> {
    return apiFetch<Task>(`/api/v1/tasks/${taskId}`);
}

export async function transitionTask(
    taskId: string,
    data: TransitionRequest
): Promise<TransitionResponse> {
    return apiFetch<TransitionResponse>(`/api/v1/tasks/${taskId}/transition`, {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

export async function getTaskEvents(taskId: string): Promise<TaskEvent[]> {
    return apiFetch<TaskEvent[]>(`/api/v1/tasks/${taskId}/events`);
}

// ── Approval API ───────────────────────────────────────────────────────

export async function listApprovals(): Promise<Approval[]> {
    return apiFetch<Approval[]>('/api/v1/approvals');
}

export async function getApproval(approvalId: string): Promise<Approval> {
    return apiFetch<Approval>(`/api/v1/approvals/${approvalId}`);
}

export async function approveRequest(
    approvalId: string,
    data: ApprovalDecisionRequest = {}
): Promise<Approval> {
    return apiFetch<Approval>(`/api/v1/approvals/${approvalId}/approve`, {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

export async function rejectRequest(
    approvalId: string,
    data: ApprovalDecisionRequest = {}
): Promise<Approval> {
    return apiFetch<Approval>(`/api/v1/approvals/${approvalId}/reject`, {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

// ── Artifact API ───────────────────────────────────────────────────────

export async function listArtifacts(
    taskId: string
): Promise<ArtifactSummary[]> {
    return apiFetch<ArtifactSummary[]>(`/api/v1/tasks/${taskId}/artifacts`);
}

export async function getArtifact(
    taskId: string,
    artifactId: string
): Promise<ArtifactDetail> {
    return apiFetch<ArtifactDetail>(
        `/api/v1/tasks/${taskId}/artifacts/${artifactId}`
    );
}

// ── Health API ─────────────────────────────────────────────────────────

export async function checkHealth(): Promise<HealthResponse> {
    return apiFetch<HealthResponse>('/health');
}
