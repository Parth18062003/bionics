'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { listMarketplaceAgents } from '@/api/client';
import type { AgentCatalogEntry } from '@/api/types';

const STATUS_STYLES: Record<string, { bg: string; color: string; label: string }> = {
    available: { bg: 'var(--color-success-muted)', color: 'var(--color-success)', label: 'Available' },
    beta: { bg: 'var(--color-warning-muted)', color: 'var(--color-warning)', label: 'Beta' },
    coming_soon: { bg: 'rgba(255,255,255,0.06)', color: 'var(--color-text-secondary)', label: 'Coming Soon' },
};

const PLATFORM_ICONS: Record<string, string> = {
    'Azure Databricks': '⚡',
    'Microsoft Fabric': '🔷',
};

const PLATFORM_FILTERS = ['All', 'Azure Databricks', 'Microsoft Fabric'] as const;

export default function MarketplacePage() {
    const router = useRouter();
    const [agents, setAgents] = useState<AgentCatalogEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [platformFilter, setPlatformFilter] = useState<string>('All');

    useEffect(() => {
        loadAgents();
    }, []);

    async function loadAgents() {
        try {
            const data = await listMarketplaceAgents();
            setAgents(data);
            setError(null);
        } catch (err: any) {
            setError(err.detail || err.message || 'Failed to load agents');
        } finally {
            setLoading(false);
        }
    }

    function handleSelectAgent(agent: AgentCatalogEntry) {
        if (agent.status === 'coming_soon') return;
        const params = new URLSearchParams({ agent: agent.id });
        router.push(`/tasks/new?${params}`);
    }

    const filteredAgents = platformFilter === 'All'
        ? agents
        : agents.filter((a) => a.platform === platformFilter);

    if (loading) {
        return <div className="loading-page"><div className="loading-spinner" /> Loading marketplace...</div>;
    }

    return (
        <div className="page-container animate-in">
            <div className="page-header">
                <h1>Agent Marketplace</h1>
                <p>Select an AI agent to handle your data engineering task.</p>
            </div>

            {error && <div className="error-banner">⚠ {error}</div>}

            {/* Platform Filter Tabs */}
            <div className="flex items-center gap-sm" style={{ marginBottom: 'var(--space-xl)' }}>
                {PLATFORM_FILTERS.map((plat) => {
                    const count = plat === 'All' ? agents.length : agents.filter((a) => a.platform === plat).length;
                    const isActive = platformFilter === plat;
                    return (
                        <button
                            key={plat}
                            className={`btn ${isActive ? 'btn-primary' : 'btn-ghost'} btn-sm`}
                            onClick={() => setPlatformFilter(plat)}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 'var(--space-xs)',
                            }}
                        >
                            {plat !== 'All' && <span>{PLATFORM_ICONS[plat] || '🔧'}</span>}
                            {plat} ({count})
                        </button>
                    );
                })}
            </div>

            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
                gap: 'var(--space-xl)',
            }}>
                {filteredAgents.map((agent) => {
                    const status = STATUS_STYLES[agent.status] || STATUS_STYLES.coming_soon;
                    const isDisabled = agent.status === 'coming_soon';

                    return (
                        <div
                            key={agent.id}
                            className="card"
                            style={{
                                padding: 'var(--space-xl)',
                                cursor: isDisabled ? 'not-allowed' : 'pointer',
                                opacity: isDisabled ? 0.55 : 1,
                                transition: 'all var(--transition-base)',
                                display: 'flex',
                                flexDirection: 'column',
                                gap: 'var(--space-lg)',
                            }}
                            onClick={() => handleSelectAgent(agent)}
                            onMouseEnter={(e) => {
                                if (!isDisabled) {
                                    (e.currentTarget as HTMLElement).style.borderColor = 'var(--color-border-hover)';
                                    (e.currentTarget as HTMLElement).style.boxShadow = 'var(--shadow-glow)';
                                }
                            }}
                            onMouseLeave={(e) => {
                                (e.currentTarget as HTMLElement).style.borderColor = '';
                                (e.currentTarget as HTMLElement).style.boxShadow = '';
                            }}
                        >
                            {/* Header */}
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-md">
                                    <div style={{
                                        width: 44,
                                        height: 44,
                                        borderRadius: 'var(--radius-md)',
                                        background: 'var(--color-accent-muted)',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        fontSize: '1.25rem',
                                    }}>
                                        {agent.icon}
                                    </div>
                                    <div>
                                        <div style={{ fontWeight: 600, fontSize: 'var(--font-size-md)' }}>
                                            {agent.name}
                                        </div>
                                        <div className="text-xs text-secondary flex items-center gap-sm">
                                            {PLATFORM_ICONS[agent.platform] || '🔧'} {agent.platform}
                                        </div>
                                    </div>
                                </div>
                                <span className="badge" style={{
                                    background: status.bg,
                                    color: status.color,
                                    fontSize: 'var(--font-size-xs)',
                                }}>
                                    {status.label}
                                </span>
                            </div>

                            {/* Description */}
                            <p className="text-sm text-secondary" style={{ lineHeight: 1.6, flex: 1 }}>
                                {agent.description}
                            </p>

                            {/* Languages */}
                            <div className="flex items-center gap-sm" style={{ flexWrap: 'wrap' }}>
                                {agent.languages.map((lang) => (
                                    <span
                                        key={lang}
                                        className="badge"
                                        style={{
                                            background: 'var(--color-bg-tertiary)',
                                            color: 'var(--color-text-primary)',
                                            fontSize: 'var(--font-size-xs)',
                                            padding: '2px 8px',
                                        }}
                                    >
                                        {lang}
                                    </span>
                                ))}
                            </div>

                            {/* Capabilities */}
                            <div style={{
                                padding: 'var(--space-md)',
                                background: 'var(--color-bg-tertiary)',
                                borderRadius: 'var(--radius-sm)',
                            }}>
                                <div className="text-xs text-secondary" style={{ marginBottom: 'var(--space-sm)', fontWeight: 500 }}>
                                    Capabilities
                                </div>
                                <div className="flex items-center gap-sm" style={{ flexWrap: 'wrap' }}>
                                    {agent.capabilities.map((cap) => (
                                        <span key={cap} className="text-xs" style={{ color: 'var(--color-accent)' }}>
                                            • {cap}
                                        </span>
                                    ))}
                                </div>
                            </div>

                            {/* Action */}
                            <button
                                className={`btn ${isDisabled ? 'btn-ghost' : 'btn-primary'}`}
                                disabled={isDisabled}
                                style={{ width: '100%', marginTop: 'auto' }}
                                onClick={(e) => {
                                    e.stopPropagation();
                                    handleSelectAgent(agent);
                                }}
                            >
                                {isDisabled ? 'Coming Soon' : 'Select Agent →'}
                            </button>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
