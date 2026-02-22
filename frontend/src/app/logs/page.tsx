/**
 * AADAP — Logs Page
 * ====================
 * Dedicated log viewer with filters, search, and export.
 */

'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { LogViewer, LogFilters } from '@/components/logs';
import { useLogs } from '@/hooks/useLogs';
import type { LogLevel } from '@/types/log';

export default function LogsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Initialize from URL params
  const [levels, setLevels] = useState<LogLevel[]>(() => {
    const levelsParam = searchParams.get('levels');
    return levelsParam ? (levelsParam.split(',') as LogLevel[]) : [];
  });
  const [search, setSearch] = useState(() => searchParams.get('search') || '');
  const [selectedTask, setSelectedTask] = useState<string | null>(
    searchParams.get('task')
  );
  const [selectedCorrelation, setSelectedCorrelation] = useState<string | null>(
    null
  );

  // Update URL when filters change
  useEffect(() => {
    const params = new URLSearchParams();
    if (levels.length > 0) params.set('levels', levels.join(','));
    if (search) params.set('search', search);
    if (selectedTask) params.set('task', selectedTask);

    const url = params.toString() ? `?${params.toString()}` : '';
    router.replace(`/logs${url}`, { scroll: false });
  }, [levels, search, selectedTask, router]);

  const {
    logs,
    total,
    isLoading,
    error,
    fetchLogs,
    exportLogs,
    fetchLogsByCorrelation,
  } = useLogs({
    taskId: selectedTask || undefined,
    levels,
    search: search || undefined,
    limit: 100,
  });

  const handleCorrelationClick = useCallback(async (correlationId: string) => {
    setSelectedCorrelation(correlationId);
    const relatedLogs = await fetchLogsByCorrelation(correlationId);
    // Could show in a modal or filter the view
  }, [fetchLogsByCorrelation]);

  const handleLevelChange = useCallback((newLevels: LogLevel[]) => {
    setLevels(newLevels);
  }, []);

  const handleSearchChange = useCallback((newSearch: string) => {
    setSearch(newSearch);
  }, []);

  const handleExport = useCallback((format: 'json' | 'csv') => {
    exportLogs(format);
  }, [exportLogs]);

  return (
    <div className="h-[calc(100vh-60px)] flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-xl font-semibold text-gray-900 dark:text-white">
            Logs
          </h1>
          <div className="flex items-center gap-2">
            <button
              onClick={() => handleExport('json')}
              className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700"
            >
              Export JSON
            </button>
            <button
              onClick={() => handleExport('csv')}
              className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700"
            >
              Export CSV
            </button>
          </div>
        </div>

        <LogFilters
          levels={levels}
          onLevelChange={handleLevelChange}
          search={search}
          onSearchChange={handleSearchChange}
        />
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden bg-gray-50 dark:bg-gray-950">
        {error && (
          <div className="p-4 text-center text-red-500">
            {error}
            <button
              onClick={() => fetchLogs()}
              className="ml-2 text-blue-500 hover:text-blue-700"
            >
              Retry
            </button>
          </div>
        )}

        {logs.length === 0 && !isLoading ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-500 dark:text-gray-400">
            <svg className="w-16 h-16 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
            <p className="text-lg mb-2">No logs found</p>
            {(levels.length > 0 || search) && (
              <p className="text-sm">
                Try removing some filters or expanding your search.
              </p>
            )}
          </div>
        ) : (
          <div className="h-full p-4">
            <div className="h-full overflow-y-auto bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700">
              <div className="p-4">
                {logs.map((log) => (
                  <div key={log.id} className="mb-2">
                    <div className="flex items-start gap-3 p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800">
                      {/* Level indicator */}
                      <div
                        className={`flex-shrink-0 w-20 text-xs font-medium px-2 py-1 rounded text-center ${
                          log.level === 'ERROR'
                            ? 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'
                            : log.level === 'WARNING'
                            ? 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300'
                            : log.level === 'INFO'
                            ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
                            : 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
                        }`}
                      >
                        {log.level}
                      </div>

                      {/* Timestamp */}
                      <div className="flex-shrink-0 w-32 text-xs text-gray-500 dark:text-gray-400 font-mono">
                        {new Date(log.timestamp).toLocaleTimeString()}
                      </div>

                      {/* Source */}
                      {log.source && (
                        <div className="flex-shrink-0 w-24 text-xs text-gray-400 dark:text-gray-500 truncate">
                          {log.source}
                        </div>
                      )}

                      {/* Message */}
                      <div className="flex-1 text-sm text-gray-700 dark:text-gray-300">
                        {log.message.length > 200
                          ? log.message.slice(0, 200) + '...'
                          : log.message}
                      </div>

                      {/* Correlation ID */}
                      {log.correlation_id && (
                        <button
                          onClick={() => handleCorrelationClick(log.correlation_id!)}
                          className="flex-shrink-0 px-2 py-1 text-xs text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-800 rounded hover:bg-gray-200 dark:hover:bg-gray-700"
                        >
                          🔗 {log.correlation_id.slice(0, 8)}
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      {total > 0 && (
        <div className="p-2 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-xs text-gray-500 dark:text-gray-400">
          Showing {logs.length} of {total} logs
        </div>
      )}
    </div>
  );
}
