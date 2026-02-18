'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { getApproval, approveRequest, rejectRequest } from '@/api/client';
import type { Approval } from '@/api/types';
import { Badge, EnvBadge, ErrorBanner, LoadingPage } from '@/components/ui';
import { formatTimeWithSeconds } from '@/lib/utils';

export default function ApprovalDetailPage() {
  const params     = useParams();
  const approvalId = params.id as string;

  const [approval, setApproval]         = useState<Approval | null>(null);
  const [loading, setLoading]           = useState(true);
  const [error, setError]               = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    loadApproval();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [approvalId]);

  async function loadApproval() {
    try {
      const res = await getApproval(approvalId);
      setApproval(res);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Approval not found');
    } finally {
      setLoading(false);
    }
  }

  async function handleApprove() {
    setActionLoading(true);
    try {
      const reason = prompt('Approval reason (optional):');
      const res    = await approveRequest(approvalId, { reason: reason || undefined });
      setApproval(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to approve');
    } finally {
      setActionLoading(false);
    }
  }

  async function handleReject() {
    setActionLoading(true);
    try {
      const reason = prompt('Rejection reason:');
      if (!reason) { setActionLoading(false); return; }
      const res = await rejectRequest(approvalId, { reason });
      setApproval(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to reject');
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) return <LoadingPage message="Loading approval…" />;

  if (!approval) {
    return (
      <div className="page-container">
        <ErrorBanner message={error ?? 'Approval not found'} />
        <Link href="/approvals" className="btn btn-ghost">
          ← Back to Approvals
        </Link>
      </div>
    );
  }

  const isPending   = approval.status === 'PENDING';
  const statusColor =
    isPending
      ? 'var(--color-warning)'
      : approval.status === 'APPROVED'
      ? 'var(--color-success)'
      : 'var(--color-danger)';

  return (
    <div className="page-container animate-in">
      {/* ── Breadcrumb ── */}
      <div className="flex items-center gap-md mb-lg">
        <Link href="/approvals" className="btn btn-ghost btn-sm" aria-label="Back to approvals list">
          ← Back
        </Link>
      </div>

      {/* ── Page title row ── */}
      <div
        className="flex items-start justify-between mb-2xl"
        style={{ gap: 'var(--space-lg)', flexWrap: 'wrap' }}
      >
        <div>
          <h1 style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 700, marginBottom: 'var(--space-sm)' }}>
            Approval: {approval.operation_type}
          </h1>
          <div className="text-sm font-mono text-secondary">{approval.id}</div>
        </div>

        <Badge
          color={statusColor}
          dot
          style={{ fontSize: 'var(--font-size-sm)', padding: '6px 16px' }}
        >
          {approval.status}
        </Badge>
      </div>

      {error && <ErrorBanner message={error} />}

      {/* ── Detail card ── */}
      <div className="card mb-xl">
        {/* Metadata grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
            gap: 'var(--space-xl)',
          }}
        >
          <div>
            <div className="text-xs text-secondary mb-xs">Task</div>
            <Link
              href={`/tasks/${approval.task_id}`}
              className="font-mono"
              style={{ color: 'var(--color-accent)' }}
            >
              {approval.task_id.slice(0, 12)}…
            </Link>
          </div>

          <div>
            <div className="text-xs text-secondary mb-xs">Environment</div>
            <EnvBadge env={approval.environment} />
          </div>

          <div>
            <div className="text-xs text-secondary mb-xs">Risk Level</div>
            <div className="font-medium">{approval.risk_level}</div>
          </div>

          <div>
            <div className="text-xs text-secondary mb-xs">Requested By</div>
            <div>{approval.requested_by}</div>
          </div>

          <div>
            <div className="text-xs text-secondary mb-xs">Created</div>
            <time className="text-sm" dateTime={approval.created_at}>
              {formatTimeWithSeconds(approval.created_at)}
            </time>
          </div>

          {approval.decided_by && (
            <div>
              <div className="text-xs text-secondary mb-xs">Decided By</div>
              <div>{approval.decided_by}</div>
            </div>
          )}
        </div>

        {/* Decision reason */}
        {approval.decision_reason && (
          <div
            style={{
              marginTop: 'var(--space-xl)',
              padding: 'var(--space-lg)',
              background: 'var(--color-bg-tertiary)',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <div className="text-xs text-secondary mb-sm">Decision Reason</div>
            <p>{approval.decision_reason}</p>
          </div>
        )}
      </div>

      {/* ── Action buttons (only when still pending) ── */}
      {isPending && (
        <div className="flex items-center gap-md">
          <button
            className="btn btn-success"
            disabled={actionLoading}
            onClick={handleApprove}
            aria-label="Approve this request"
          >
            {actionLoading ? (
              <div className="loading-spinner" style={{ width: 16, height: 16 }} aria-hidden="true" />
            ) : (
              <span aria-hidden="true">✓</span>
            )}
            Approve
          </button>
          <button
            className="btn btn-danger"
            disabled={actionLoading}
            onClick={handleReject}
            aria-label="Reject this request"
          >
            <span aria-hidden="true">✕</span>
            Reject
          </button>
        </div>
      )}
    </div>
  );
}
