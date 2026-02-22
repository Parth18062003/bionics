/**
 * AADAP — Log Types
 * ===================
 * TypeScript types for log functionality.
 */

export type LogLevel = 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR';

export interface TaskLog {
  id: string;
  task_id: string;
  timestamp: string;
  level: LogLevel;
  message: string;
  correlation_id: string | null;
  source: string | null;
}

export interface LogQueryParams {
  task_id?: string;
  levels?: LogLevel[];
  search?: string;
  limit?: number;
  offset?: number;
  start_time?: string;
  end_time?: string;
}

export interface LogsResponse {
  logs: TaskLog[];
  total: number;
  limit: number;
  offset: number;
}
