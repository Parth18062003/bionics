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
    task_mode?: TaskMode | null;
    operation_type?: OperationType | null;
    platform?: 'fabric' | 'databricks' | null;
}

export interface TaskListResponse {
    tasks: Task[];
    total: number;
    page: number;
    page_size: number;
}

// ── Task Mode & Operation Types ─────────────────────────────────────────

export type TaskMode = 'generate_code' | 'execute_code' | 'read' | 'list' | 'manage';

export type OperationType =
    | 'generate_notebook'
    | 'generate_pipeline'
    | 'generate_job'
    | 'execute_notebook'
    | 'execute_sql'
    | 'list_tables'
    | 'list_files'
    | 'list_notebooks'
    | 'list_pipelines'
    | 'list_jobs'
    | 'preview_table'
    | 'get_schema'
    | 'create_table'
    | 'drop_table'
    | 'create_shortcut'
    | 'custom';

export interface QuickAction {
    id: string;
    label: string;
    description: string;
    operation_type: OperationType;
    task_mode: TaskMode;
    platform: 'fabric' | 'databricks' | 'any';
    icon?: string;
}

export interface TaskCreateRequest {
    title: string;
    description?: string;
    priority?: number;
    environment?: string;
    agent_type?: string;
    capability_id?: string;
    language?: string;
    auto_execute?: boolean;
    capability_config?: IngestionConfig | PipelineConfig | JobConfig;
    task_mode?: TaskMode;
    operation_type?: OperationType;
    platform?: 'fabric' | 'databricks';
    catalog?: string;
    schema_name?: string;
    table?: string;
    file_path?: string;
    selection_context?: Record<string, unknown>;
}

// ── Capability Config Types ────────────────────────────────────────────

export interface IngestionConfig {
    /** Source system type, e.g. "adls", "sql_server", "kafka". */
    source_type: string;
    /** Target system type, e.g. "delta_lake", "lakehouse". */
    target_type: string;
    ingestion_mode: 'batch' | 'streaming' | 'cdc';
}

export interface Transformation {
    name: string;
    type: string;
}

export interface ScheduleConfig {
    cron_expression?: string;
    interval_minutes?: number;
    timezone?: string;
}

export interface PipelineConfig {
    pipeline_type: 'dlt' | 'datafactory' | 'workflow';
    transformations: Transformation[];
}

export interface JobConfig {
    job_type: 'notebook' | 'spark' | 'pipeline';
    schedule?: ScheduleConfig;
}

// ── Agent Marketplace Types ────────────────────────────────────────────

export interface AgentCatalogEntry {
    id: string;
    name: string;
    description: string;
    platform: string;
    languages: string[];
    capabilities: string[];
    icon: string;
    status: 'available' | 'coming_soon' | 'beta';
    config_defaults: Record<string, string>;
}

// ── Execution Types ────────────────────────────────────────────────────

export interface ExecutionTriggerResponse {
    task_id: string;
    status: string;
    message?: string | null;
    output?: string | null;
    error?: string | null;
    code?: string | null;
    language?: string | null;
    job_id?: string | null;
    duration_ms?: number | null;
}

export interface ExecutionRecord {
    id: string;
    task_id: string;
    environment: string;
    status: string;
    output: string | null;
    error: string | null;
    duration_ms: number | null;
    started_at: string | null;
    completed_at: string | null;
    created_at: string;
    platform?: string | null;
    code?: string | null;
    language?: string | null;
    job_id?: string | null;
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
    version?: number;
    parent_id?: string | null;
    edit_message?: string | null;
}

// ── Artifact Version Types ─────────────────────────────────────────────

export interface ArtifactVersionSummary {
    id: string;
    version: number;
    created_at: string;
    content_hash: string | null;
    edit_message?: string | null;
}

export interface DiffLine {
    old_line: number | null;
    new_line: number | null;
    content: string;
    type: 'unchanged' | 'added' | 'removed';
}

export interface DiffResponse {
    from_version: number;
    to_version: number;
    from_content: string | null;
    to_content: string | null;
    diff: DiffLine[];
    stats: { added: number; removed: number; unchanged: number };
}

export interface ArtifactVersionCreateRequest {
    content: string;
    edit_message?: string;
}

// ── Health Types ───────────────────────────────────────────────────────

export interface HealthResponse {
    status: string;
    checks: Record<string, string>;
}

// ── State Metadata ─────────────────────────────────────────────────────

export const STATE_COLORS: Record<string, string> = {
    SUBMITTED: '#6366f1',
    PARSING: '#8b5cf6',
    PARSED: '#7c3aed',
    PARSE_FAILED: '#ef4444',
    PLANNING: '#a78bfa',
    PLANNED: '#818cf8',
    AGENT_ASSIGNMENT: '#22d3ee',
    AGENT_ASSIGNED: '#06b6d4',
    IN_DEVELOPMENT: '#f59e0b',
    CODE_GENERATED: '#eab308',
    DEV_FAILED: '#ef4444',
    IN_VALIDATION: '#f97316',
    VALIDATION_PASSED: '#10b981',
    VALIDATION_FAILED: '#ef4444',
    OPTIMIZATION_PENDING: '#fb923c',
    IN_OPTIMIZATION: '#d97706',
    OPTIMIZED: '#059669',
    APPROVAL_PENDING: '#f59e0b',
    IN_REVIEW: '#fb923c',
    APPROVED: '#10b981',
    REJECTED: '#ef4444',
    DEPLOYING: '#3b82f6',
    DEPLOYED: '#059669',
    COMPLETED: '#16a34a',
    CANCELLED: '#6b7280',
};

export const STATE_LABELS: Record<string, string> = {
    SUBMITTED: 'Submitted',
    PARSING: 'Parsing',
    PARSED: 'Parsed',
    PARSE_FAILED: 'Parse Failed',
    PLANNING: 'Planning',
    PLANNED: 'Planned',
    AGENT_ASSIGNMENT: 'Assigning Agent',
    AGENT_ASSIGNED: 'Agent Assigned',
    IN_DEVELOPMENT: 'In Development',
    CODE_GENERATED: 'Code Generated',
    DEV_FAILED: 'Dev Failed',
    IN_VALIDATION: 'Validating',
    VALIDATION_PASSED: 'Validation Passed',
    VALIDATION_FAILED: 'Validation Failed',
    OPTIMIZATION_PENDING: 'Optimization Pending',
    IN_OPTIMIZATION: 'Optimizing',
    OPTIMIZED: 'Optimized',
    APPROVAL_PENDING: 'Awaiting Approval',
    IN_REVIEW: 'In Review',
    APPROVED: 'Approved',
    REJECTED: 'Rejected',
    DEPLOYING: 'Deploying',
    DEPLOYED: 'Deployed',
    COMPLETED: 'Completed',
    CANCELLED: 'Cancelled',
};

// ── Explorer Types ───────────────────────────────────────────────────────

export interface CatalogResponse {
    id: string;
    name: string;
    type: string;
    description?: string | null;
}

export interface SchemaResponse {
    id: string;
    name: string;
    catalog_id: string;
    type: string;
    description?: string | null;
}

export interface TableResponse {
    id: string;
    name: string;
    schema_name: string;
    catalog_name: string;
    full_name: string;
    type: string;
    row_count?: number | null;
}

export interface ColumnResponse {
    name: string;
    data_type: string;
    nullable: boolean;
    comment?: string | null;
}

export interface TableDetailResponse {
    id: string;
    name: string;
    schema_name: string;
    catalog_name: string;
    full_name: string;
    columns: ColumnResponse[];
    table_type?: string | null;
    row_count?: number | null;
    comment?: string | null;
}

export interface TablePreviewResponse {
    columns: string[];
    rows: unknown[][];
    row_count: number;
    truncated: boolean;
}

export interface FileResponse {
    name: string;
    path: string;
    type: string;
    size?: number | null;
}

export interface NotebookResponse {
    id: string;
    name: string;
    path?: string | null;
}

export interface JobResponse {
    id: string;
    name: string;
    status?: string | null;
}

export interface PipelineResponse {
    id: string;
    name: string;
    status?: string | null;
}

// ── Quick Actions List ───────────────────────────────────────────────────

export const QUICK_ACTIONS: QuickAction[] = [
    { id: 'list-tables', label: 'List Tables', description: 'List all tables in a schema', operation_type: 'list_tables', task_mode: 'list', platform: 'any', icon: 'table' },
    { id: 'preview-table', label: 'Preview Table', description: 'Preview data from a table', operation_type: 'preview_table', task_mode: 'read', platform: 'any', icon: 'eye' },
    { id: 'get-schema', label: 'Get Schema', description: 'Get table schema and columns', operation_type: 'get_schema', task_mode: 'read', platform: 'any', icon: 'schema' },
    { id: 'list-files', label: 'List Files', description: 'List files in a directory', operation_type: 'list_files', task_mode: 'list', platform: 'any', icon: 'folder' },
    { id: 'list-notebooks', label: 'List Notebooks', description: 'List all notebooks', operation_type: 'list_notebooks', task_mode: 'list', platform: 'any', icon: 'notebook' },
    { id: 'generate-notebook', label: 'Generate Notebook', description: 'Create a new notebook', operation_type: 'generate_notebook', task_mode: 'generate_code', platform: 'any', icon: 'code' },
    { id: 'generate-pipeline', label: 'Generate Pipeline', description: 'Create a new pipeline', operation_type: 'generate_pipeline', task_mode: 'generate_code', platform: 'any', icon: 'pipeline' },
];
