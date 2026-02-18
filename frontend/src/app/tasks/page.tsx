'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { listTasks } from '@/api/client';
import type { Task } from '@/api/types';
import { STATE_COLORS, STATE_LABELS } from '@/api/types';
import {
  StateBadge,
  EnvBadge,
  EmptyState,
  ErrorBanner,
  LoadingPage,
  PageHeader,
} from '@/components/ui';
import { formatTime } from '@/lib/utils';

const PAGE_SIZE = 20;

const TASK_STATES = [
  '', 'SUBMITTED', 'PARSING', 'PARSED', 'PARSE_FAILED', 'PLANNING', 'PLANNED',
  'AGENT_ASSIGNMENT', 'AGENT_ASSIGNED', 'IN_DEVELOPMENT', 'CODE_GENERATED',
  'DEV_FAILED', 'IN_VALIDATION', 'VALIDATION_PASSED', 'VALIDATION_FAILED',
  'OPTIMIZATION_PENDING', 'IN_OPTIMIZATION', 'OPTIMIZED',
  'APPROVAL_PENDING', 'IN_REVIEW', 'APPROVED', 'REJECTED',
  'DEPLOYING', 'DEPLOYED', 'COMPLETED', 'CANCELLED',
];

export default function TasksPage() {
  const router = useRouter();

  const [tasks, setTasks]           = useState<Task[]>([]);
  const [total, setTotal]           = useState(0);
  const [page, setPage]             = useState(1);
  const [stateFilter, setStateFilter] = useState('');
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState<string | null>(null);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  useEffect(() => {
    loadTasks();
    const interval = setInterval(loadTasks, 5000);
    return () => clearInterval(interval);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, stateFilter]);

  async function loadTasks() {
    try {
      const res = await listTasks(page, PAGE_SIZE, stateFilter || undefined);
      setTasks(res.tasks);
      setTotal(res.total);
      setError(null);
    } catch {
      setError('Failed to load tasks');
    } finally {
      setLoading(false);
    }
  }

  function handleFilterChange(value: string) {
    setStateFilter(value);
    setPage(1);
  }

  return (
    <div className="page-container animate-in">
      <PageHeader
        title="Tasks"
        subtitle={`${total} total task${total !== 1 ? 's' : ''}`}
        actions={
          <Link href="/tasks/new" className="btn btn-primary">
            + New Task
          </Link>
        }
      />

      {error && <ErrorBanner message={error} />}

      {/* ── Filter row ── */}
      <div className="flex items-center gap-md mb-lg flex-wrap">
        <label
          htmlFor="state-filter"
          className="text-sm text-secondary"
          style={{ whiteSpace: 'nowrap' }}
        >
          Filter by state:
        </label>
        <select
          id="state-filter"
          className="form-select"
          value={stateFilter}
          onChange={(e) => handleFilterChange(e.target.value)}
          style={{ width: 'auto', minWidth: 180 }}
        >
          <option value="">All States</option>
          {TASK_STATES.filter(Boolean).map((s) => (
            <option key={s} value={s}>
              {STATE_LABELS[s] ?? s}
            </option>
          ))}
        </select>

        {stateFilter && (
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => handleFilterChange('')}
            aria-label="Clear state filter"
          >
            Clear
          </button>
        )}
      </div>

      {/* ── Content ── */}
      {loading ? (
        <LoadingPage message="Loading tasks…" />
      ) : tasks.length === 0 ? (
        <div className="card">
          <EmptyState
            icon="📋"
            title="No tasks found"
            description={
              stateFilter
                ? `No tasks with state "${STATE_LABELS[stateFilter] ?? stateFilter}".`
                : 'Submit your first task to get started.'
            }
            action={
              !stateFilter ? (
                <Link href="/tasks/new" className="btn btn-primary">
                  Create Task
                </Link>
              ) : undefined
            }
          />
        </div>
      ) : (
        <>
          {/* Scroll wrapper ensures mobile horizontal scrolling */}
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <div className="table-scroll-wrapper">
              <table className="data-table" aria-label="Tasks list">
                <thead>
                  <tr>
                    <th scope="col">Task</th>
                    <th scope="col">State</th>
                    <th scope="col">Environment</th>
                    <th scope="col">Priority</th>
                    <th scope="col">Tokens</th>
                    <th scope="col">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {tasks.map((task) => (
                    <tr
                      key={task.id}
                      data-clickable
                      onClick={() => router.push(`/tasks/${task.id}`)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          router.push(`/tasks/${task.id}`);
                        }
                      }}
                      tabIndex={0}
                      role="link"
                      aria-label={`View task: ${task.title}`}
                    >
                      <td>
                        <div className="font-medium">{task.title}</div>
                        <div className="text-xs text-secondary font-mono mt-xs">
                          {task.id.slice(0, 8)}…
                        </div>
                      </td>
                      <td>
                        <StateBadge
                          state={task.current_state}
                          stateColors={STATE_COLORS}
                          stateLabels={STATE_LABELS}
                        />
                      </td>
                      <td>
                        <EnvBadge env={task.environment} />
                      </td>
                      <td className="text-sm">{task.priority}</td>
                      <td className="text-sm font-mono">
                        {task.tokens_used.toLocaleString()} /{' '}
                        {task.token_budget.toLocaleString()}
                      </td>
                      <td className="text-sm text-secondary">
                        {formatTime(task.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* ── Pagination ── */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-xl">
              <span className="text-sm text-secondary">
                Page {page} of {totalPages}
              </span>
              <div className="flex gap-sm">
                <button
                  className="btn btn-ghost btn-sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                  aria-label="Previous page"
                >
                  ← Previous
                </button>
                <button
                  className="btn btn-ghost btn-sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  aria-label="Next page"
                >
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
