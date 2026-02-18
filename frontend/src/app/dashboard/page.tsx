'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { listTasks, listApprovals, checkHealth } from '@/api/client';
import type { Task, Approval, HealthResponse } from '@/api/types';
import { STATE_COLORS, STATE_LABELS } from '@/api/types';
import {
  Badge,
  StateBadge,
  EmptyState,
  ErrorBanner,
  LoadingPage,
  PageHeader,
} from '@/components/ui';
import { formatTime } from '@/lib/utils';

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
    } catch {
      setError('Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return <LoadingPage message="Loading dashboard…" />;
  }

  const activeTasks = tasks.filter(
    (t) => !['COMPLETE', 'FAILED', 'CANCELLED', 'ARCHIVED'].includes(t.current_state)
  );
  const isHealthy = health?.status === 'healthy';

  return (
    <div className="page-container animate-in">
      <PageHeader
        title="Control Plane"
        subtitle="Autonomous AI Developer Agents Platform — real-time system overview"
      />

      {error && <ErrorBanner message={error} />}

      {/* ── Stats Grid ── */}
      <div className="grid-stats mb-2xl">
        <div
          className="card stat-card"
          style={{ '--stat-accent': 'var(--color-accent)' } as React.CSSProperties}
        >
          <div className="stat-value">{tasks.length}</div>
          <div className="stat-label">Total Tasks</div>
        </div>

        <div
          className="card stat-card"
          style={{ '--stat-accent': 'var(--color-warning)' } as React.CSSProperties}
        >
          <div className="stat-value">{activeTasks.length}</div>
          <div className="stat-label">Active</div>
        </div>

        <div
          className="card stat-card"
          style={{ '--stat-accent': 'var(--color-danger)' } as React.CSSProperties}
        >
          <div className="stat-value">{approvals.length}</div>
          <div className="stat-label">Pending Approvals</div>
        </div>

        <div
          className="card stat-card"
          style={{
            '--stat-accent': isHealthy ? 'var(--color-success)' : 'var(--color-danger)',
          } as React.CSSProperties}
        >
          <div
            className="stat-value"
            style={{
              fontSize: 'var(--font-size-xl)',
              color: isHealthy ? 'var(--color-success)' : 'var(--color-danger)',
            }}
          >
            {isHealthy ? '● Healthy' : '○ Degraded'}
          </div>
          <div className="stat-label">System Health</div>
        </div>
      </div>

      {/* ── Two-column layout (responsive) ── */}
      <div className="grid-2col">
        {/* Recent Tasks */}
        <section className="card" aria-labelledby="recent-tasks-heading">
          <div className="flex items-center justify-between mb-lg">
            <h2
              id="recent-tasks-heading"
              style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600 }}
            >
              Recent Tasks
            </h2>
            <Link href="/tasks" className="btn btn-ghost btn-sm">
              View All →
            </Link>
          </div>

          {tasks.length === 0 ? (
            <EmptyState
              icon="📋"
              title="No tasks yet"
              description="Submit your first task to get started."
              action={
                <Link href="/tasks/new" className="btn btn-primary">
                  Create Task
                </Link>
              }
            />
          ) : (
            <div className="flex flex-col gap-sm" role="list" aria-label="Recent tasks">
              {tasks.slice(0, 5).map((task) => (
                <Link
                  key={task.id}
                  href={`/tasks/${task.id}`}
                  role="listitem"
                  className="dashboard-task-row"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: 'var(--space-md) var(--space-lg)',
                    borderRadius: 'var(--radius-md)',
                    background: 'var(--color-bg-tertiary)',
                    border: '1px solid transparent',
                    transition: 'all var(--transition-fast)',
                    textDecoration: 'none',
                    color: 'var(--color-text-primary)',
                    gap: 'var(--space-md)',
                  }}
                >
                  <div style={{ minWidth: 0 }}>
                    <div
                      className="font-medium truncate"
                      style={{ fontSize: 'var(--font-size-base)' }}
                    >
                      {task.title}
                    </div>
                    <div className="text-xs text-secondary font-mono mt-xs">
                      {task.id.slice(0, 8)}… · {formatTime(task.created_at)}
                    </div>
                  </div>
                  <StateBadge
                    state={task.current_state}
                    stateColors={STATE_COLORS}
                    stateLabels={STATE_LABELS}
                  />
                </Link>
              ))}
            </div>
          )}
        </section>

        {/* Pending Approvals */}
        <section className="card" aria-labelledby="pending-approvals-heading">
          <div className="flex items-center justify-between mb-lg">
            <h2
              id="pending-approvals-heading"
              style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600 }}
            >
              Pending Approvals
            </h2>
            <Link href="/approvals" className="btn btn-ghost btn-sm">
              View All →
            </Link>
          </div>

          {approvals.length === 0 ? (
            <EmptyState
              icon="✅"
              title="All clear"
              description="No pending approvals require your attention."
            />
          ) : (
            <div className="flex flex-col gap-sm" role="list" aria-label="Pending approvals">
              {approvals.slice(0, 5).map((approval) => (
                <Link
                  key={approval.id}
                  href={`/approvals/${approval.id}`}
                  role="listitem"
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
                    gap: 'var(--space-md)',
                  }}
                >
                  <div style={{ minWidth: 0 }}>
                    <div
                      className="font-medium truncate"
                      style={{ fontSize: 'var(--font-size-base)' }}
                    >
                      {approval.operation_type} — {approval.environment}
                    </div>
                    <div className="text-xs text-secondary mt-xs">
                      Requested by {approval.requested_by}
                    </div>
                  </div>
                  <Badge
                    bg="var(--color-warning-muted)"
                    color="var(--color-warning)"
                    dot
                  >
                    Pending
                  </Badge>
                </Link>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
