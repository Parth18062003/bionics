'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { createTask, getMarketplaceAgent } from '@/api/client';
import type { AgentCatalogEntry } from '@/api/types';

export default function NewTaskPage() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const agentParam = searchParams.get('agent');

    const [title, setTitle] = useState('');
    const [description, setDescription] = useState('');
    const [priority, setPriority] = useState(0);
    const [environment, setEnvironment] = useState('SANDBOX');
    const [autoExecute, setAutoExecute] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Selected agent from marketplace
    const [agent, setAgent] = useState<AgentCatalogEntry | null>(null);
    const [agentLoading, setAgentLoading] = useState(!!agentParam);

    useEffect(() => {
        if (agentParam) {
            getMarketplaceAgent(agentParam)
                .then(setAgent)
                .catch(() => setError(`Agent "${agentParam}" not found`))
                .finally(() => setAgentLoading(false));
        }
    }, [agentParam]);

    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        if (!title.trim()) return;

        setSubmitting(true);
        setError(null);

        try {
            const task = await createTask({
                title: title.trim(),
                description: description.trim() || undefined,
                priority,
                environment,
                agent_type: agent?.id,
                language: agent?.languages[0],
                auto_execute: autoExecute,
            });
            router.push(`/tasks/${task.id}`);
        } catch (err: any) {
            setError(err.detail || err.message || 'Failed to create task');
        } finally {
            setSubmitting(false);
        }
    }

    if (agentLoading) {
        return <div className="loading-page"><div className="loading-spinner" /> Loading agent...</div>;
    }

    return (
        <div className="page-container animate-in">
            <div className="page-header">
                <h1>Submit New Task</h1>
                <p>Describe the data engineering task for autonomous AI execution.</p>
            </div>

            {error && <div className="error-banner">⚠ {error}</div>}

            {/* Selected Agent Banner */}
            {agent && (
                <div className="card" style={{
                    maxWidth: 640,
                    marginBottom: 'var(--space-xl)',
                    padding: 'var(--space-lg)',
                    borderLeft: '3px solid var(--color-accent)',
                }}>
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-md">
                            <div style={{
                                width: 36,
                                height: 36,
                                borderRadius: 'var(--radius-sm)',
                                background: 'var(--color-accent-muted)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontSize: '1rem',
                            }}>
                                {agent.icon}
                            </div>
                            <div>
                                <div style={{ fontWeight: 600, fontSize: 'var(--font-size-base)' }}>{agent.name}</div>
                                <div className="text-xs text-secondary">
                                    {agent.platform} · {agent.languages.join(', ')}
                                </div>
                            </div>
                        </div>
                        <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            onClick={() => router.push('/marketplace')}
                        >
                            Change
                        </button>
                    </div>
                    <div className="flex items-center gap-sm" style={{ marginTop: 'var(--space-md)', flexWrap: 'wrap' }}>
                        {agent.capabilities.map((cap) => (
                            <span key={cap} className="text-xs" style={{ color: 'var(--color-accent)' }}>• {cap}</span>
                        ))}
                    </div>
                </div>
            )}

            <div className="card" style={{ maxWidth: 640 }}>
                <form onSubmit={handleSubmit} className="flex flex-col gap-xl">
                    <div className="form-group">
                        <label className="form-label">Task Title *</label>
                        <input
                            type="text"
                            className="form-input"
                            placeholder="e.g., Optimize customer_orders ETL pipeline"
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            required
                            maxLength={512}
                            autoFocus
                        />
                    </div>

                    <div className="form-group">
                        <label className="form-label">Description</label>
                        <textarea
                            className="form-textarea"
                            placeholder="Describe what needs to be done, any constraints, expected outcomes..."
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            rows={5}
                        />
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-xl)' }}>
                        <div className="form-group">
                            <label className="form-label">Environment</label>
                            <select
                                className="form-select"
                                value={environment}
                                onChange={(e) => setEnvironment(e.target.value)}
                            >
                                <option value="SANDBOX">Sandbox</option>
                                <option value="PRODUCTION">Production</option>
                            </select>
                            {environment === 'PRODUCTION' && (
                                <div style={{
                                    marginTop: 'var(--space-sm)',
                                    padding: 'var(--space-sm) var(--space-md)',
                                    background: 'var(--color-warning-muted)',
                                    borderRadius: 'var(--radius-sm)',
                                    fontSize: 'var(--font-size-xs)',
                                    color: '#fbbf24',
                                }}>
                                    ⚠ Production tasks may require human approval for write/destructive operations (INV-01).
                                </div>
                            )}
                        </div>

                        <div className="form-group">
                            <label className="form-label">Priority (0–10)</label>
                            <input
                                type="number"
                                className="form-input"
                                value={priority}
                                onChange={(e) => setPriority(Math.max(0, Math.min(10, Number(e.target.value))))}
                                min={0}
                                max={10}
                            />
                        </div>
                    </div>

                    {/* Auto-Execute Toggle */}
                    <div className="form-group">
                        <label
                            className="flex items-center gap-md"
                            style={{ cursor: 'pointer' }}
                        >
                            <input
                                type="checkbox"
                                checked={autoExecute}
                                onChange={(e) => setAutoExecute(e.target.checked)}
                                style={{
                                    width: 18,
                                    height: 18,
                                    accentColor: 'var(--color-accent)',
                                    cursor: 'pointer',
                                }}
                            />
                            <div>
                                <div style={{ fontWeight: 500, fontSize: 'var(--font-size-base)' }}>
                                    Execute Immediately
                                </div>
                                <div className="text-xs text-secondary">
                                    Automatically run the full pipeline after submission: LLM code generation → safety analysis → Databricks execution.
                                </div>
                            </div>
                        </label>
                    </div>

                    <div className="flex items-center gap-md" style={{ marginTop: 'var(--space-lg)' }}>
                        <button
                            type="submit"
                            className="btn btn-primary"
                            disabled={submitting || !title.trim()}
                        >
                            {submitting ? (
                                <><div className="loading-spinner" style={{ width: 16, height: 16 }} /> Submitting...</>
                            ) : autoExecute ? (
                                'Submit & Execute'
                            ) : (
                                'Submit Task'
                            )}
                        </button>
                        <button type="button" className="btn btn-ghost" onClick={() => router.back()}>
                            Cancel
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
