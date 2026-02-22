/**
 * AADAP — useLogs Hook
 * =====================
 * React hook for fetching and filtering task logs.
 */

import { useState, useEffect, useCallback } from 'react';
import type { TaskLog, LogLevel, LogsResponse } from '@/types/log';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface UseLogsOptions {
  taskId?: string;
  levels?: LogLevel[];
  search?: string;
  limit?: number;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

export function useLogs(options: UseLogsOptions = {}) {
  const [logs, setLogs] = useState<TaskLog[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [levels, setLevels] = useState<LogLevel[]>(options.levels || []);
  const [search, setSearch] = useState(options.search || '');
  const [offset, setOffset] = useState(0);

  const limit = options.limit || 50;

  const fetchLogs = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      params.set('limit', limit.toString());
      params.set('offset', offset.toString());
      if (options.taskId) params.set('task_id', options.taskId);
      if (levels.length > 0) params.set('levels', levels.join(','));
      if (search) params.set('search', search);

      const response = await fetch(`${API_BASE}/api/logs?${params}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch logs: ${response.statusText}`);
      }

      const data: LogsResponse = await response.json();
      setLogs(data.logs);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch logs');
    } finally {
      setIsLoading(false);
    }
  }, [options.taskId, levels, search, limit, offset]);

  const fetchLogsByCorrelation = useCallback(async (correlationId: string) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/api/logs/correlation/${correlationId}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch logs: ${response.statusText}`);
      }

      const data: LogsResponse = await response.json();
      return data.logs;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch logs');
      return [];
    } finally {
        setIsLoading(false);
    }
  }, []);

  const exportLogs = useCallback(async (format: 'json' | 'csv') => {
    try {
      const params = new URLSearchParams();
      params.set('format', format);
      if (options.taskId) params.set('task_id', options.taskId);
      if (levels.length > 0) params.set('levels', levels.join(','));
      if (search) params.set('search', search);

      const response = await fetch(`${API_BASE}/api/logs/export?${params}`);
      if (!response.ok) {
        throw new Error(`Failed to export logs: ${response.statusText}`);
      }

      // Download the file
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = response.headers.get('content-disposition')?.split('filename="')[1]?.replace(/"/g, '') || `logs.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to export logs');
    }
  }, [options.taskId, levels, search]);

  // Auto-refresh for real-time updates
  useEffect(() => {
    if (options.autoRefresh) {
      const interval = setInterval(fetchLogs, options.refreshInterval || 3000);
      return () => clearInterval(interval);
    }
  }, [options.autoRefresh, options.refreshInterval, fetchLogs]);

  // Initial fetch
  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  return {
    logs,
    total,
    isLoading,
    error,
    levels,
    setLevels,
    search,
    setSearch,
    offset,
    setOffset,
    fetchLogs,
    exportLogs,
    fetchLogsByCorrelation,
  };
}
