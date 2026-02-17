'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { listTasks, listApprovals, checkHealth } from '@/api/client';
import type { Task, Approval, HealthResponse } from '@/api/types';
import { STATE_COLORS, STATE_LABELS } from '@/api/types';

export default function DashboardPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadDashboard();
    const interval = setInterval(loadDashboard, 5000);
    return () => clearInterval(interval);
  }, []);

  async function loadDashboard() {
    try {
      const [taskRes, approvalRes, healthRes] = await Promise.allSettled([
        listTasks(1, 10),
        listApprovals(),
        checkHealth(),
      ]);

      if (taskRes.status === 'fulfilled') setTasks(taskRes.value.tasks);
      if (approvalRes.status === 'fulfilled') setApprovals(approvalRes.value);
      if (healthRes.status === 'fulfilled') setHealth(healthRes.value);
      setError(null);
    } catch (err) {
      setError('Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="loading-page">
        <div className="loading-spinner" />
        Loading dashboard...
      </div>
    );
  }

  const activeTasks = tasks.filter(
    (t) => !['COMPLETE', 'FAILED', 'CANCELLED', 'ARCHIVED'].includes(t.current_state)
  );
  const completedTasks = tasks.filter((t) => t.current_state === 'COMPLETE');
  const failedTasks = tasks.filter((t) => t.current_state === 'FAILED');

  return (
    <div className="page-container animate-in">
      <div className="page-header">
        <h1>Control Plane</h1>
        <p>Autonomous AI Developer Agents Platform — real-time system overview</p>
      </div>

      {error && <div className="error-banner">⚠ {error}</div>}

      {/* Stats Grid */}
      <div className="grid-stats" style={{ marginBottom: 'var(--space-2xl)' }}>
        <div className="card stat-card" style={{ '--stat-accent': 'var(--color-accent)' } as React.CSSProperties}>
          <div className="stat-value">{tasks.length}</div>
          <div className="stat-label">Total Tasks</div>
        </div>
        <div className="card stat-card" style={{ '--stat-accent': 'var(--color-warning)' } as React.CSSProperties}>
          <div className="stat-value">{activeTasks.length}</div>
          <div className="stat-label">Active</div>
        </div>
        <div className="card stat-card" style={{ '--stat-accent': 'var(--color-danger)' } as React.CSSProperties}>
          <div className="stat-value">{approvals.length}</div>
          <div className="stat-label">Pending Approvals</div>
        </div>
        <div className="card stat-card" style={{ '--stat-accent': health?.status === 'healthy' ? 'var(--color-success)' : 'var(--color-danger)' } as React.CSSProperties}>
          <div className="stat-value" style={{ fontSize: 'var(--font-size-xl)' }}>
            {health?.status === 'healthy' ? '● Healthy' : '○ Degraded'}
          </div>
          <div className="stat-label">System Health</div>
        </div>
      </div>

      {/* Two-column layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-xl)' }}>
        {/* Recent Tasks */}
        <div className="card">
          <div className="flex items-center justify-between mb-lg">
            <h2 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600 }}>Recent Tasks</h2>
            <Link href="/tasks" className="btn btn-ghost btn-sm">View All →</Link>
          </div>
          {tasks.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📋</div>
              <div className="empty-state-title">No tasks yet</div>
              <div className="empty-state-description">Submit your first task to get started.</div>
              <Link href="/tasks/new" className="btn btn-primary">Create Task</Link>
            </div>
          ) : (
            <div className="flex flex-col gap-sm">
              {tasks.slice(0, 5).map((task) => (
                <Link
                  key={task.id}
                  href={`/tasks/${task.id}`}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: 'var(--space-md) var(--space-lg)',
                    borderRadius: 'var(--radius-md)',
                    background: 'var(--color-bg-tertiary)',
                    transition: 'all var(--transition-fast)',
                    textDecoration: 'none',
                    color: 'var(--color-text-primary)',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 500, fontSize: 'var(--font-size-base)' }}>{task.title}</div>
                    <div className="text-xs text-secondary font-mono" style={{ marginTop: 2 }}>
                      {task.id.slice(0, 8)}… · {formatTime(task.created_at)}
                    </div>
                  </div>
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
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Pending Approvals */}
        <div className="card">
          <div className="flex items-center justify-between mb-lg">
            <h2 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600 }}>Pending Approvals</h2>
            <Link href="/approvals" className="btn btn-ghost btn-sm">View All →</Link>
          </div>
          {approvals.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">✅</div>
              <div className="empty-state-title">All clear</div>
              <div className="empty-state-description">No pending approvals require your attention.</div>
            </div>
          ) : (
            <div className="flex flex-col gap-sm">
              {approvals.slice(0, 5).map((approval) => (
                <Link
                  key={approval.id}
                  href={`/approvals/${approval.id}`}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: 'var(--space-md) var(--space-lg)',
                    borderRadius: 'var(--radius-md)',
                    background: 'var(--color-danger-muted)',
                    border: '1px solid rgba(239, 68, 68, 0.2)',
                    transition: 'all var(--transition-fast)',
                    textDecoration: 'none',
                    color: 'var(--color-text-primary)',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 500, fontSize: 'var(--font-size-base)' }}>
                      {approval.operation_type} — {approval.environment}
                    </div>
                    <div className="text-xs text-secondary">
                      Requested by {approval.requested_by}
                    </div>
                  </div>
                  <span className="badge" style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b' }}>
                    <span className="badge-dot" style={{ background: '#f59e0b' }} />
                    Pending
                  </span>
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
    const d = new Date(iso);
    return d.toLocaleString('en-US', {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return iso;
  }
}
