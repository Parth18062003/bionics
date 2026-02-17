'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { getTask, getTaskEvents, listArtifacts } from '@/api/client';
import type { Task, TaskEvent, ArtifactSummary } from '@/api/types';
import { STATE_COLORS, STATE_LABELS } from '@/api/types';

export default function TaskDetailPage() {
    const params = useParams();
    const taskId = params.id as string;

    const [task, setTask] = useState<Task | null>(null);
    const [events, setEvents] = useState<TaskEvent[]>([]);
    const [artifacts, setArtifacts] = useState<ArtifactSummary[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        loadDetail();
        const interval = setInterval(loadDetail, 3000);
        return () => clearInterval(interval);
    }, [taskId]);

    async function loadDetail() {
        try {
            const [taskRes, eventsRes, artifactsRes] = await Promise.allSettled([
                getTask(taskId),
                getTaskEvents(taskId),
                listArtifacts(taskId),
            ]);

            if (taskRes.status === 'fulfilled') setTask(taskRes.value);
            else throw new Error('Task not found');

            if (eventsRes.status === 'fulfilled') setEvents(eventsRes.value);
            if (artifactsRes.status === 'fulfilled') setArtifacts(artifactsRes.value);
            setError(null);
        } catch (err: any) {
            setError(err.message || 'Failed to load task');
        } finally {
            setLoading(false);
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
