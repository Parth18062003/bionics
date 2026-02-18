'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { getTask, getTaskEvents, listArtifacts, executeTask, getExecutions } from '@/api/client';
import type { Task, TaskEvent, ArtifactSummary, ExecutionRecord } from '@/api/types';
import { STATE_COLORS, STATE_LABELS } from '@/api/types';

export default function TaskDetailPage() {
    const params = useParams();
    const taskId = params.id as string;

    const [task, setTask] = useState<Task | null>(null);
    const [events, setEvents] = useState<TaskEvent[]>([]);
    const [artifacts, setArtifacts] = useState<ArtifactSummary[]>([]);
    const [executions, setExecutions] = useState<ExecutionRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [executing, setExecuting] = useState(false);
    const [execResult, setExecResult] = useState<string | null>(null);
    const [expandedCode, setExpandedCode] = useState<Record<string, boolean>>({});

    useEffect(() => {
        loadDetail();
        const interval = setInterval(loadDetail, 3000);
        return () => clearInterval(interval);
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

            if (eventsRes.status === 'fulfilled') setEvents(eventsRes.value);
            if (artifactsRes.status === 'fulfilled') setArtifacts(artifactsRes.value);
            if (execRes.status === 'fulfilled') setExecutions(execRes.value);
            setError(null);
        } catch (err: any) {
            setError(err.message || 'Failed to load task');
        } finally {
            setLoading(false);
        }
    }

    async function handleExecute() {
        setExecuting(true);
        setExecResult(null);
        try {
            const res = await executeTask(taskId);
            setExecResult(res.status === 'completed' ? 'Execution completed successfully!' : `Status: ${res.status}`);
            loadDetail(); // Refresh data
        } catch (err: any) {
            setExecResult(`Execution failed: ${err.detail || err.message}`);
        } finally {
            setExecuting(false);
        }
    }

    if (loading) {
        return <div className="loading-page"><div className="loading-spinner" /> Loading task...</div>;
    }

    if (error || !task) {
        return (
            <div className="page-container">
                <div className="error-banner">⚠ {error || 'Task not found'}</div>
                <Link href="/tasks" className="btn btn-ghost">← Back to Tasks</Link>
            </div>
        );
    }

    const stateColor = STATE_COLORS[task.current_state] || '#6b7280';
    const tokenPct = task.token_budget > 0 ? Math.round((task.tokens_used / task.token_budget) * 100) : 0;
    const canExecute = ['SUBMITTED', 'PARSED', 'PLANNED', 'AGENT_ASSIGNED', 'APPROVED'].includes(task.current_state);

    return (
        <div className="page-container animate-in">
            {/* Header */}
            <div className="flex items-center gap-md mb-lg">
                <Link href="/tasks" className="btn btn-ghost btn-sm">← Back</Link>
            </div>

            <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-2xl)' }}>
                <div>
                    <h1 style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 700, marginBottom: 'var(--space-sm)' }}>
                        {task.title}
                    </h1>
                    <div className="flex items-center gap-md">
                        <span className="text-sm font-mono text-secondary">{task.id}</span>
                        <span className="badge" style={{
                            background: task.environment === 'PRODUCTION' ? 'var(--color-danger-muted)' : 'var(--color-info-muted)',
                            color: task.environment === 'PRODUCTION' ? 'var(--color-danger)' : 'var(--color-info)',
                        }}>
                            {task.environment}
                        </span>
                    </div>
                </div>
                <div className="flex items-center gap-md">
                    {canExecute && (
                        <button
                            className="btn btn-primary"
                            disabled={executing}
                            onClick={handleExecute}
                        >
                            {executing ? (
                                <><div className="loading-spinner" style={{ width: 16, height: 16 }} /> Executing...</>
                            ) : (
                                '▶ Execute'
                            )}
                        </button>
                    )}
                    <span
                        className="badge"
                        style={{
                            background: `${stateColor}20`,
                            color: stateColor,
                            fontSize: 'var(--font-size-sm)',
                            padding: '6px 16px',
                        }}
                    >
                        <span className="badge-dot" style={{ background: stateColor, width: 8, height: 8 }} />
                        {STATE_LABELS[task.current_state] || task.current_state}
                    </span>
                </div>
            </div>

            {/* Execution result banner */}
            {execResult && (
                <div style={{
                    marginBottom: 'var(--space-xl)',
                    padding: 'var(--space-md) var(--space-lg)',
                    borderRadius: 'var(--radius-md)',
                    background: execResult.includes('failed') ? 'var(--color-danger-muted)' : 'var(--color-success-muted)',
                    color: execResult.includes('failed') ? 'var(--color-danger)' : 'var(--color-success)',
                    fontSize: 'var(--font-size-sm)',
                }}>
                    {execResult}
                </div>
            )}

            {/* Metadata Grid */}
            <div className="grid-stats" style={{ marginBottom: 'var(--space-2xl)' }}>
                <div className="card" style={{ padding: 'var(--space-lg)' }}>
                    <div className="text-xs text-secondary" style={{ marginBottom: 'var(--space-xs)' }}>Priority</div>
                    <div style={{ fontSize: 'var(--font-size-xl)', fontWeight: 700 }}>{task.priority}</div>
                </div>
                <div className="card" style={{ padding: 'var(--space-lg)' }}>
                    <div className="text-xs text-secondary" style={{ marginBottom: 'var(--space-xs)' }}>Token Usage</div>
                    <div style={{ fontSize: 'var(--font-size-xl)', fontWeight: 700 }}>{tokenPct}%</div>
                    <div style={{
                        marginTop: 'var(--space-sm)',
                        height: 4,
                        borderRadius: 2,
                        background: 'var(--color-bg-tertiary)',
                        overflow: 'hidden',
                    }}>
                        <div style={{
                            width: `${Math.min(tokenPct, 100)}%`,
                            height: '100%',
                            borderRadius: 2,
                            background: tokenPct > 90 ? 'var(--color-danger)' : tokenPct > 70 ? 'var(--color-warning)' : 'var(--color-accent)',
                            transition: 'width var(--transition-slow)',
                        }} />
                    </div>
                    <div className="text-xs text-secondary" style={{ marginTop: 'var(--space-xs)' }}>
                        {task.tokens_used.toLocaleString()} / {task.token_budget.toLocaleString()}
                    </div>
                </div>
                <div className="card" style={{ padding: 'var(--space-lg)' }}>
                    <div className="text-xs text-secondary" style={{ marginBottom: 'var(--space-xs)' }}>Retries</div>
                    <div style={{ fontSize: 'var(--font-size-xl)', fontWeight: 700 }}>{task.retry_count}</div>
                </div>
                <div className="card" style={{ padding: 'var(--space-lg)' }}>
                    <div className="text-xs text-secondary" style={{ marginBottom: 'var(--space-xs)' }}>Created By</div>
                    <div style={{ fontSize: 'var(--font-size-base)', fontWeight: 500 }}>{task.created_by || '—'}</div>
                    <div className="text-xs text-secondary" style={{ marginTop: 'var(--space-xs)' }}>
                        {formatTime(task.created_at)}
                    </div>
                </div>
            </div>

            {/* Description */}
            {task.description && (
                <div className="card" style={{ marginBottom: 'var(--space-2xl)' }}>
                    <h3 style={{ fontSize: 'var(--font-size-base)', fontWeight: 600, marginBottom: 'var(--space-md)' }}>Description</h3>
                    <p className="text-secondary" style={{ lineHeight: 1.7 }}>{task.description}</p>
                </div>
            )}

            {/* Execution Records */}
            {executions.length > 0 && (
                <div className="card" style={{ marginBottom: 'var(--space-2xl)' }}>
                    <h3 style={{ fontSize: 'var(--font-size-base)', fontWeight: 600, marginBottom: 'var(--space-xl)' }}>
                        Execution Records ({executions.length})
                    </h3>
                    <div className="flex flex-col gap-md">
                        {executions.map((exec) => (
                            <div
                                key={exec.id}
                                style={{
                                    padding: 'var(--space-lg)',
                                    background: 'var(--color-bg-tertiary)',
                                    borderRadius: 'var(--radius-md)',
                                    borderLeft: `3px solid ${exec.status === 'completed' ? 'var(--color-success)' : exec.status === 'failed' ? 'var(--color-danger)' : 'var(--color-warning)'}`,
                                }}
                            >
                                <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-md)' }}>
                                    <div className="flex items-center gap-md">
                                        <span className="badge" style={{
                                            background: exec.status === 'completed' ? 'var(--color-success-muted)' : exec.status === 'failed' ? 'var(--color-danger-muted)' : 'var(--color-warning-muted)',
                                            color: exec.status === 'completed' ? 'var(--color-success)' : exec.status === 'failed' ? 'var(--color-danger)' : 'var(--color-warning)',
                                        }}>
                                            {exec.status.toUpperCase()}
                                        </span>
                                        <span className="text-xs text-secondary">{exec.environment}</span>
                                        {/* Platform badge */}
                                        {exec.platform && (
                                            <span className="badge" style={{
                                                background: exec.platform === 'Microsoft Fabric' ? 'rgba(59,130,246,0.12)' : 'rgba(245,158,11,0.12)',
                                                color: exec.platform === 'Microsoft Fabric' ? '#60a5fa' : '#fbbf24',
                                                fontSize: 'var(--font-size-xs)',
                                            }}>
                                                {exec.platform === 'Microsoft Fabric' ? '🔷' : '⚡'} {exec.platform}
                                            </span>
                                        )}
                                    </div>
                                    <div className="text-xs text-secondary">
                                        {exec.job_id && <span className="font-mono">Job: {exec.job_id} · </span>}
                                        {exec.duration_ms != null && <span>{exec.duration_ms}ms · </span>}
                                        {formatTime(exec.created_at)}
                                    </div>
                                </div>

                                {/* Generated Code (collapsible) */}
                                {exec.code && (
                                    <div style={{ marginBottom: 'var(--space-sm)' }}>
                                        <button
                                            type="button"
                                            className="btn btn-ghost btn-sm"
                                            style={{
                                                padding: '2px 8px',
                                                marginBottom: 'var(--space-xs)',
                                                fontSize: 'var(--font-size-xs)',
                                                fontWeight: 500,
                                                display: 'flex',
                                                alignItems: 'center',
                                                gap: 'var(--space-xs)',
                                            }}
                                            onClick={() =>
                                                setExpandedCode((prev) => ({
                                                    ...prev,
                                                    [exec.id]: !prev[exec.id],
                                                }))
                                            }
                                        >
                                            <span style={{
                                                transform: expandedCode[exec.id] ? 'rotate(90deg)' : 'rotate(0deg)',
                                                transition: 'transform 0.15s',
                                                display: 'inline-block',
                                            }}>▶</span>
                                            Generated Code{exec.language ? ` (${exec.language})` : ''}
                                        </button>
                                        {expandedCode[exec.id] && (
                                            <pre style={{
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
                                            }}>
                                                {exec.code}
                                            </pre>
                                        )}
                                    </div>
                                )}

                                {exec.output && (
                                    <div style={{ marginBottom: 'var(--space-sm)' }}>
                                        <div className="text-xs text-secondary" style={{ marginBottom: 'var(--space-xs)', fontWeight: 500 }}>Output</div>
                                        <pre style={{
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
                                        }}>
                                            {exec.output}
                                        </pre>
                                    </div>
                                )}
                                {exec.error && (
                                    <div>
                                        <div className="text-xs text-secondary" style={{ marginBottom: 'var(--space-xs)', fontWeight: 500 }}>Error</div>
                                        <pre style={{
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
                                        }}>
                                            {exec.error}
                                        </pre>
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Two-column: Events + Artifacts */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-xl)' }}>
                {/* Event Timeline */}
                <div className="card">
                    <h3 style={{ fontSize: 'var(--font-size-base)', fontWeight: 600, marginBottom: 'var(--space-xl)' }}>
                        State Timeline ({events.length} events)
                    </h3>
                    {events.length === 0 ? (
                        <div className="text-sm text-secondary">No state transitions recorded yet.</div>
                    ) : (
                        <div className="timeline">
                            {events.map((event) => (
                                <div key={event.id} className="timeline-item">
                                    <div
                                        className="timeline-dot"
                                        style={{ borderColor: STATE_COLORS[event.to_state] || '#6b7280' }}
                                    />
                                    <div className="timeline-content">
                                        <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-xs)' }}>
                                            <div className="timeline-label">
                                                <span style={{ color: STATE_COLORS[event.from_state] || '#6b7280' }}>
                                                    {STATE_LABELS[event.from_state] || event.from_state}
                                                </span>
                                                {' → '}
                                                <span style={{ color: STATE_COLORS[event.to_state] || '#6b7280' }}>
                                                    {STATE_LABELS[event.to_state] || event.to_state}
                                                </span>
                                            </div>
                                            <span className="text-xs text-secondary">#{event.sequence_num}</span>
                                        </div>
                                        {event.reason && (
                                            <div className="text-xs text-secondary" style={{ marginTop: 'var(--space-xs)' }}>
                                                {event.reason}
                                            </div>
                                        )}
                                        <div className="timeline-time" style={{ marginTop: 'var(--space-xs)' }}>
                                            {formatTime(event.created_at)} · by {event.triggered_by || 'system'}
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Artifacts */}
                <div className="card">
                    <h3 style={{ fontSize: 'var(--font-size-base)', fontWeight: 600, marginBottom: 'var(--space-xl)' }}>
                        Artifacts ({artifacts.length})
                    </h3>
                    {artifacts.length === 0 ? (
                        <div className="text-sm text-secondary">No artifacts generated yet.</div>
                    ) : (
                        <div className="flex flex-col gap-sm">
                            {artifacts.map((artifact) => (
                                <Link
                                    key={artifact.id}
                                    href={`/artifacts/${taskId}/${artifact.id}`}
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
                                    }}
                                >
                                    <div>
                                        <div style={{ fontWeight: 500, fontSize: 'var(--font-size-base)' }}>{artifact.name}</div>
                                        <div className="text-xs text-secondary">{artifact.artifact_type} · {formatTime(artifact.created_at)}</div>
                                    </div>
                                    <span className="text-sm text-secondary">→</span>
                                </Link>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

function formatTime(iso: string): string {
    try {
        return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch { return iso; }
}
