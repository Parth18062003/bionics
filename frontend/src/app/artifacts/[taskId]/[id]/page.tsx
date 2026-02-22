'use client';

import { useEffect, useState, useCallback, Component, type ReactNode } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { getArtifact, getArtifactVersions, saveArtifactVersion } from '@/api/client';
import type { ArtifactDetail, ArtifactVersionSummary } from '@/api/types';
import { MonacoEditor, DiffViewer, EditorToolbar } from '@/components/editor';

// ── Error Boundary ────────────────────────────────────────────────────────────

class EditorErrorBoundary extends Component<
    { children: ReactNode },
    { hasError: boolean; error: Error | null }
> {
    constructor(props: { children: ReactNode }) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error) {
        console.error('[EditorErrorBoundary] Caught error:', error);
        return { hasError: true, error };
    }

    render() {
        if (this.state.hasError) {
            return (
                <div style={{
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: 'var(--color-bg-primary)',
                    padding: 'var(--space-xl)',
                    color: 'var(--color-text-primary)',
                }}>
                    <div style={{
                        padding: 'var(--space-lg)',
                        background: 'var(--color-error-muted, #ef444420)',
                        borderRadius: 'var(--radius-md)',
                        maxWidth: 600,
                    }}>
                        <h3 style={{ color: 'var(--color-error)', marginBottom: 'var(--space-md)' }}>
                            ⚠️ Editor Error
                        </h3>
                        <pre style={{
                            fontSize: 'var(--font-size-sm)',
                            whiteSpace: 'pre-wrap',
                            color: 'var(--color-text-secondary)',
                        }}>
                            {this.state.error?.message || 'Unknown error occurred'}
                        </pre>
                        <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => window.location.reload()}
                            style={{ marginTop: 'var(--space-md)' }}
                        >
                            🔄 Reload Page
                        </button>
                    </div>
                </div>
            );
        }
        return this.props.children;
    }
}

// ── Helpers ────────────────────────────────────────────────────────────

function formatTime(iso: string): string {
    try {
        return new Date(iso).toLocaleString('en-US', {
            month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit', second: '2-digit',
        });
    } catch { return iso; }
}

function detectLanguageFromContent(content: string | null, metadata: Record<string, unknown> | null): string {
    // Check metadata first
    if (metadata?.language && typeof metadata.language === 'string') {
        return metadata.language;
    }

    if (!content) return 'plaintext';

    // Python/PySpark detection
    if (content.includes('def ') || content.includes('import ')) {
        return 'python';
    }

    // SQL detection
    if (content.includes('SELECT ') || content.includes('FROM ') || content.includes('CREATE TABLE')) {
        return 'sql';
    }

    // JSON detection
    const trimmed = content.trim();
    if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
        try {
            JSON.parse(content);
            return 'json';
        } catch { /* not valid JSON */ }
    }

    // YAML detection
    if (trimmed.includes(':\n') || content.includes('---\n')) {
        return 'yaml';
    }

    return 'plaintext';
}

function getArtifactTypeLabel(type: string): string {
    const labels: Record<string, string> = {
        notebook: 'Notebook',
        pipeline: 'Pipeline',
        pipeline_definition: 'Pipeline Definition',
        job_config: 'Job Configuration',
        ingestion_config: 'Ingestion Config',
        generated_code: 'Generated Code',
        source_code: 'Source Code',
        optimized_code: 'Optimized Code',
        validation_report: 'Validation Report',
        optimization_report: 'Optimization Report',
        decision_explanation: 'Decision Explanation',
        execution_result: 'Execution Result',
    };
    return labels[type] || type;
}

// ── Page ───────────────────────────────────────────────────────────────

export default function ArtifactViewPage() {
    const params = useParams();
    const taskId = params.taskId as string;
    const artifactId = params.id as string;

    const [artifact, setArtifact] = useState<ArtifactDetail | null>(null);
    const [versions, setVersions] = useState<ArtifactVersionSummary[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Editor state
    const [isEditing, setIsEditing] = useState(false);
    const [isDiffView, setIsDiffView] = useState(false);
    const [editedContent, setEditedContent] = useState<string>('');
    const [originalContent, setOriginalContent] = useState<string>('');
    const [selectedVersion, setSelectedVersion] = useState<number>(1);
    const [isSaving, setIsSaving] = useState(false);
    const [saveError, setSaveError] = useState<string | null>(null);
    const [saveSuccess, setSaveSuccess] = useState(false);

    useEffect(() => {
        loadArtifact();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [taskId, artifactId]);

    async function loadArtifact() {
        try {
            const res = await getArtifact(taskId, artifactId);
            setArtifact(res);
            setOriginalContent(res.content || '');
            setEditedContent(res.content || '');
            setSelectedVersion(res.version || 1);

            // Load versions
            try {
                const versionRes = await getArtifactVersions(taskId, artifactId);
                setVersions(versionRes);
            } catch {
                // Versions might not exist yet, that's ok
                setVersions([]);
            }

            setError(null);
        } catch (err: unknown) {
            const detail = err instanceof Error ? err.message : 'Artifact not found';
            setError(detail);
        } finally {
            setLoading(false);
        }
    }

    const language = detectLanguageFromContent(artifact?.content ?? null, artifact?.metadata ?? null);
    const hasUnsavedChanges = editedContent !== originalContent;

    const versionSummaries = versions.map(v => ({
        id: v.id,
        version: v.version,
        created_at: v.created_at,
        content_hash: v.content_hash,
        edit_message: v.edit_message ?? undefined,
    }));

    const handleToggleEditMode = useCallback(() => {
        if (isEditing) {
            // Exiting edit mode - discard changes if any
            setEditedContent(originalContent);
        }
        setIsEditing(!isEditing);
        setIsDiffView(false);
    }, [isEditing, originalContent]);

    const handleToggleDiffView = useCallback(() => {
        setIsDiffView(!isDiffView);
        if (!isDiffView) {
            setIsEditing(false);
        }
    }, [isDiffView]);

    const handleSaveVersion = useCallback(async () => {
        if (!artifact || !hasUnsavedChanges || isSaving) return;

        setIsSaving(true);
        setSaveError(null);
        setSaveSuccess(false);

        try {
            await saveArtifactVersion(taskId, artifactId, {
                content: editedContent,
                edit_message: `Updated via editor at ${new Date().toISOString()}`,
            });

            // Reload to get new version
            await loadArtifact();
            setSaveSuccess(true);
            setTimeout(() => setSaveSuccess(false), 3000);
        } catch (err: unknown) {
            const detail = err instanceof Error ? err.message : 'Failed to save version';
            setSaveError(detail);
        } finally {
            setIsSaving(false);
        }
    }, [artifact, artifactId, taskId, hasUnsavedChanges, isSaving, editedContent]);

    const handleVersionSelect = useCallback(async (version: number) => {
        if (version === selectedVersion) return;

        try {
            const versionArtifact = versions.find(v => v.version === version);
            if (versionArtifact) {
                setSelectedVersion(version);
                // For now, just show the version number changed
                // In a full implementation, we'd load the actual content from that version
            }
        } catch (err: unknown) {
            console.error('Failed to load version:', err);
        }
    }, [selectedVersion, versions]);

    const handleCopy = useCallback(() => {
        if (editedContent) {
            navigator.clipboard.writeText(editedContent);
        }
    }, [editedContent]);

    // Check if this is a code-type artifact that should use Monaco editor
    const isCodeArtifact = artifact && [
        'generated_code',
        'source_code',
        'optimized_code',
        'notebook',
        'pipeline_definition',
        'job_config',
        'ingestion_config',
    ].includes(artifact.artifact_type);

    // Debug logging
    useEffect(() => {
        if (artifact) {
            console.log('[ArtifactPage] Artifact loaded:', {
                name: artifact.name,
                artifact_type: artifact.artifact_type,
                isCodeArtifact,
                contentLength: artifact.content?.length ?? 0,
            });
        }
    }, [artifact, isCodeArtifact]);

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

    // Render code editor for code artifacts
    if (isCodeArtifact) {
        return (
            <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--color-bg-primary)' }}>
                <EditorToolbar
                    artifactName={artifact.name}
                    artifactType={artifact.artifact_type}
                    language={language}
                    currentVersion={selectedVersion}
                    versions={versionSummaries}
                    lastModified={artifact.created_at}
                    isEditing={isEditing}
                    hasUnsavedChanges={hasUnsavedChanges}
                    isDiffView={isDiffView}
                    onToggleEditMode={handleToggleEditMode}
                    onToggleDiffView={handleToggleDiffView}
                    onSaveVersion={handleSaveVersion}
                    onVersionSelect={handleVersionSelect}
                    onCopy={handleCopy}
                />

                {/* Status messages */}
                {saveError && (
                    <div style={{
                        padding: 'var(--space-sm) var(--space-lg)',
                        background: 'var(--color-error-muted, #ef444420)',
                        color: 'var(--color-error)',
                        fontSize: 'var(--font-size-sm)',
                    }}>
                        ⚠ {saveError}
                    </div>
                )}
                {saveSuccess && (
                    <div style={{
                        padding: 'var(--space-sm) var(--space-lg)',
                        background: 'var(--color-success-muted, #10b98120)',
                        color: 'var(--color-success)',
                        fontSize: 'var(--font-size-sm)',
                    }}>
                        ✓ Version saved successfully
                    </div>
                )}
                {isSaving && (
                    <div style={{
                        padding: 'var(--space-sm) var(--space-lg)',
                        background: 'var(--color-accent-muted)',
                        color: 'var(--color-accent)',
                        fontSize: 'var(--font-size-sm)',
                    }}>
                        💾 Saving...
                    </div>
                )}

                {/* Editor area */}
                <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
                    <EditorErrorBoundary>
                        {isDiffView ? (
                            <DiffViewer
                                originalContent={originalContent}
                                modifiedContent={editedContent}
                                language={language}
                                height="100%"
                                readOnly={!isEditing}
                                onModifiedChange={isEditing ? setEditedContent : undefined}
                                showStats={true}
                            />
                        ) : (
                            <MonacoEditor
                                value={editedContent}
                                onChange={isEditing ? setEditedContent : undefined}
                                language={language}
                                readOnly={!isEditing}
                                height="100%"
                                showMinimap={true}
                                showLineNumbers={true}
                            />
                        )}
                    </EditorErrorBoundary>
                </div>
            </div>
        );
    }

    // Render specialized viewers for non-code artifacts
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
                        {getArtifactTypeLabel(artifact.artifact_type)}
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

            {/* Content viewer for reports */}
            {artifact.artifact_type === 'optimization_report' && (
                <OptimizationReportCard content={artifact.content} />
            )}

            {artifact.artifact_type === 'validation_report' && (
                <ValidationReportCard content={artifact.content} />
            )}

            {/* Generic content fallback */}
            {!['optimization_report', 'validation_report'].includes(artifact.artifact_type) && (
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
                        <pre style={{
                            padding: 'var(--space-md)',
                            background: 'var(--color-bg-primary)',
                            borderRadius: 'var(--radius-sm)',
                            fontFamily: 'var(--font-mono)',
                            fontSize: 'var(--font-size-xs)',
                            color: 'var(--color-text-primary)',
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word',
                            overflow: 'auto',
                            maxHeight: 600,
                            border: '1px solid var(--color-border)',
                        }}>
                            {artifact.content}
                        </pre>
                    ) : (
                        <div className="text-sm text-secondary">
                            {artifact.storage_uri
                                ? `Content stored externally: ${artifact.storage_uri}`
                                : 'No content available.'}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

// ── Specialized Renderers ──────────────────────────────────────────────

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

function ValidationReportCard({ content }: { content: string | null }) {
    const rpt = tryParseJson(content) as Record<string, unknown> | null;
    return (
        <div className="card">
            <h3 style={{ fontSize: 'var(--font-size-base)', fontWeight: 600, marginBottom: 'var(--space-lg)' }}>
                ✅ Validation Report
            </h3>
            {rpt ? (
                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
                    gap: 'var(--space-lg)',
                }}>
                    {['status', 'total_tests', 'passed', 'failed', 'warnings'].map((key) =>
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
            ) : (
                <div className="code-block" style={{ fontSize: 'var(--font-size-xs)' }}>{content ?? 'No content.'}</div>
            )}
        </div>
    );
}

function tryParseJson(content: string | null): Record<string, unknown> | null {
    if (!content) return null;
    try { return JSON.parse(content); } catch { return null; }
}
