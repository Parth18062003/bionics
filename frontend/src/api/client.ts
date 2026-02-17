import type { Task, SystemHealth, Artifact } from './types';

const API_BASE_Url = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL) ? import.meta.env.VITE_API_URL : '/api';

export class ApiClient {
    private baseUrl: string;

    constructor(baseUrl: string) {
        this.baseUrl = baseUrl;
    }

    private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
        const url = `${this.baseUrl}${endpoint}`;

        // Phase 7.4: Correlation ID Propagation
        const correlationId = (options.headers as any)?.['X-Correlation-ID'] || crypto.randomUUID();

        const headers = {
            'Content-Type': 'application/json',
            'X-Correlation-ID': correlationId,
            ...options.headers,
        };

        // Trace logging (Console for now, could be OpenTelemetry later)
        console.debug(`[${correlationId}] Requesting ${endpoint}`, { method: options.method || 'GET' });

        try {
            const response = await fetch(url, { ...options, headers });

            const responseCid = response.headers.get('X-Correlation-ID');
            if (responseCid && responseCid !== correlationId) {
                console.warn(`[${correlationId}] Response correlation ID mismatch: ${responseCid}`);
            }

            if (!response.ok) {
                // Handle error responses
                const errorBody = await response.text();
                console.error(`[${correlationId}] API Error ${response.status}`, errorBody);
                throw new Error(`API Error ${response.status}: ${errorBody}`);
            }

            return response.json();
        } catch (error) {
            console.error(`[${correlationId}] API Request Failed: ${endpoint}`, error);
            throw error;
        }
    }

    // Tasks
    async getTasks(filters?: { state?: string; environment?: string }): Promise<Task[]> {
        const query = new URLSearchParams(filters as any).toString();
        return this.request<Task[]>(`/tasks?${query}`);
    }

    async getTask(id: string): Promise<Task> {
        return this.request<Task>(`/tasks/${id}`);
    }

    async createTask(data: { description: string; environment: string; priority: string }): Promise<Task> {
        return this.request<Task>('/tasks', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    async updateTaskState(id: string, action: 'approve' | 'reject' | 'cancel' | 'escalate', payload?: any): Promise<Task> {
        return this.request<Task>(`/tasks/${id}/${action}`, {
            method: 'POST',
            body: JSON.stringify(payload || {}),
        });
    }

    // Artifacts
    async getArtifact(taskId: string, artifactId: string): Promise<Artifact> {
        return this.request<Artifact>(`/tasks/${taskId}/artifacts/${artifactId}`);
    }

    async getArtifactContent(taskId: string, artifactId: string): Promise<string> {
        // Special case for content often returning raw text
        const url = `${this.baseUrl}/tasks/${taskId}/artifacts/${artifactId}/content`;
        const response = await fetch(url);
        if (!response.ok) throw new Error('Failed to fetch artifact content');
        return response.text();
    }

    // System
    async getHealth(): Promise<SystemHealth> {
        return this.request<SystemHealth>('/health');
    }
}

export const api = new ApiClient(API_BASE_Url);
