/**
 * AADAP — Logs Page
 * ====================
 * Dedicated log viewer with filters, search, and export.
 */

'use client';

import { useState, useEffect, useCallback, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useLogs } from '@/hooks/useLogs';
import type { LogLevel, TaskLog } from '@/types/log';

function LogsPageContent() {
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
  const [selectedCorrelation, setSelectedCorrelation] = useState<string | null>(null);

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
    <div className="h-[calc(100vh-60px)] flex flex-col bg-[var(--color-bg-primary)]">
      {/* Header */}
      <div className="p-4 border-b border-[var(--color-border)] bg-[var(--color-bg-card)]">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-xl font-semibold text-[var(--color-text-primary)]">
            Logs
          </h1>
          <div className="flex items-center gap-2">
            <button
              onClick={() => handleExport('json')}
              className="btn btn-ghost btn-sm"
            >
              Export JSON
            </button>
            <button
              onClick={() => handleExport('csv')}
              className="btn btn-ghost btn-sm"
            >
              Export CSV
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-3">
          {/* Level Filter */}
          <select
            value={levels.length === 4 ? 'all' : levels[0] || ''}
            onChange={(e) => {
              const val = e.target.value;
              if (val === 'all') {
                setLevels(['DEBUG', 'INFO', 'WARNING', 'ERROR']);
              } else {
                setLevels([val] as LogLevel[]);
              }
            }}
            className="form-select"
            style={{ width: 'auto' }}
          >
            <option value="all">All Levels</option>
            <option value="ERROR">ERROR</option>
            <option value="WARNING">WARNING</option>
            <option value="INFO">INFO</option>
            <option value="DEBUG">DEBUG</option>
          </select>

          {/* Search */}
          <input
            type="text"
            placeholder="Search logs..."
            value={search}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="form-input"
            style={{ width: '300px' }}
          />

          {(levels.length > 0 || search) && (
            <button
              onClick={() => {
                setLevels([]);
                setSearch('');
              }}
              className="btn btn-ghost btn-sm"
            >
              Reset
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden p-4">
        {error && (
          <div className="error-banner mb-4">
            {error}
            <button onClick={() => fetchLogs()} className="btn btn-ghost btn-sm ml-2">
              Retry
            </button>
          </div>
        )}

        {logs.length === 0 && !isLoading ? (
          <div className="empty-state">
            <div className="empty-state-icon">📋</div>
            <div className="empty-state-title">No logs found</div>
            <div className="empty-state-description">
              {(levels.length > 0 || search)
                ? "Try removing some filters or expanding your search."
                : "No logs have been recorded yet."}
            </div>
          </div>
        ) : (
          <div className="h-full overflow-y-auto">
            <div className="space-y-2">
              {logs.map((log) => (
                <LogEntry
                  key={log.id}
                  log={log}
                  onCorrelationClick={handleCorrelationClick}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      {total > 0 && (
        <div className="p-2 border-t border-[var(--color-border)] bg-[var(--color-bg-card)] text-xs text-[var(--color-text-secondary)]">
          Showing {logs.length} of {total} logs
        </div>
      )}
    </div>
  );
}

// Log Entry Component
function LogEntry({ log, onCorrelationClick }: { log: TaskLog; onCorrelationClick?: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = log.message.length > 150;

  const levelColors: Record<string, string> = {
    ERROR: 'bg-[var(--color-danger-muted)] text-[var(--color-danger)]',
    WARNING: 'bg-[var(--color-warning-muted)] text-[var(--color-warning)]',
    INFO: 'bg-[var(--color-info-muted)] text-[var(--color-info)]',
    DEBUG: 'bg-[var(--color-bg-tertiary)] text-[var(--color-text-secondary)]',
  };

  return (
    <div className="flex items-start gap-3 p-3 rounded-lg bg-[var(--color-bg-card)] border border-[var(--color-border)] hover:border-[var(--color-border-hover)]">
      {/* Level Badge */}
      <span className={`badge ${levelColors[log.level] || ''}`}>
        {log.level}
      </span>

      {/* Timestamp */}
      <span className="text-xs text-[var(--color-text-tertiary)] font-mono w-28 flex-shrink-0">
        {new Date(log.timestamp).toLocaleTimeString()}
      </span>

      {/* Source */}
      {log.source && (
        <span className="text-xs text-[var(--color-text-tertiary)] flex-shrink-0 px-2 py-0.5 rounded bg-[var(--color-bg-tertiary)]">
          {log.source}
        </span>
      )}

      {/* Message */}
      <span className="text-sm text-[var(--color-text-primary)] flex-1">
        {expanded || !isLong ? log.message : log.message.slice(0, 150) + '...'}
        {isLong && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-[var(--color-accent)] hover:underline ml-2"
          >
            {expanded ? 'Show less' : 'Show more'}
          </button>
        )}
      </span>

      {/* Correlation ID */}
      {log.correlation_id && onCorrelationClick && (
        <button
          onClick={() => onCorrelationClick(log.correlation_id!)}
          className="text-xs text-[var(--color-text-tertiary)] px-2 py-1 rounded bg-[var(--color-bg-tertiary)] hover:bg-[var(--color-bg-secondary)]"
          title="Click to filter by correlation ID"
        >
          🔗 {log.correlation_id.slice(0, 8)}
        </button>
      )}
    </div>
  );
}

export default function LogsPage() {
  return (
    <Suspense fallback={
      <div className="h-[calc(100vh-60px)] flex items-center justify-center">
        <div className="loading-spinner"></div>
      </div>
    }>
      <LogsPageContent />
    </Suspense>
  );
}
