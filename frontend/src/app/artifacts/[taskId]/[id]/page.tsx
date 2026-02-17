'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { getArtifact } from '@/api/client';
import type { ArtifactDetail } from '@/api/types';

export default function ArtifactViewPage() {
    const params = useParams();
    const taskId = params.taskId as string;
    const artifactId = params.id as string;

    const [artifact, setArtifact] = useState<ArtifactDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        loadArtifact();
    }, [taskId, artifactId]);

    async function loadArtifact() {
        try {
            const res = await getArtifact(taskId, artifactId);
            setArtifact(res);
            setError(null);
        } catch (err: any) {
            setError(err.detail || 'Artifact not found');
        } finally {
            setLoading(false);
        }
    }

    if (loading) {
        return <div className="loading-page"><div className="loading-spinner" /> Loading artifact...</div>;
    }

    if (!artifact) {
        return (
            <div className="page-container">
                <div className="error-banner">⚠ {error || 'Artifact not found'}</div>
                <Link href={`/tasks/${taskId}`} className="btn btn-ghost">← Back to Task</Link>
            </div>
        );
    }

    return (
        <div className="page-container animate-in">
            <div className="flex items-center gap-md mb-lg">
                <Link href={`/tasks/${taskId}`} className="btn btn-ghost btn-sm">← Back to Task</Link>
            </div>

            <div style={{ marginBottom: 'var(--space-2xl)' }}>
                <h1 style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 700, marginBottom: 'var(--space-sm)' }}>
                    {artifact.name}
                </h1>
                <div className="flex items-center gap-md">
                    <span className="badge" style={{ background: 'var(--color-accent-muted)', color: 'var(--color-accent)' }}>
                        {artifact.artifact_type}
                    </span>
                    <span className="text-sm text-secondary">
                        Created {formatTime(artifact.created_at)}
                    </span>
                    {artifact.content_hash && (
                        <span className="text-xs font-mono text-secondary">
                            {artifact.content_hash}
                        </span>
                    )}
                </div>
            </div>

            {/* Metadata */}
            {artifact.metadata && Object.keys(artifact.metadata).length > 0 && (
                <div className="card" style={{ marginBottom: 'var(--space-xl)' }}>
                    <h3 style={{ fontSize: 'var(--font-size-base)', fontWeight: 600, marginBottom: 'var(--space-md)' }}>
                        Metadata
                    </h3>
                    <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
                        gap: 'var(--space-md)',
                    }}>
                        {Object.entries(artifact.metadata).map(([key, value]) => (
                            <div key={key}>
                                <div className="text-xs text-secondary">{key}</div>
                                <div className="text-sm font-mono">{String(value)}</div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Content */}
            <div className="card">
                <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-lg)' }}>
                    <h3 style={{ fontSize: 'var(--font-size-base)', fontWeight: 600 }}>Content</h3>
                    {artifact.content && (
                        <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => {
                                navigator.clipboard.writeText(artifact.content || '');
                            }}
                        >
                            📋 Copy
                        </button>
                    )}
                </div>
                {artifact.content ? (
                    <div className="code-block">{artifact.content}</div>
                ) : (
                    <div className="text-sm text-secondary">
                        {artifact.storage_uri
                            ? `Content stored externally: ${artifact.storage_uri}`
                            : 'No content available.'}
                    </div>
                )}
            </div>
        </div>
    );
}

function formatTime(iso: string): string {
    try {
        return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch { return iso; }
}
