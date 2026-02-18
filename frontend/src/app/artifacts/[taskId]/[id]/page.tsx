'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { getArtifact } from '@/api/client';
import type { ArtifactDetail } from '@/api/types';

// ── Helpers ────────────────────────────────────────────────────────────

function formatTime(iso: string): string {
    try {
        return new Date(iso).toLocaleString('en-US', {
            month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit', second: '2-digit',
        });
    } catch { return iso; }
}

function tryParseJson(content: string | null): Record<string, unknown> | null {
    if (!content) return null;
    try { return JSON.parse(content); } catch { return null; }
}

// ── Specialized Renderers ──────────────────────────────────────────────

function JsonViewer({ content, label }: { content: string | null; label?: string }) {
    const parsed = tryParseJson(content);
    return (
        <div className="card">
            <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-lg)' }}>
                <h3 style={{ fontSize: 'var(--font-size-base)', fontWeight: 600 }}>{label ?? 'Configuration'}</h3>
                {content && (
                    <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => navigator.clipboard.writeText(content)}
                    >
                        📋 Copy
                    </button>
                )}
            </div>
            {content ? (
                <pre style={{
                    padding: 'var(--space-md)',
                    background: 'var(--color-bg-primary)',
                    borderRadius: 'var(--radius-sm)',
                    fontFamily: 'var(--font-mono)',
                    fontSize: 'var(--font-size-xs)',
                    color: 'var(--color-accent)',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    overflow: 'auto',
                    maxHeight: 480,
                    border: '1px solid var(--color-border)',
                }}>
                    {parsed ? JSON.stringify(parsed, null, 2) : content}
                </pre>
            ) : (
                <p className="text-sm text-secondary">No content available.</p>
            )}
        </div>
    );
}

function IngestionConfigCard({ content }: { content: string | null }) {
    const cfg = tryParseJson(content) as { source_type?: string; target_type?: string; ingestion_mode?: string } | null;
    return (
        <div className="card">
            <h3 style={{ fontSize: 'var(--font-size-base)', fontWeight: 600, marginBottom: 'var(--space-lg)' }}>
                📥 Ingestion Configuration
            </h3>
            {cfg ? (
                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
                    gap: 'var(--space-lg)',
                }}>
                    <div style={{ padding: 'var(--space-lg)', background: 'var(--color-bg-tertiary)', borderRadius: 'var(--radius-md)' }}>
                        <div className="text-xs text-secondary mb-xs">Source Type</div>
                        <div className="font-semibold" style={{ fontSize: 'var(--font-size-base)' }}>
                            {cfg.source_type ?? '—'}
                        </div>
                    </div>
                    <div style={{ padding: 'var(--space-lg)', background: 'var(--color-bg-tertiary)', borderRadius: 'var(--radius-md)' }}>
                        <div className="text-xs text-secondary mb-xs">Target Type</div>
                        <div className="font-semibold" style={{ fontSize: 'var(--font-size-base)' }}>
                            {cfg.target_type ?? '—'}
                        </div>
                    </div>
                    <div style={{ padding: 'var(--space-lg)', background: 'var(--color-bg-tertiary)', borderRadius: 'var(--radius-md)' }}>
                        <div className="text-xs text-secondary mb-xs">Ingestion Mode</div>
                        <div className="font-semibold" style={{ fontSize: 'var(--font-size-base)', textTransform: 'uppercase' }}>
                            {cfg.ingestion_mode ?? '—'}
                        </div>
                    </div>
                </div>
            ) : (
                <div className="code-block" style={{ fontSize: 'var(--font-size-xs)' }}>{content ?? 'No content.'}</div>
            )}
            {cfg && content && (
                <details style={{ marginTop: 'var(--space-lg)' }}>
                    <summary className="text-xs text-secondary" style={{ cursor: 'pointer' }}>Raw JSON</summary>
                    <pre style={{
                        marginTop: 'var(--space-sm)',
                        padding: 'var(--space-md)',
                        background: 'var(--color-bg-primary)',
                        borderRadius: 'var(--radius-sm)',
                        fontFamily: 'var(--font-mono)',
                        fontSize: 'var(--font-size-xs)',
                        color: 'var(--color-text-secondary)',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                    }}>
                        {JSON.stringify(cfg, null, 2)}
                    </pre>
                </details>
            )}
        </div>
    );
}

function OptimizationReportCard({ content }: { content: string | null }) {
    const rpt = tryParseJson(content) as Record<string, unknown> | null;
    return (
        <div className="card">
            <h3 style={{ fontSize: 'var(--font-size-base)', fontWeight: 600, marginBottom: 'var(--space-lg)' }}>
                📊 Optimization Report
            </h3>
            {rpt ? (
                <>
                    <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
                        gap: 'var(--space-lg)',
                        marginBottom: 'var(--space-lg)',
                    }}>
                        {['platform', 'optimizations_applied', 'estimated_improvement', 'risk_level'].map((key) =>
                            rpt[key] !== undefined ? (
                                <div key={key} style={{ padding: 'var(--space-lg)', background: 'var(--color-bg-tertiary)', borderRadius: 'var(--radius-md)' }}>
                                    <div className="text-xs text-secondary mb-xs">{key.replace(/_/g, ' ')}</div>
                                    <div className="font-semibold" style={{ fontSize: 'var(--font-size-sm)' }}>
                                        {String(rpt[key])}
                                    </div>
                                </div>
                            ) : null
                        )}
                    </div>
                    {rpt.recommendations && Array.isArray(rpt.recommendations) && rpt.recommendations.length > 0 && (
                        <div>
                            <div className="text-xs text-secondary mb-sm font-medium">Recommendations</div>
                            <ul style={{ paddingLeft: 'var(--space-lg)' }}>
                                {(rpt.recommendations as string[]).map((r, i) => (
                                    <li key={i} className="text-sm" style={{ marginBottom: 'var(--space-xs)', lineHeight: 1.6 }}>{r}</li>
                                ))}
                            </ul>
                        </div>
                    )}
                </>
            ) : (
                <div className="code-block" style={{ fontSize: 'var(--font-size-xs)' }}>{content ?? 'No content.'}</div>
            )}
        </div>
    );
}

function OptimizedCodeViewer({ content, metadata }: { content: string | null; metadata: Record<string, unknown> | null }) {
    const language = (metadata?.language as string) ?? '';
    return (
        <div className="card">
            <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-lg)' }}>
                <h3 style={{ fontSize: 'var(--font-size-base)', fontWeight: 600 }}>
                    ✨ Optimized Code{language ? ` (${language})` : ''}
                </h3>
                {content && (
                    <button className="btn btn-ghost btn-sm" onClick={() => navigator.clipboard.writeText(content)}>
                        📋 Copy
                    </button>
                )}
            </div>
            {content ? (
                <pre style={{
                    padding: 'var(--space-md)',
                    background: 'var(--color-bg-primary)',
                    borderRadius: 'var(--radius-sm)',
                    fontFamily: 'var(--font-mono)',
                    fontSize: 'var(--font-size-xs)',
                    color: 'var(--color-success)',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    overflow: 'auto',
                    maxHeight: 600,
                    border: '1px solid var(--color-border)',
                }}>
                    {content}
                </pre>
            ) : (
                <p className="text-sm text-secondary">No optimized code available.</p>
            )}
        </div>
    );
}

function GenericContentViewer({ artifact }: { artifact: ArtifactDetail }) {
    return (
        <div className="card">
            <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-lg)' }}>
                <h3 style={{ fontSize: 'var(--font-size-base)', fontWeight: 600 }}>Content</h3>
                {artifact.content && (
                    <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => navigator.clipboard.writeText(artifact.content || '')}
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
    );
}

// ── Page ───────────────────────────────────────────────────────────────

export default function ArtifactViewPage() {
    const params = useParams();
    const taskId = params.taskId as string;
    const artifactId = params.id as string;

    const [artifact, setArtifact] = useState<ArtifactDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        loadArtifact();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [taskId, artifactId]);

    async function loadArtifact() {
        try {
            const res = await getArtifact(taskId, artifactId);
            setArtifact(res);
            setError(null);
        } catch (err: unknown) {
            const detail = err instanceof Error ? err.message : 'Artifact not found';
            setError(detail);
        } finally {
            setLoading(false);
        }
    }

    if (loading) {
        return (
            <div className="loading-page">
                <div className="loading-spinner" aria-hidden="true" /> Loading artifact...
            </div>
        );
    }

    if (!artifact) {
        return (
            <div className="page-container">
                <div className="error-banner">⚠ {error || 'Artifact not found'}</div>
                <Link href={`/tasks/${taskId}`} className="btn btn-ghost">← Back to Task</Link>
            </div>
        );
    }

    const t = artifact.artifact_type;

    return (
        <div className="page-container animate-in">
            {/* Breadcrumb */}
            <div className="flex items-center gap-md mb-lg">
                <Link href={`/tasks/${taskId}`} className="btn btn-ghost btn-sm">← Back to Task</Link>
            </div>

            {/* Header */}
            <div style={{ marginBottom: 'var(--space-2xl)' }}>
                <h1 style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 700, marginBottom: 'var(--space-sm)' }}>
                    {artifact.name}
                </h1>
                <div className="flex items-center gap-md flex-wrap">
                    <span className="badge" style={{ background: 'var(--color-accent-muted)', color: 'var(--color-accent)' }}>
                        {t}
                    </span>
                    <span className="text-sm text-secondary">Created {formatTime(artifact.created_at)}</span>
                    {artifact.content_hash && (
                        <span className="text-xs font-mono text-secondary">{artifact.content_hash}</span>
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

            {/* Specialized content renderers */}
            {t === 'ingestion_config' && (
                <IngestionConfigCard content={artifact.content} />
            )}
            {(t === 'pipeline_definition') && (
                <JsonViewer content={artifact.content} label="🔀 Pipeline Definition" />
            )}
            {t === 'job_config' && (
                <JsonViewer content={artifact.content} label="⏱ Job Configuration" />
            )}
            {t === 'optimization_report' && (
                <OptimizationReportCard content={artifact.content} />
            )}
            {t === 'optimized_code' && (
                <OptimizedCodeViewer content={artifact.content} metadata={artifact.metadata} />
            )}
            {!['ingestion_config', 'pipeline_definition', 'job_config', 'optimization_report', 'optimized_code'].includes(t) && (
                <GenericContentViewer artifact={artifact} />
            )}
        </div>
    );
}

