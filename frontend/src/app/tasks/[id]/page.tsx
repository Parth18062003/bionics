'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { getTask, getTaskEvents, listArtifacts, executeTask, getExecutions } from '@/api/client';
import type { Task, TaskEvent, ArtifactSummary, ExecutionRecord } from '@/api/types';
import { STATE_COLORS, STATE_LABELS } from '@/api/types';
import {
  StateBadge,
  EnvBadge,
  Badge,
  ErrorBanner,
  LoadingPage,
  TokenBar,
} from '@/components/ui';
import { formatTimeWithSeconds } from '@/lib/utils';

export default function TaskDetailPage() {
  const params = useParams();
  const taskId = params.id as string;

  const [task, setTask]             = useState<Task | null>(null);
  const [events, setEvents]         = useState<TaskEvent[]>([]);
  const [artifacts, setArtifacts]   = useState<ArtifactSummary[]>([]);
  const [executions, setExecutions] = useState<ExecutionRecord[]>([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState<string | null>(null);
  const [executing, setExecuting]   = useState(false);
  const [execResult, setExecResult] = useState<string | null>(null);
  const [expandedCode, setExpandedCode] = useState<Record<string, boolean>>({});

  useEffect(() => {
    loadDetail();
    const interval = setInterval(loadDetail, 3000);
    return () => clearInterval(interval);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId]);

  async function loadDetail() {
    try {
      const [taskRes, eventsRes, artifactsRes, execRes] = await Promise.allSettled([
        getTask(taskId),
        getTaskEvents(taskId),
        listArtifacts(taskId),
        getExecutions(taskId),
      ]);

      if (taskRes.status === 'fulfilled') setTask(taskRes.value);
      else throw new Error('Task not found');

      if (eventsRes.status === 'fulfilled')   setEvents(eventsRes.value);
      if (artifactsRes.status === 'fulfilled') setArtifacts(artifactsRes.value);
      if (execRes.status === 'fulfilled')     setExecutions(execRes.value);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load task');
    } finally {
      setLoading(false);
    }
  }

  async function handleExecute() {
    setExecuting(true);
    setExecResult(null);
    try {
      const res = await executeTask(taskId);
      setExecResult(
        res.status === 'completed'
          ? 'Execution completed successfully!'
          : `Status: ${res.status}`
      );
      loadDetail();
    } catch (err: unknown) {
      const detail = err instanceof Error ? err.message : 'Unknown error';
      setExecResult(`Execution failed: ${detail}`);
    } finally {
      setExecuting(false);
    }
  }

  if (loading) return <LoadingPage message="Loading task…" />;

  if (error || !task) {
    return (
      <div className="page-container">
        <ErrorBanner message={error ?? 'Task not found'} />
        <Link href="/tasks" className="btn btn-ghost">
          ← Back to Tasks
        </Link>
      </div>
    );
  }

  const canExecute  = ['SUBMITTED', 'PARSED', 'PLANNED', 'AGENT_ASSIGNED', 'APPROVED'].includes(
    task.current_state
  );
  const execFailed  = execResult?.includes('failed') ?? false;

  return (
    <div className="page-container animate-in">
      {/* ── Breadcrumb ── */}
      <div className="flex items-center gap-md mb-lg">
        <Link href="/tasks" className="btn btn-ghost btn-sm" aria-label="Back to tasks list">
          ← Back
        </Link>
      </div>

      {/* ── Page title row ── */}
      <div className="flex items-start justify-between mb-2xl" style={{ gap: 'var(--space-lg)', flexWrap: 'wrap' }}>
        <div style={{ minWidth: 0 }}>
          <h1
            className="truncate"
            style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 700, marginBottom: 'var(--space-sm)' }}
          >
            {task.title}
          </h1>
          <div className="flex items-center gap-md flex-wrap">
            <span className="text-sm font-mono text-secondary">{task.id}</span>
            <EnvBadge env={task.environment} />
          </div>
        </div>

        <div className="flex items-center gap-md flex-wrap">
          {canExecute && (
            <button
              className="btn btn-primary"
              disabled={executing}
              onClick={handleExecute}
              aria-label={executing ? 'Executing task…' : 'Execute task'}
            >
              {executing ? (
                <>
                  <div className="loading-spinner" style={{ width: 16, height: 16 }} aria-hidden="true" />
                  Executing…
                </>
              ) : (
                '▶ Execute'
              )}
            </button>
          )}
          <StateBadge
            state={task.current_state}
            stateColors={STATE_COLORS}
            stateLabels={STATE_LABELS}
          />
        </div>
      </div>

      {/* ── Execution result banner ── */}
      {execResult && (
        <div
          className="mb-xl"
          style={{
            padding: 'var(--space-md) var(--space-lg)',
            borderRadius: 'var(--radius-md)',
            background: execFailed ? 'var(--color-danger-muted)' : 'var(--color-success-muted)',
            color: execFailed ? 'var(--color-danger)' : 'var(--color-success)',
            fontSize: 'var(--font-size-sm)',
            border: `1px solid ${execFailed ? 'rgba(239,68,68,0.2)' : 'rgba(16,185,129,0.2)'}`,
          }}
          role="status"
          aria-live="polite"
        >
          {execResult}
        </div>
      )}

      {/* ── Metadata Grid ── */}
      <div className="grid-stats mb-2xl">
        <div className="card" style={{ padding: 'var(--space-lg)' }}>
          <div className="text-xs text-secondary mb-xs">Priority</div>
          <div style={{ fontSize: 'var(--font-size-xl)', fontWeight: 700 }}>{task.priority}</div>
        </div>

        <div className="card" style={{ padding: 'var(--space-lg)' }}>
          <div className="text-xs text-secondary mb-xs">Token Usage</div>
          <TokenBar used={task.tokens_used} budget={task.token_budget} />
        </div>

        <div className="card" style={{ padding: 'var(--space-lg)' }}>
          <div className="text-xs text-secondary mb-xs">Retries</div>
          <div style={{ fontSize: 'var(--font-size-xl)', fontWeight: 700 }}>{task.retry_count}</div>
        </div>

        <div className="card" style={{ padding: 'var(--space-lg)' }}>
          <div className="text-xs text-secondary mb-xs">Created By</div>
          <div className="font-medium">{task.created_by ?? '—'}</div>
          <div className="text-xs text-secondary mt-xs">
            {formatTimeWithSeconds(task.created_at)}
          </div>
        </div>
      </div>

      {/* ── Description ── */}
      {task.description && (
        <div className="card mb-2xl">
          <h2 style={{ fontSize: 'var(--font-size-base)', fontWeight: 600, marginBottom: 'var(--space-md)' }}>
            Description
          </h2>
          <p className="text-secondary" style={{ lineHeight: 1.7 }}>
            {task.description}
          </p>
        </div>
      )}

      {/* ── Execution Records ── */}
      {executions.length > 0 && (
        <div className="card mb-2xl">
          <h2 style={{ fontSize: 'var(--font-size-base)', fontWeight: 600, marginBottom: 'var(--space-xl)' }}>
            Execution Records ({executions.length})
          </h2>

          <div className="flex flex-col gap-md">
            {executions.map((exec) => {
              const execColor =
                exec.status === 'completed'
                  ? 'var(--color-success)'
                  : exec.status === 'failed'
                  ? 'var(--color-danger)'
                  : 'var(--color-warning)';
              const execBg =
                exec.status === 'completed'
                  ? 'var(--color-success-muted)'
                  : exec.status === 'failed'
                  ? 'var(--color-danger-muted)'
                  : 'var(--color-warning-muted)';
              const isFabric = exec.platform === 'Microsoft Fabric';

              return (
                <div
                  key={exec.id}
                  style={{
                    padding: 'var(--space-lg)',
                    background: 'var(--color-bg-tertiary)',
                    borderRadius: 'var(--radius-md)',
                    borderLeft: `3px solid ${execColor}`,
                  }}
                >
                  {/* Header row */}
                  <div className="flex items-center justify-between mb-md flex-wrap" style={{ gap: 'var(--space-sm)' }}>
                    <div className="flex items-center gap-md flex-wrap">
                      <Badge bg={execBg} color={execColor}>
                        {exec.status.toUpperCase()}
                      </Badge>
                      <span className="text-xs text-secondary">{exec.environment}</span>
                      {exec.platform && (
                        <Badge
                          bg={isFabric ? 'rgba(59,130,246,0.12)' : 'rgba(245,158,11,0.12)'}
                          color={isFabric ? '#60a5fa' : '#fbbf24'}
                        >
                          {isFabric ? '🔷' : '⚡'} {exec.platform}
                        </Badge>
                      )}
                    </div>
                    <div className="text-xs text-secondary font-mono">
                      {exec.job_id && <span>Job: {exec.job_id} · </span>}
                      {exec.duration_ms != null && <span>{exec.duration_ms}ms · </span>}
                      {formatTimeWithSeconds(exec.created_at)}
                    </div>
                  </div>

                  {/* Collapsible generated code */}
                  {exec.code && (
                    <div className="mb-sm">
                      <button
                        type="button"
                        className="btn btn-ghost btn-sm"
                        style={{ marginBottom: 'var(--space-xs)', fontSize: 'var(--font-size-xs)' }}
                        aria-expanded={expandedCode[exec.id] ?? false}
                        onClick={() =>
                          setExpandedCode((prev) => ({ ...prev, [exec.id]: !prev[exec.id] }))
                        }
                      >
                        <span
                          style={{
                            transform: expandedCode[exec.id] ? 'rotate(90deg)' : 'none',
                            transition: 'transform 0.15s',
                            display: 'inline-block',
                          }}
                          aria-hidden="true"
                        >
                          ▶
                        </span>
                        Generated Code{exec.language ? ` (${exec.language})` : ''}
                      </button>
                      {expandedCode[exec.id] && (
                        <pre
                          style={{
                            padding: 'var(--space-md)',
                            background: 'var(--color-bg-primary)',
                            borderRadius: 'var(--radius-sm)',
                            fontFamily: 'var(--font-mono)',
                            fontSize: 'var(--font-size-xs)',
                            color: 'var(--color-accent)',
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word',
                            maxHeight: 400,
                            overflow: 'auto',
                            border: '1px solid var(--color-border)',
                          }}
                        >
                          {exec.code}
                        </pre>
                      )}
                    </div>
                  )}

                  {exec.output && (
                    <div className="mb-sm">
                      <div className="text-xs text-secondary mb-xs font-medium">Output</div>
                      <pre
                        style={{
                          padding: 'var(--space-md)',
                          background: 'var(--color-bg-primary)',
                          borderRadius: 'var(--radius-sm)',
                          fontFamily: 'var(--font-mono)',
                          fontSize: 'var(--font-size-xs)',
                          color: 'var(--color-success)',
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                          maxHeight: 200,
                          overflow: 'auto',
                        }}
                      >
                        {exec.output}
                      </pre>
                    </div>
                  )}

                  {exec.error && (
                    <div>
                      <div className="text-xs text-secondary mb-xs font-medium">Error</div>
                      <pre
                        style={{
                          padding: 'var(--space-md)',
                          background: 'var(--color-bg-primary)',
                          borderRadius: 'var(--radius-sm)',
                          fontFamily: 'var(--font-mono)',
                          fontSize: 'var(--font-size-xs)',
                          color: 'var(--color-danger)',
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                          maxHeight: 200,
                          overflow: 'auto',
                        }}
                      >
                        {exec.error}
                      </pre>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── State Timeline + Artifacts (responsive 2-col) ── */}
      <div className="grid-2col">
        {/* Event Timeline */}
        <section className="card" aria-labelledby="timeline-heading">
          <h2
            id="timeline-heading"
            style={{ fontSize: 'var(--font-size-base)', fontWeight: 600, marginBottom: 'var(--space-xl)' }}
          >
            State Timeline ({events.length} event{events.length !== 1 ? 's' : ''})
          </h2>

          {events.length === 0 ? (
            <p className="text-sm text-secondary">No state transitions recorded yet.</p>
          ) : (
            <div className="timeline">
              {events.map((event) => (
                <div key={event.id} className="timeline-item">
                  <div
                    className="timeline-dot"
                    style={{ borderColor: STATE_COLORS[event.to_state] ?? '#6b7280' }}
                    aria-hidden="true"
                  />
                  <div className="timeline-content">
                    <div className="flex items-center justify-between mb-xs">
                      <div className="timeline-label">
                        <span style={{ color: STATE_COLORS[event.from_state] ?? '#6b7280' }}>
                          {STATE_LABELS[event.from_state] ?? event.from_state}
                        </span>
                        {' → '}
                        <span style={{ color: STATE_COLORS[event.to_state] ?? '#6b7280' }}>
                          {STATE_LABELS[event.to_state] ?? event.to_state}
                        </span>
                      </div>
                      <span className="text-xs text-secondary">#{event.sequence_num}</span>
                    </div>
                    {event.reason && (
                      <div className="text-xs text-secondary mt-xs">{event.reason}</div>
                    )}
                    <div className="timeline-time mt-xs">
                      {formatTimeWithSeconds(event.created_at)} · by {event.triggered_by ?? 'system'}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Artifacts */}
        <section className="card" aria-labelledby="artifacts-heading">
          <h2
            id="artifacts-heading"
            style={{ fontSize: 'var(--font-size-base)', fontWeight: 600, marginBottom: 'var(--space-xl)' }}
          >
            Artifacts ({artifacts.length})
          </h2>

          {artifacts.length === 0 ? (
            <p className="text-sm text-secondary">No artifacts generated yet.</p>
          ) : (
            <div className="flex flex-col gap-sm" role="list" aria-label="Task artifacts">
              {artifacts.map((artifact) => (
                <Link
                  key={artifact.id}
                  href={`/artifacts/${taskId}/${artifact.id}`}
                  role="listitem"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: 'var(--space-md) var(--space-lg)',
                    borderRadius: 'var(--radius-md)',
                    background: 'var(--color-bg-tertiary)',
                    textDecoration: 'none',
                    color: 'var(--color-text-primary)',
                    transition: 'all var(--transition-fast)',
                    gap: 'var(--space-md)',
                  }}
                >
                  <div style={{ minWidth: 0 }}>
                    <div className="font-medium truncate">{artifact.name}</div>
                    <div className="text-xs text-secondary mt-xs">
                      {artifact.artifact_type} · {formatTimeWithSeconds(artifact.created_at)}
                    </div>
                  </div>
                  <span className="text-sm text-secondary" aria-hidden="true">→</span>
                </Link>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
