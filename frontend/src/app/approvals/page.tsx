'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { listApprovals, approveRequest, rejectRequest } from '@/api/client';
import type { Approval } from '@/api/types';

export default function ApprovalsPage() {
    const [approvals, setApprovals] = useState<Approval[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
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
        } catch (err) {
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
        } catch (err: any) {
            setError(err.detail || 'Failed to approve');
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
        } catch (err: any) {
            setError(err.detail || 'Failed to reject');
        } finally {
            setActionLoading(null);
        }
    }

    if (loading) {
        return <div className="loading-page"><div className="loading-spinner" /> Loading approvals...</div>;
    }

    return (
        <div className="page-container animate-in">
            <div className="page-header">
                <h1>Pending Approvals</h1>
                <p>
                    {approvals.length === 0
                        ? 'No pending approvals — all clear.'
                        : `${approvals.length} approval${approvals.length > 1 ? 's' : ''} require${approvals.length === 1 ? 's' : ''} your attention.`
                    }
                </p>
            </div>

            {error && <div className="error-banner">⚠ {error}</div>}

            {approvals.length === 0 ? (
                <div className="card">
                    <div className="empty-state">
                        <div className="empty-state-icon">✅</div>
                        <div className="empty-state-title">All clear</div>
                        <div className="empty-state-description">
                            No operations are waiting for human approval. The Autonomy Policy Matrix<br />
                            auto-approves safe operations in sandbox environments.
                        </div>
                    </div>
                </div>
            ) : (
                <div className="grid-cards">
                    {approvals.map((approval) => (
                        <div key={approval.id} className="card" style={{ position: 'relative', overflow: 'hidden' }}>
                            {/* Accent bar */}
                            <div style={{
                                position: 'absolute', top: 0, left: 0, right: 0, height: 3,
                                background: approval.environment === 'PRODUCTION'
                                    ? 'linear-gradient(90deg, var(--color-danger), #f97316)'
                                    : 'linear-gradient(90deg, var(--color-warning), var(--color-accent))',
                            }} />

                            <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-lg)' }}>
                                <div>
                                    <div style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600 }}>
                                        {approval.operation_type}
                                    </div>
                                    <div className="text-sm text-secondary font-mono">{approval.id.slice(0, 8)}…</div>
                                </div>
                                <div className="flex items-center gap-md">
                                    <span className="badge" style={{
                                        background: approval.environment === 'PRODUCTION' ? 'var(--color-danger-muted)' : 'var(--color-info-muted)',
                                        color: approval.environment === 'PRODUCTION' ? 'var(--color-danger)' : 'var(--color-info)',
                                    }}>
                                        {approval.environment}
                                    </span>
                                    <span className="badge" style={{
                                        background: 'var(--color-warning-muted)',
                                        color: 'var(--color-warning)',
                                    }}>
                                        <span className="badge-dot" style={{ background: 'var(--color-warning)' }} />
                                        PENDING
                                    </span>
                                </div>
                            </div>

                            {/* Details */}
                            <div style={{
                                display: 'grid',
                                gridTemplateColumns: '1fr 1fr 1fr',
                                gap: 'var(--space-lg)',
                                marginBottom: 'var(--space-xl)',
                                padding: 'var(--space-lg)',
                                background: 'var(--color-bg-tertiary)',
                                borderRadius: 'var(--radius-md)',
                            }}>
                                <div>
                                    <div className="text-xs text-secondary">Task ID</div>
                                    <Link href={`/tasks/${approval.task_id}`} className="text-sm font-mono" style={{ color: 'var(--color-accent)' }}>
                                        {approval.task_id.slice(0, 8)}…
                                    </Link>
                                </div>
                                <div>
                                    <div className="text-xs text-secondary">Requested By</div>
                                    <div className="text-sm">{approval.requested_by}</div>
                                </div>
                                <div>
                                    <div className="text-xs text-secondary">Risk Level</div>
                                    <div className="text-sm">{approval.risk_level}</div>
                                </div>
                            </div>

                            {/* INV-01 notice */}
                            {approval.environment === 'PRODUCTION' && approval.operation_type === 'destructive' && (
                                <div style={{
                                    padding: 'var(--space-md) var(--space-lg)',
                                    background: 'var(--color-danger-muted)',
                                    border: '1px solid rgba(239, 68, 68, 0.2)',
                                    borderRadius: 'var(--radius-md)',
                                    fontSize: 'var(--font-size-xs)',
                                    color: '#fca5a5',
                                    marginBottom: 'var(--space-xl)',
                                }}>
                                    ⚠ <strong>INV-01:</strong> This is a destructive operation in production. No execution without explicit human approval.
                                </div>
                            )}

                            {/* Actions */}
                            <div className="flex items-center gap-md">
                                <button
                                    className="btn btn-success"
                                    disabled={actionLoading === approval.id}
                                    onClick={() => handleApprove(approval.id)}
                                >
                                    {actionLoading === approval.id ? <div className="loading-spinner" style={{ width: 16, height: 16 }} /> : '✓'} Approve
                                </button>
                                <button
                                    className="btn btn-danger"
                                    disabled={actionLoading === approval.id}
                                    onClick={() => handleReject(approval.id)}
                                >
                                    ✕ Reject
                                </button>
                                <div className="text-xs text-secondary" style={{ marginLeft: 'auto' }}>
                                    {formatTime(approval.created_at)}
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

function formatTime(iso: string): string {
    try {
        return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch { return iso; }
}
