export interface Agent {
    id: string;
    type: 'Orchestrator' | 'Developer' | 'Validation' | 'Optimization';
    status: 'IDLE' | 'BUSY' | 'ERROR';
    current_task_id?: string | null;
    uptime_seconds: number;
}

export interface Artifact {
    id: string;
    task_id: string;
    name: string;
    type: 'code' | 'markdown' | 'json' | 'sql' | 'plan' | 'report';
    size_bytes: number;
    created_at: string;
    download_url?: string;
    content?: string; // For inline viewing
}

// 25 States from ARCHITECTURE.md
export type TaskState =
    | "SUBMITTED" | "PARSING" | "PARSED" | "PARSE_FAILED"
    | "PLANNING" | "PLANNED"
    | "AGENT_ASSIGNMENT" | "AGENT_ASSIGNED" | "IN_DEVELOPMENT" | "CODE_GENERATED" | "DEV_FAILED"
    | "IN_VALIDATION" | "VALIDATION_PASSED" | "VALIDATION_FAILED"
    | "OPTIMIZATION_PENDING" | "IN_OPTIMIZATION" | "OPTIMIZED"
    | "APPROVAL_PENDING" | "IN_REVIEW" | "APPROVED" | "REJECTED"
    | "DEPLOYING" | "DEPLOYED" | "COMPLETED" | "CANCELLED";

export interface Task {
    id: string;
    description: string;
    state: TaskState;
    environment: 'SANDBOX' | 'PRODUCTION';
    risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
    created_at: string;
    updated_at: string;
    agent_id?: string | null;
    logs?: TaskLogEntry[];
    artifacts?: Artifact[];
    budget_estimate?: number;
    budget_used?: number;
    gate_results?: {
        gate_1: boolean;
        gate_2: boolean;
        gate_3: boolean;
        gate_4: boolean;
    };
    approval_context?: {
        trigger: string;
        wait_time_minutes: number;
        patterns_detected: string[];
        risk_score: number;
    };
}

export interface TaskLogEntry {
    timestamp: string;
    level: 'INFO' | 'WARN' | 'ERROR';
    agent_id?: string;
    message: string;
    metadata?: Record<string, any>;
}

export interface SystemHealth {
    services: {
        api: boolean;
        orchestrator: boolean;
        database: boolean;
        redis: boolean;
    };
    agents: Agent[];
    invariants: {
        id: string;
        description: string;
        status: 'ENFORCED' | 'WARNING' | 'VIOLATED';
    }[];
    events: TaskLogEntry[];
}
