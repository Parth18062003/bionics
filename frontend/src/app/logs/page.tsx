/**
 * AADAP — Logs Page
 * ====================
 * Dedicated log viewer with filters, search, and export.
 * Uses CSS variables for consistent theming.
 */

'use client';

import { useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
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
    levels,
    search: search || undefined,
    limit: 100,
  });

  const handleCorrelationClick = async (correlationId: string) => {
    setSelectedCorrelation(correlationId);
    await fetchLogsByCorrelation(correlationId);
  };

  const handleExport = (format: 'json' | 'csv') => {
    exportLogs(format);
  };

  const clearFilters = () => {
    setLevels([]);
    setSearch('');
    setSelectedCorrelation(null);
  };

  const hasFilters = levels.length > 0 || search || selectedCorrelation;

  return (
    <div className="page-container animate-in">
      {/* Header */}
      <div className="page-header">
        <div className="page-header-inner">
          <div>
            <h1>System Logs</h1>
            <p>View and filter execution logs from all tasks and agents</p>
          </div>
          <div className="page-header-actions">
            <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
              <button onClick={() => handleExport('json')} className="btn btn-ghost btn-sm">
                Export JSON
              </button>
              <button onClick={() => handleExport('csv')} className="btn btn-ghost btn-sm">
                Export CSV
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div
        className="card"
        style={{
          marginBottom: 'var(--space-xl)',
          padding: 'var(--space-lg)',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-md)',
            flexWrap: 'wrap',
          }}
        >
          {/* Level Filter */}
          <div className="form-group" style={{ marginBottom: 0 }}>
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
              style={{ width: 'auto', minWidth: '140px' }}
            >
              <option value="all">All Levels</option>
              <option value="ERROR">ERROR</option>
              <option value="WARNING">WARNING</option>
              <option value="INFO">INFO</option>
              <option value="DEBUG">DEBUG</option>
            </select>
          </div>

          {/* Search */}
          <div className="form-group" style={{ marginBottom: 0, flex: 1, minWidth: '200px' }}>
            <input
              type="text"
              placeholder="Search logs..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="form-input"
            />
          </div>

          {/* Clear filters */}
          {hasFilters && (
            <button onClick={clearFilters} className="btn btn-ghost btn-sm">
              Clear Filters
            </button>
          )}
        </div>

        {/* Active filters display */}
        {hasFilters && (
          <div
            style={{
              display: 'flex',
              gap: 'var(--space-sm)',
              marginTop: 'var(--space-md)',
              flexWrap: 'wrap',
            }}
          >
            {levels.map((level) => (
              <span
                key={level}
                style={{
                  padding: 'var(--space-xs) var(--space-md)',
                  background: 'var(--color-accent-muted)',
                  color: 'var(--color-accent)',
                  borderRadius: 'var(--radius-full)',
                  fontSize: 'var(--font-size-xs)',
                  fontWeight: 500,
                }}
              >
                {level}
              </span>
            ))}
            {search && (
              <span
                style={{
                  padding: 'var(--space-xs) var(--space-md)',
                  background: 'var(--color-bg-tertiary)',
                  color: 'var(--color-text-secondary)',
                  borderRadius: 'var(--radius-full)',
                  fontSize: 'var(--font-size-xs)',
                }}
              >
                Search: &quot;{search}&quot;
              </span>
            )}
            {selectedCorrelation && (
              <span
                style={{
                  padding: 'var(--space-xs) var(--space-md)',
                  background: 'var(--color-info-muted)',
                  color: 'var(--color-info)',
                  borderRadius: 'var(--radius-full)',
                  fontSize: 'var(--font-size-xs)',
                }}
              >
                🔗 {selectedCorrelation.slice(0, 8)}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Error Banner */}
      {error && (
        <div className="error-banner" style={{ marginBottom: 'var(--space-lg)' }}>
          {error}
          <button onClick={() => fetchLogs()} className="btn btn-ghost btn-sm" style={{ marginLeft: 'var(--space-md)' }}>
            Retry
          </button>
        </div>
      )}

      {/* Logs List */}
      {isLoading && logs.length === 0 ? (
        <div className="card" style={{ padding: 'var(--space-3xl)', textAlign: 'center' }}>
          <div className="loading-spinner" style={{ margin: '0 auto var(--space-md)' }} />
          <p className="text-secondary">Loading logs...</p>
        </div>
      ) : logs.length === 0 ? (
        <div className="card" style={{ padding: 'var(--space-3xl)' }}>
          <div className="empty-state">
            <div className="empty-state-icon">📋</div>
            <div className="empty-state-title">No logs found</div>
            <div className="empty-state-description">
              {hasFilters
                ? 'Try removing some filters or expanding your search.'
                : 'No logs have been recorded yet. Logs will appear here when tasks are executed.'}
            </div>
          </div>
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          {/* Table Header */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '80px 100px 1fr 120px 140px',
              gap: 'var(--space-md)',
              padding: 'var(--space-md) var(--space-lg)',
              borderBottom: '1px solid var(--color-border)',
              background: 'var(--color-bg-tertiary)',
              fontSize: 'var(--font-size-xs)',
              fontWeight: 600,
              color: 'var(--color-text-tertiary)',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
            }}
          >
            <span>Level</span>
            <span>Time</span>
            <span>Message</span>
            <span>Source</span>
            <span>Correlation</span>
          </div>

          {/* Table Body */}
          <div style={{ maxHeight: 'calc(100vh - 350px)', overflowY: 'auto' }}>
            {logs.map((log) => (
              <LogEntry
                key={log.id}
                log={log}
                onCorrelationClick={handleCorrelationClick}
              />
            ))}
          </div>

          {/* Footer */}
          <div
            style={{
              padding: 'var(--space-md) var(--space-lg)',
              borderTop: '1px solid var(--color-border)',
              background: 'var(--color-bg-tertiary)',
              fontSize: 'var(--font-size-xs)',
              color: 'var(--color-text-secondary)',
              display: 'flex',
              justifyContent: 'space-between',
            }}
          >
            <span>Showing {logs.length} of {total} logs</span>
            <span className="font-mono">Last updated: {new Date().toLocaleTimeString()}</span>
          </div>
        </div>
      )}
    </div>
  );
}

// Log Entry Component
function LogEntry({ log, onCorrelationClick }: { log: TaskLog; onCorrelationClick?: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = log.message.length > 150;

  const levelStyles: Record<string, { bg: string; color: string }> = {
    ERROR: { bg: 'var(--color-danger-muted)', color: 'var(--color-danger)' },
    WARNING: { bg: 'var(--color-warning-muted)', color: 'var(--color-warning)' },
    INFO: { bg: 'var(--color-info-muted)', color: 'var(--color-info)' },
    DEBUG: { bg: 'var(--color-bg-tertiary)', color: 'var(--color-text-secondary)' },
  };

  const style = levelStyles[log.level] || levelStyles.DEBUG;

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '80px 100px 1fr 120px 140px',
        gap: 'var(--space-md)',
        padding: 'var(--space-md) var(--space-lg)',
        borderBottom: '1px solid var(--color-border)',
        fontSize: 'var(--font-size-sm)',
        transition: 'background var(--transition-fast)',
      }}
    >
      {/* Level */}
      <span
        style={{
          padding: '2px var(--space-sm)',
          background: style.bg,
          color: style.color,
          borderRadius: 'var(--radius-sm)',
          fontSize: 'var(--font-size-xs)',
          fontWeight: 600,
          height: 'fit-content',
        }}
      >
        {log.level}
      </span>

      {/* Timestamp */}
      <span
        style={{
          color: 'var(--color-text-tertiary)',
          fontFamily: 'var(--font-mono)',
          fontSize: 'var(--font-size-xs)',
        }}
      >
        {new Date(log.timestamp).toLocaleTimeString()}
      </span>

      {/* Message */}
      <div>
        <span
          style={{
            color: 'var(--color-text-primary)',
            wordBreak: 'break-word',
          }}
        >
          {expanded || !isLong ? log.message : log.message.slice(0, 150) + '...'}
        </span>
        {isLong && (
          <button
            onClick={() => setExpanded(!expanded)}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--color-accent)',
              fontSize: 'var(--font-size-xs)',
              cursor: 'pointer',
              marginLeft: 'var(--space-sm)',
              padding: 0,
            }}
          >
            {expanded ? 'Show less' : 'Show more'}
          </button>
        )}
      </div>

      {/* Source */}
      <span
        style={{
          color: 'var(--color-text-tertiary)',
          fontSize: 'var(--font-size-xs)',
        }}
      >
        {log.source || '—'}
      </span>

      {/* Correlation ID */}
      <span>
        {log.correlation_id && onCorrelationClick ? (
          <button
            onClick={() => onCorrelationClick(log.correlation_id!)}
            style={{
              background: 'var(--color-bg-tertiary)',
              border: 'none',
              color: 'var(--color-text-secondary)',
              fontSize: 'var(--font-size-xs)',
              padding: '2px var(--space-sm)',
              borderRadius: 'var(--radius-sm)',
              cursor: 'pointer',
              fontFamily: 'var(--font-mono)',
            }}
            title="Click to filter by correlation ID"
          >
            🔗 {log.correlation_id.slice(0, 8)}
          </button>
        ) : (
          <span style={{ color: 'var(--color-text-tertiary)', fontSize: 'var(--font-size-xs)' }}>—</span>
        )}
      </span>
    </div>
  );
}

export default function LogsPage() {
  return (
    <Suspense
      fallback={
        <div className="page-container">
          <div className="loading-page">
            <div className="loading-spinner" />
            Loading logs...
          </div>
        </div>
      }
    >
      <LogsPageContent />
    </Suspense>
  );
}
