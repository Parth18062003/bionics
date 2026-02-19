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
  CodeViewer,
  PhaseVisualization,
  ErrorDiagnostics,
  OutputVisualization,
} from '@/components/ui';
import { formatTimeWithSeconds } from '@/lib/utils';

type TabId = 'overview' | 'code' | 'output' | 'artifacts' | 'logs' | 'history';

const TABS: { id: TabId; label: string; icon: string }[] = [
  { id: 'overview', label: 'Overview', icon: '📊' },
  { id: 'code', label: 'Code', icon: '💻' },
  { id: 'output', label: 'Output', icon: '📄' },
  { id: 'artifacts', label: 'Artifacts', icon: '📦' },
  { id: 'logs', label: 'Logs', icon: '📋' },
  { id: 'history', label: 'History', icon: '🕐' },
];

const ARTIFACT_DISPLAY: Record<string, { icon: string; color: string }> = {
  pipeline_definition:  { icon: '🔀', color: '#a78bfa' },
  job_config:           { icon: '⏱', color: '#fb923c' },
  ingestion_config:     { icon: '📥', color: '#22d3ee' },
  optimized_code:       { icon: '✨', color: '#10b981' },
  optimization_report:  { icon: '📊', color: '#34d399' },
  source_code:          { icon: '💻', color: '#818cf8' },
  validation_report:    { icon: '🛡️', color: '#f59e0b' },
};

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
  const [activeTab, setActiveTab]   = useState<TabId>('overview');

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
  const hasCode     = executions.some(e => e.code);
  const hasOutput   = executions.some(e => e.output);
  const hasErrors   = executions.some(e => e.error);

  const latestExecution = executions[0];
  const latestCode = latestExecution?.code;
  const latestOutput = latestExecution?.output;
  const latestError = latestExecution?.error;
  const codeLanguage = latestExecution?.language || 'python';

  return (
    <div className="page-container animate-in">
      {/* ── Breadcrumb ── */}
      <div className="flex items-center gap-md mb-lg">
        <Link href="/tasks" className="btn btn-ghost btn-sm" aria-label="Back to tasks list">
          ← Back
        </Link>
      </div>

      {/* ── Page title row ── */}
      <div className="flex items-start justify-between mb-xl" style={{ gap: 'var(--space-lg)', flexWrap: 'wrap' }}>
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
            {task.platform && (
              <Badge
                bg={task.platform === 'fabric' ? 'rgba(59,130,246,0.12)' : 'rgba(245,158,11,0.12)'}
                color={task.platform === 'fabric' ? '#60a5fa' : '#fbbf24'}
              >
                {task.platform === 'fabric' ? '🔷 Fabric' : '⚡ Databricks'}
              </Badge>
            )}
            {task.task_mode && (
              <Badge bg="var(--color-accent-muted)" color="var(--color-accent)">
                {task.task_mode.replace('_', ' ')}
              </Badge>
            )}
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

      {/* ── Tabs ── */}
      <div
        style={{
          display: 'flex',
          gap: 'var(--space-xs)',
          marginBottom: 'var(--space-lg)',
          borderBottom: '1px solid var(--color-border)',
          paddingBottom: 'var(--space-sm)',
        }}
      >
        {TABS.map(tab => {
          const isDisabled = 
            (tab.id === 'code' && !hasCode) ||
            (tab.id === 'output' && !hasOutput);
          
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              disabled={isDisabled}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-xs)',
                padding: 'var(--space-sm) var(--space-md)',
                borderRadius: 'var(--radius-sm) var(--radius-sm) 0 0',
                border: 'none',
                borderBottom: activeTab === tab.id ? '2px solid var(--color-accent)' : '2px solid transparent',
                background: activeTab === tab.id ? 'var(--color-bg-secondary)' : 'transparent',
                color: isDisabled ? 'var(--color-text-tertiary)' : activeTab === tab.id ? 'var(--color-accent)' : 'var(--color-text-secondary)',
                cursor: isDisabled ? 'not-allowed' : 'pointer',
                fontSize: 'var(--font-size-sm)',
                fontWeight: activeTab === tab.id ? 600 : 400,
                marginBottom: -1,
              }}
            >
              <span aria-hidden="true">{tab.icon}</span>
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* ── Tab Content ── */}
      <div style={{ minHeight: 400 }}>
        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <div>
            {/* Phase Visualization */}
            <div className="mb-xl">
              <PhaseVisualization currentState={task.current_state} events={events} />
            </div>

            {/* Metadata Grid */}
            <div className="grid-stats mb-xl">
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

            {/* Description */}
            {task.description && (
              <div className="card mb-xl">
                <h2 style={{ fontSize: 'var(--font-size-base)', fontWeight: 600, marginBottom: 'var(--space-md)' }}>
                  Description
                </h2>
                <p className="text-secondary" style={{ lineHeight: 1.7 }}>
                  {task.description}
                </p>
              </div>
            )}

            {/* Latest Error */}
            {hasErrors && latestError && (
              <div className="mb-xl">
                <h2 style={{ fontSize: 'var(--font-size-base)', fontWeight: 600, marginBottom: 'var(--space-md)' }}>
                  Latest Error
                </h2>
                <ErrorDiagnostics error={latestError} onRetry={canExecute ? handleExecute : undefined} />
              </div>
            )}
          </div>
        )}

        {/* Code Tab */}
        {activeTab === 'code' && latestCode && (
          <div>
            <CodeViewer
              code={latestCode}
              language={codeLanguage}
              maxHeight={600}
              showLineNumbers
            />
            
            {executions.length > 1 && (
              <div className="mt-xl">
                <h3 style={{ fontSize: 'var(--font-size-base)', fontWeight: 600, marginBottom: 'var(--space-md)' }}>
                  Previous Executions
                </h3>
                {executions.slice(1).map((exec, i) => (
                  exec.code && (
                    <div key={exec.id} className="mb-md">
                      <CodeViewer
                        code={exec.code}
                        language={exec.language || 'python'}
                        maxHeight={300}
                        showLineNumbers
                        filename={`Execution #${executions.length - i}`}
                        collapsible
                        defaultCollapsed
                      />
                    </div>
                  )
                ))}
              </div>
            )}
          </div>
        )}

        {/* Output Tab */}
        {activeTab === 'output' && (
          <div>
            {latestOutput ? (
              <OutputVisualization output={latestOutput} title="Execution Output" />
            ) : (
              <div className="card" style={{ padding: 'var(--space-xl)', textAlign: 'center' }}>
                <p className="text-secondary">No output available yet.</p>
              </div>
            )}
            
            {executions.length > 1 && (
              <div className="mt-xl">
                <h3 style={{ fontSize: 'var(--font-size-base)', fontWeight: 600, marginBottom: 'var(--space-md)' }}>
                  Previous Outputs
                </h3>
                {executions.slice(1).filter(e => e.output).map((exec, i) => (
                  <div key={exec.id} className="mb-md">
                    <OutputVisualization
                      output={exec.output}
                      title={`Execution #${executions.length - i} - ${formatTimeWithSeconds(exec.created_at)}`}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Artifacts Tab */}
        {activeTab === 'artifacts' && (
          <div className="card">
            <h2 style={{ fontSize: 'var(--font-size-base)', fontWeight: 600, marginBottom: 'var(--space-lg)' }}>
              Generated Artifacts ({artifacts.length})
            </h2>

            {artifacts.length === 0 ? (
              <p className="text-sm text-secondary">No artifacts generated yet.</p>
            ) : (
              <div className="flex flex-col gap-sm" role="list" aria-label="Task artifacts">
                {artifacts.map((artifact) => {
                  const display = ARTIFACT_DISPLAY[artifact.artifact_type];
                  return (
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
                      <div className="flex items-center gap-md" style={{ minWidth: 0 }}>
                        {display && (
                          <span style={{ fontSize: '1rem', flexShrink: 0 }} aria-hidden="true">
                            {display.icon}
                          </span>
                        )}
                        <div style={{ minWidth: 0 }}>
                          <div className="font-medium truncate">{artifact.name}</div>
                          <div className="text-xs mt-xs" style={{ color: display?.color ?? 'var(--color-text-secondary)' }}>
                            {artifact.artifact_type} · {formatTimeWithSeconds(artifact.created_at)}
                          </div>
                        </div>
                      </div>
                      <span className="text-sm text-secondary" aria-hidden="true">→</span>
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Logs Tab */}
        {activeTab === 'logs' && (
          <div className="card">
            <h2 style={{ fontSize: 'var(--font-size-base)', fontWeight: 600, marginBottom: 'var(--space-lg)' }}>
              Execution Logs
            </h2>
            
            {executions.length === 0 ? (
              <p className="text-sm text-secondary">No execution logs available.</p>
            ) : (
              <div className="flex flex-col gap-md">
                {executions.map((exec) => (
                  <div
                    key={exec.id}
                    style={{
                      padding: 'var(--space-md)',
                      background: 'var(--color-bg-tertiary)',
                      borderRadius: 'var(--radius-md)',
                      fontFamily: 'var(--font-mono)',
                      fontSize: 'var(--font-size-xs)',
                    }}
                  >
                    <div className="flex items-center justify-between mb-sm">
                      <div className="flex items-center gap-sm">
                        <Badge
                          bg={exec.status === 'completed' ? 'var(--color-success-muted)' : 'var(--color-danger-muted)'}
                          color={exec.status === 'completed' ? 'var(--color-success)' : 'var(--color-danger)'}
                        >
                          {exec.status.toUpperCase()}
                        </Badge>
                        <span className="text-xs text-secondary">{exec.environment}</span>
                      </div>
                      <span className="text-xs text-secondary">
                        {exec.duration_ms != null && `${exec.duration_ms}ms · `}
                        {formatTimeWithSeconds(exec.created_at)}
                      </span>
                    </div>
                    {exec.job_id && (
                      <div className="text-xs text-secondary">Job ID: {exec.job_id}</div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* History Tab */}
        {activeTab === 'history' && (
          <div className="card">
            <h2 style={{ fontSize: 'var(--font-size-base)', fontWeight: 600, marginBottom: 'var(--space-lg)' }}>
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
          </div>
        )}
      </div>
    </div>
  );
}
