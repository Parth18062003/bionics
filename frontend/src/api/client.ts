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
    AgentCatalogEntry,
    ExecutionTriggerResponse,
    ExecutionRecord,
    CatalogResponse,
    SchemaResponse,
    TableResponse,
    TableDetailResponse,
    TablePreviewResponse,
    FileResponse,
    NotebookResponse,
    JobResponse,
    PipelineResponse,
    QuickAction,
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

// ── Marketplace API ────────────────────────────────────────────────────

export async function listMarketplaceAgents(): Promise<AgentCatalogEntry[]> {
    return apiFetch<AgentCatalogEntry[]>('/api/v1/marketplace/agents');
}

export async function getMarketplaceAgent(agentId: string): Promise<AgentCatalogEntry> {
    return apiFetch<AgentCatalogEntry>(`/api/v1/marketplace/agents/${agentId}`);
}

// ── Execution API ──────────────────────────────────────────────────────

export async function executeTask(taskId: string): Promise<ExecutionTriggerResponse> {
    return apiFetch<ExecutionTriggerResponse>(`/api/v1/tasks/${taskId}/execute`, {
        method: 'POST',
    });
}

export async function getExecutions(taskId: string): Promise<ExecutionRecord[]> {
    return apiFetch<ExecutionRecord[]>(`/api/v1/executions/${taskId}`);
}

// ── Explorer API ────────────────────────────────────────────────────────

export async function listCatalogs(platform: 'fabric' | 'databricks'): Promise<CatalogResponse[]> {
    return apiFetch<CatalogResponse[]>(`/api/v1/explorer/${platform}/catalogs`);
}

export async function listSchemas(platform: 'fabric' | 'databricks', catalog: string): Promise<SchemaResponse[]> {
    const params = new URLSearchParams({ catalog });
    return apiFetch<SchemaResponse[]>(`/api/v1/explorer/${platform}/schemas?${params}`);
}

export async function listTables(platform: 'fabric' | 'databricks', catalog: string, schema: string): Promise<TableResponse[]> {
    const params = new URLSearchParams({ catalog, schema });
    return apiFetch<TableResponse[]>(`/api/v1/explorer/${platform}/tables?${params}`);
}

export async function getTableDetail(platform: 'fabric' | 'databricks', fullName: string): Promise<TableDetailResponse> {
    return apiFetch<TableDetailResponse>(`/api/v1/explorer/${platform}/tables/${encodeURIComponent(fullName)}`);
}

export async function previewTable(platform: 'fabric' | 'databricks', fullName: string, limit = 100): Promise<TablePreviewResponse> {
    const params = new URLSearchParams({ limit: String(limit) });
    return apiFetch<TablePreviewResponse>(`/api/v1/explorer/${platform}/tables/${encodeURIComponent(fullName)}/preview?${params}`);
}

export async function listExplorerFiles(
    platform: 'fabric' | 'databricks',
    path: string,
    workspaceId?: string,
    lakehouseId?: string
): Promise<FileResponse[]> {
    const params = new URLSearchParams({ path });
    if (workspaceId) params.set('workspace_id', workspaceId);
    if (lakehouseId) params.set('lakehouse_id', lakehouseId);
    return apiFetch<FileResponse[]>(`/api/v1/explorer/${platform}/files?${params}`);
}

export async function listExplorerNotebooks(
    platform: 'fabric' | 'databricks',
    path?: string,
    workspaceId?: string
): Promise<NotebookResponse[]> {
    const params = new URLSearchParams();
    if (path) params.set('path', path);
    if (workspaceId) params.set('workspace_id', workspaceId);
    return apiFetch<NotebookResponse[]>(`/api/v1/explorer/${platform}/notebooks?${params}`);
}

export async function listExplorerJobs(platform: 'fabric' | 'databricks'): Promise<JobResponse[]> {
    return apiFetch<JobResponse[]>(`/api/v1/explorer/${platform}/jobs`);
}

export async function listExplorerPipelines(
    platform: 'fabric' | 'databricks',
    workspaceId?: string
): Promise<PipelineResponse[]> {
    const params = new URLSearchParams();
    if (workspaceId) params.set('workspace_id', workspaceId);
    return apiFetch<PipelineResponse[]>(`/api/v1/explorer/${platform}/pipelines?${params}`);
}

export async function listLakehouses(workspaceId: string): Promise<SchemaResponse[]> {
    const params = new URLSearchParams({ workspace_id: workspaceId });
    return apiFetch<SchemaResponse[]>(`/api/v1/explorer/fabric/lakehouses?${params}`);
}

export async function listShortcuts(workspaceId: string, lakehouseId: string): Promise<Record<string, unknown>[]> {
    const params = new URLSearchParams({ workspace_id: workspaceId, lakehouse_id: lakehouseId });
    return apiFetch<Record<string, unknown>[]>(`/api/v1/explorer/fabric/shortcuts?${params}`);
}

// ── Quick Actions API ───────────────────────────────────────────────────

export async function getQuickActions(): Promise<QuickAction[]> {
    return apiFetch<QuickAction[]>('/api/v1/tasks/quick-actions');
}
