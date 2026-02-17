'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { getApproval, approveRequest, rejectRequest } from '@/api/client';
import type { Approval } from '@/api/types';

export default function ApprovalDetailPage() {
    const params = useParams();
    const approvalId = params.id as string;

    const [approval, setApproval] = useState<Approval | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [actionLoading, setActionLoading] = useState(false);

    useEffect(() => {
        loadApproval();
    }, [approvalId]);

    async function loadApproval() {
        try {
            const res = await getApproval(approvalId);
            setApproval(res);
            setError(null);
        } catch (err: any) {
            setError(err.detail || 'Approval not found');
        } finally {
            setLoading(false);
        }
    }

    async function handleApprove() {
        setActionLoading(true);
        try {
            const reason = prompt('Approval reason (optional):');
            const res = await approveRequest(approvalId, { reason: reason || undefined });
            setApproval(res);
        } catch (err: any) {
            setError(err.detail || 'Failed to approve');
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
        } catch (err: any) {
            setError(err.detail || 'Failed to reject');
        } finally {
            setActionLoading(false);
        }
    }

    if (loading) {
        return <div className="loading-page"><div className="loading-spinner" /> Loading approval...</div>;
    }

    if (!approval) {
        return (
            <div className="page-container">
                <div className="error-banner">⚠ {error || 'Approval not found'}</div>
                <Link href="/approvals" className="btn btn-ghost">← Back to Approvals</Link>
            </div>
        );
    }

    const isPending = approval.status === 'PENDING';
    const statusColor = isPending ? 'var(--color-warning)' : approval.status === 'APPROVED' ? 'var(--color-success)' : 'var(--color-danger)';

    return (
        <div className="page-container animate-in">
            <div className="flex items-center gap-md mb-lg">
                <Link href="/approvals" className="btn btn-ghost btn-sm">← Back</Link>
            </div>

            <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-2xl)' }}>
                <div>
                    <h1 style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 700, marginBottom: 'var(--space-sm)' }}>
                        Approval: {approval.operation_type}
                    </h1>
                    <div className="text-sm font-mono text-secondary">{approval.id}</div>
                </div>
                <span className="badge" style={{
                    background: `${statusColor}20`,
                    color: statusColor,
                    fontSize: 'var(--font-size-sm)',
                    padding: '6px 16px',
                }}>
                    <span className="badge-dot" style={{ background: statusColor, width: 8, height: 8 }} />
                    {approval.status}
                </span>
            </div>

            {error && <div className="error-banner">⚠ {error}</div>}

            <div className="card" style={{ marginBottom: 'var(--space-xl)' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-xl)' }}>
                    <div>
                        <div className="text-xs text-secondary" style={{ marginBottom: 'var(--space-xs)' }}>Task</div>
                        <Link href={`/tasks/${approval.task_id}`} className="font-mono" style={{ color: 'var(--color-accent)' }}>
                            {approval.task_id.slice(0, 12)}…
                        </Link>
                    </div>
                    <div>
                        <div className="text-xs text-secondary" style={{ marginBottom: 'var(--space-xs)' }}>Environment</div>
                        <span className="badge" style={{
                            background: approval.environment === 'PRODUCTION' ? 'var(--color-danger-muted)' : 'var(--color-info-muted)',
                            color: approval.environment === 'PRODUCTION' ? 'var(--color-danger)' : 'var(--color-info)',
                        }}>
                            {approval.environment}
                        </span>
                    </div>
                    <div>
                        <div className="text-xs text-secondary" style={{ marginBottom: 'var(--space-xs)' }}>Risk Level</div>
                        <div>{approval.risk_level}</div>
                    </div>
                    <div>
                        <div className="text-xs text-secondary" style={{ marginBottom: 'var(--space-xs)' }}>Requested By</div>
                        <div>{approval.requested_by}</div>
                    </div>
                    <div>
                        <div className="text-xs text-secondary" style={{ marginBottom: 'var(--space-xs)' }}>Created</div>
                        <div className="text-sm">{formatTime(approval.created_at)}</div>
                    </div>
                    {approval.decided_by && (
                        <div>
                            <div className="text-xs text-secondary" style={{ marginBottom: 'var(--space-xs)' }}>Decided By</div>
                            <div>{approval.decided_by}</div>
                        </div>
                    )}
                </div>

                {approval.decision_reason && (
                    <div style={{ marginTop: 'var(--space-xl)', padding: 'var(--space-lg)', background: 'var(--color-bg-tertiary)', borderRadius: 'var(--radius-md)' }}>
                        <div className="text-xs text-secondary" style={{ marginBottom: 'var(--space-sm)' }}>Decision Reason</div>
                        <div>{approval.decision_reason}</div>
                    </div>
                )}
            </div>

            {isPending && (
                <div className="flex items-center gap-md">
                    <button className="btn btn-success" disabled={actionLoading} onClick={handleApprove}>
                        {actionLoading ? <div className="loading-spinner" style={{ width: 16, height: 16 }} /> : '✓'} Approve
                    </button>
                    <button className="btn btn-danger" disabled={actionLoading} onClick={handleReject}>
                        ✕ Reject
                    </button>
                </div>
            )}
        </div>
    );
}

function formatTime(iso: string): string {
    try {
        return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch { return iso; }
}
