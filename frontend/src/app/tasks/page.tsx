'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { listTasks } from '@/api/client';
import type { Task } from '@/api/types';
import { STATE_COLORS, STATE_LABELS } from '@/api/types';

export default function TasksPage() {
    const [tasks, setTasks] = useState<Task[]>([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [stateFilter, setStateFilter] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const pageSize = 20;

    useEffect(() => {
        loadTasks();
        const interval = setInterval(loadTasks, 5000);
        return () => clearInterval(interval);
    }, [page, stateFilter]);

    async function loadTasks() {
        try {
            const res = await listTasks(page, pageSize, stateFilter || undefined);
            setTasks(res.tasks);
            setTotal(res.total);
            setError(null);
        } catch (err) {
            setError('Failed to load tasks');
        } finally {
            setLoading(false);
        }
    }

    const totalPages = Math.ceil(total / pageSize);

    const states = [
        '', 'SUBMITTED', 'VALIDATING', 'PLANNING', 'READY', 'ASSIGNED',
        'EXECUTING', 'AWAITING_REVIEW', 'APPROVED', 'COMPLETE', 'FAILED',
        'CANCELLED', 'ESCALATED', 'PAUSED',
    ];

    return (
        <div className="page-container animate-in">
            <div className="page-header">
                <div className="flex items-center justify-between">
                    <div>
                        <h1>Tasks</h1>
                        <p>{total} total tasks</p>
                    </div>
                    <Link href="/tasks/new" className="btn btn-primary">+ New Task</Link>
                </div>
            </div>

            {error && <div className="error-banner">⚠ {error}</div>}

            {/* Filters */}
            <div className="flex items-center gap-md mb-lg">
                <label className="text-sm text-secondary">Filter by state:</label>
                <select
                    className="form-select"
                    value={stateFilter}
                    onChange={(e) => { setStateFilter(e.target.value); setPage(1); }}
                    style={{ width: 'auto', minWidth: 160 }}
                >
                    <option value="">All States</option>
                    {states.filter(Boolean).map((s) => (
                        <option key={s} value={s}>{STATE_LABELS[s] || s}</option>
                    ))}
                </select>
            </div>

            {loading ? (
                <div className="loading-page"><div className="loading-spinner" /> Loading tasks...</div>
            ) : tasks.length === 0 ? (
                <div className="card">
                    <div className="empty-state">
                        <div className="empty-state-icon">📋</div>
                        <div className="empty-state-title">No tasks found</div>
                        <div className="empty-state-description">
                            {stateFilter ? `No tasks with state "${STATE_LABELS[stateFilter] || stateFilter}".` : 'Submit your first task to get started.'}
                        </div>
                        <Link href="/tasks/new" className="btn btn-primary">Create Task</Link>
                    </div>
                </div>
            ) : (
                <>
                    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Task</th>
                                    <th>State</th>
                                    <th>Environment</th>
                                    <th>Priority</th>
                                    <th>Tokens</th>
                                    <th>Created</th>
                                </tr>
                            </thead>
                            <tbody>
                                {tasks.map((task) => (
                                    <tr key={task.id} style={{ cursor: 'pointer' }} onClick={() => window.location.href = `/tasks/${task.id}`}>
                                        <td>
                                            <div style={{ fontWeight: 500 }}>{task.title}</div>
                                            <div className="text-xs text-secondary font-mono">{task.id.slice(0, 8)}…</div>
                                        </td>
                                        <td>
                                            <span
                                                className="badge"
                                                style={{
                                                    background: `${STATE_COLORS[task.current_state] || '#6b7280'}20`,
                                                    color: STATE_COLORS[task.current_state] || '#6b7280',
                                                }}
                                            >
                                                <span className="badge-dot" style={{ background: STATE_COLORS[task.current_state] || '#6b7280' }} />
                                                {STATE_LABELS[task.current_state] || task.current_state}
                                            </span>
                                        </td>
                                        <td>
                                            <span className="badge" style={{
                                                background: task.environment === 'PRODUCTION' ? 'var(--color-danger-muted)' : 'var(--color-info-muted)',
                                                color: task.environment === 'PRODUCTION' ? 'var(--color-danger)' : 'var(--color-info)',
                                            }}>
                                                {task.environment}
                                            </span>
                                        </td>
                                        <td className="text-sm">{task.priority}</td>
                                        <td className="text-sm font-mono">{task.tokens_used.toLocaleString()} / {task.token_budget.toLocaleString()}</td>
                                        <td className="text-sm text-secondary">{formatTime(task.created_at)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    {/* Pagination */}
                    {totalPages > 1 && (
                        <div className="flex items-center justify-between mt-xl">
                            <span className="text-sm text-secondary">
                                Page {page} of {totalPages}
                            </span>
                            <div className="flex gap-sm">
                                <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                                    ← Previous
                                </button>
                                <button className="btn btn-ghost btn-sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
                                    Next →
                                </button>
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}

function formatTime(iso: string): string {
    try {
        return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch { return iso; }
}
