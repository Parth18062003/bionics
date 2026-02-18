'use client';

import { useEffect, useState } from 'react';
import { listApprovals, approveRequest, rejectRequest } from '@/api/client';
import type { Approval } from '@/api/types';
import { Badge, EnvBadge, EmptyState, ErrorBanner, LoadingPage, PageHeader } from '@/components/ui';
import { formatTime } from '@/lib/utils';

export default function ApprovalsPage() {
  const [approvals, setApprovals]       = useState<Approval[]>([]);
  const [loading, setLoading]           = useState(true);
  const [error, setError]               = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  useEffect(() => {
    loadApprovals();
    const interval = setInterval(loadApprovals, 5000);
    return () => clearInterval(interval);
  }, []);

  async function loadApprovals() {
    try {
      const res = await listApprovals();
      setApprovals(res);
      setError(null);
    } catch {
      setError('Failed to load approvals');
    } finally {
      setLoading(false);
    }
  }

  async function handleApprove(id: string) {
    setActionLoading(id);
    try {
      const reason = prompt('Approval reason (optional):');
      await approveRequest(id, { reason: reason || undefined });
      await loadApprovals();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to approve';
      setError(msg);
    } finally {
      setActionLoading(null);
    }
  }

  async function handleReject(id: string) {
    setActionLoading(id);
    try {
      const reason = prompt('Rejection reason:');
      if (!reason) { setActionLoading(null); return; }
      await rejectRequest(id, { reason });
      await loadApprovals();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to reject';
      setError(msg);
    } finally {
      setActionLoading(null);
    }
  }

  if (loading) return <LoadingPage message="Loading approvals…" />;

  const count = approvals.length;

  return (
    <div className="page-container animate-in">
      <PageHeader
        title="Pending Approvals"
        subtitle={
          count === 0
            ? 'No pending approvals — all clear.'
            : `${count} approval${count > 1 ? 's' : ''} require${count === 1 ? 's' : ''} your attention.`
        }
      />

      {error && <ErrorBanner message={error} />}

      {count === 0 ? (
        <div className="card">
          <EmptyState
            icon="✅"
            title="All clear"
            description={
              'No operations are waiting for human approval. The Autonomy Policy Matrix ' +
              'auto-approves safe operations in sandbox environments.'
            }
          />
        </div>
      ) : (
        <div className="grid-cards" role="list" aria-label="Pending approvals">
          {approvals.map((approval) => {
            const isProd        = approval.environment === 'PRODUCTION';
            const isDestructive = approval.operation_type === 'destructive';
            const isActioning   = actionLoading === approval.id;

            return (
              <article
                key={approval.id}
                className="card"
                role="listitem"
                style={{ position: 'relative', overflow: 'hidden' }}
                aria-label={`Approval: ${approval.operation_type} in ${approval.environment}`}
              >
                {/* Coloured accent bar */}
                <div
                  style={{
                    position: 'absolute',
                    top: 0, left: 0, right: 0,
                    height: 3,
                    background: isProd
                      ? 'linear-gradient(90deg, var(--color-danger), #f97316)'
                      : 'linear-gradient(90deg, var(--color-warning), var(--color-accent))',
                  }}
                  aria-hidden="true"
                />

                {/* Header */}
                <div
                  className="flex items-center justify-between mb-lg"
                  style={{ paddingTop: 'var(--space-xs)' }}
                >
                  <div>
                    <div className="font-semibold" style={{ fontSize: 'var(--font-size-lg)' }}>
                      {approval.operation_type}
                    </div>
                    <div className="text-sm text-secondary font-mono mt-xs">
                      {approval.id.slice(0, 8)}…
                    </div>
                  </div>
                  <div className="flex items-center gap-md flex-wrap">
                    <EnvBadge env={approval.environment} />
                    <Badge
                      bg="var(--color-warning-muted)"
                      color="var(--color-warning)"
                      dot
                    >
                      Pending
                    </Badge>
                  </div>
                </div>

                {/* Detail grid */}
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(3, 1fr)',
                    gap: 'var(--space-lg)',
                    padding: 'var(--space-lg)',
                    background: 'var(--color-bg-tertiary)',
                    borderRadius: 'var(--radius-md)',
                    marginBottom: 'var(--space-xl)',
                  }}
                >
                  <div>
                    <div className="text-xs text-secondary mb-xs">Task ID</div>
                    <a
                      href={`/tasks/${approval.task_id}`}
                      className="text-sm font-mono"
                      style={{ color: 'var(--color-accent)' }}
                    >
                      {approval.task_id.slice(0, 8)}…
                    </a>
                  </div>
                  <div>
                    <div className="text-xs text-secondary mb-xs">Requested By</div>
                    <div className="text-sm">{approval.requested_by}</div>
                  </div>
                  <div>
                    <div className="text-xs text-secondary mb-xs">Risk Level</div>
                    <div className="text-sm font-medium">{approval.risk_level}</div>
                  </div>
                </div>

                {/* INV-01 warning */}
                {isProd && isDestructive && (
                  <div
                    style={{
                      padding: 'var(--space-md) var(--space-lg)',
                      background: 'var(--color-danger-muted)',
                      border: '1px solid rgba(239, 68, 68, 0.2)',
                      borderRadius: 'var(--radius-md)',
                      fontSize: 'var(--font-size-xs)',
                      color: '#fca5a5',
                      marginBottom: 'var(--space-xl)',
                    }}
                    role="alert"
                  >
                    ⚠ <strong>INV-01:</strong> This is a destructive operation in production.
                    No execution without explicit human approval.
                  </div>
                )}

                {/* Actions */}
                <div className="flex items-center gap-md">
                  <button
                    className="btn btn-success"
                    disabled={isActioning}
                    onClick={() => handleApprove(approval.id)}
                    aria-label={`Approve ${approval.operation_type}`}
                  >
                    {isActioning ? (
                      <div className="loading-spinner" style={{ width: 16, height: 16 }} aria-hidden="true" />
                    ) : (
                      <span aria-hidden="true">✓</span>
                    )}
                    Approve
                  </button>
                  <button
                    className="btn btn-danger"
                    disabled={isActioning}
                    onClick={() => handleReject(approval.id)}
                    aria-label={`Reject ${approval.operation_type}`}
                  >
                    <span aria-hidden="true">✕</span>
                    Reject
                  </button>
                  <time
                    className="text-xs text-secondary"
                    style={{ marginLeft: 'auto' }}
                    dateTime={approval.created_at}
                  >
                    {formatTime(approval.created_at)}
                  </time>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
