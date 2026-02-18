'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { listMarketplaceAgents } from '@/api/client';
import type { AgentCatalogEntry } from '@/api/types';
import { Badge, EmptyState, ErrorBanner, LoadingPage, PageHeader } from '@/components/ui';

/* ── Status styling map ─────────────────────────────────────────────── */
const STATUS_STYLES: Record<string, { bg: string; color: string; label: string }> = {
  available:   { bg: 'var(--color-success-muted)', color: 'var(--color-success)',        label: 'Available'   },
  beta:        { bg: 'var(--color-warning-muted)', color: 'var(--color-warning)',        label: 'Beta'        },
  coming_soon: { bg: 'rgba(255,255,255,0.06)',      color: 'var(--color-text-secondary)', label: 'Coming Soon' },
};

const PLATFORM_ICONS: Record<string, string> = {
  'Azure Databricks':  '⚡',
  'Microsoft Fabric':  '🔷',
};

const PLATFORM_FILTERS = ['All', 'Azure Databricks', 'Microsoft Fabric'] as const;
type PlatformFilter = (typeof PLATFORM_FILTERS)[number];

export default function MarketplacePage() {
  const router = useRouter();

  const [agents, setAgents]               = useState<AgentCatalogEntry[]>([]);
  const [loading, setLoading]             = useState(true);
  const [error, setError]                 = useState<string | null>(null);
  const [platformFilter, setPlatformFilter] = useState<PlatformFilter>('All');

  useEffect(() => {
    loadAgents();
  }, []);

  async function loadAgents() {
    try {
      const data = await listMarketplaceAgents();
      setAgents(data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load agents');
    } finally {
      setLoading(false);
    }
  }

  function handleSelectAgent(agent: AgentCatalogEntry) {
    if (agent.status === 'coming_soon') return;
    const params = new URLSearchParams({ agent: agent.id });
    router.push(`/tasks/new?${params}`);
  }

  const filteredAgents =
    platformFilter === 'All'
      ? agents
      : agents.filter((a) => a.platform === platformFilter);

  if (loading) return <LoadingPage message="Loading marketplace…" />;

  return (
    <div className="page-container animate-in">
      <PageHeader
        title="Agent Marketplace"
        subtitle="Select an AI agent to handle your data engineering task."
      />

      {error && <ErrorBanner message={error} />}

      {/* ── Platform filter tabs ── */}
      <div className="flex items-center gap-sm mb-xl flex-wrap" role="tablist" aria-label="Filter by platform">
        {PLATFORM_FILTERS.map((plat) => {
          const count    = plat === 'All' ? agents.length : agents.filter((a) => a.platform === plat).length;
          const isActive = platformFilter === plat;

          return (
            <button
              key={plat}
              role="tab"
              aria-selected={isActive}
              className={`btn btn-sm ${isActive ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => setPlatformFilter(plat)}
            >
              {plat !== 'All' && (
                <span aria-hidden="true">{PLATFORM_ICONS[plat] ?? '🔧'}</span>
              )}
              {plat} ({count})
            </button>
          );
        })}
      </div>

      {/* ── Agent grid ── */}
      {filteredAgents.length === 0 ? (
        <div className="card">
          <EmptyState
            icon="🤖"
            title="No agents found"
            description={`No agents available for "${platformFilter}".`}
          />
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
            gap: 'var(--space-xl)',
          }}
          role="list"
          aria-label="Available agents"
        >
          {filteredAgents.map((agent) => {
            const status     = STATUS_STYLES[agent.status] ?? STATUS_STYLES.coming_soon;
            const isDisabled = agent.status === 'coming_soon';

            return (
              <div
                key={agent.id}
                role="listitem"
                className={`card${!isDisabled ? ' card-clickable' : ''}`}
                style={{
                  padding: 'var(--space-xl)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 'var(--space-lg)',
                  opacity: isDisabled ? 0.55 : 1,
                  cursor: isDisabled ? 'not-allowed' : 'pointer',
                }}
                onClick={() => handleSelectAgent(agent)}
                /* Keyboard support */
                tabIndex={isDisabled ? -1 : 0}
                onKeyDown={(e) => {
                  if (!isDisabled && (e.key === 'Enter' || e.key === ' ')) {
                    e.preventDefault();
                    handleSelectAgent(agent);
                  }
                }}
                aria-label={`${agent.name} — ${status.label}${isDisabled ? ' (unavailable)' : ''}`}
                aria-disabled={isDisabled}
              >
                {/* ── Card header ── */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-md">
                    <div
                      style={{
                        width: 44,
                        height: 44,
                        borderRadius: 'var(--radius-md)',
                        background: 'var(--color-accent-muted)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '1.25rem',
                        flexShrink: 0,
                      }}
                      aria-hidden="true"
                    >
                      {agent.icon}
                    </div>
                    <div>
                      <div className="font-semibold" style={{ fontSize: 'var(--font-size-md)' }}>
                        {agent.name}
                      </div>
                      <div className="text-xs text-secondary flex items-center gap-xs mt-xs">
                        <span aria-hidden="true">{PLATFORM_ICONS[agent.platform] ?? '🔧'}</span>
                        {agent.platform}
                      </div>
                    </div>
                  </div>
                  <Badge bg={status.bg} color={status.color}>
                    {status.label}
                  </Badge>
                </div>

                {/* ── Description ── */}
                <p className="text-sm text-secondary" style={{ lineHeight: 1.6, flex: 1 }}>
                  {agent.description}
                </p>

                {/* ── Language tags ── */}
                {agent.languages.length > 0 && (
                  <div className="flex items-center gap-xs flex-wrap" aria-label="Supported languages">
                    {agent.languages.map((lang) => (
                      <Badge
                        key={lang}
                        bg="var(--color-bg-tertiary)"
                        color="var(--color-text-primary)"
                        style={{ padding: '2px 8px' }}
                      >
                        {lang}
                      </Badge>
                    ))}
                  </div>
                )}

                {/* ── Capabilities ── */}
                {agent.capabilities.length > 0 && (
                  <div
                    style={{
                      padding: 'var(--space-md)',
                      background: 'var(--color-bg-tertiary)',
                      borderRadius: 'var(--radius-sm)',
                    }}
                  >
                    <div
                      className="text-xs text-secondary font-medium mb-sm"
                      id={`caps-label-${agent.id}`}
                    >
                      Capabilities
                    </div>
                    <div
                      className="flex items-center gap-sm flex-wrap"
                      aria-labelledby={`caps-label-${agent.id}`}
                    >
                      {agent.capabilities.map((cap) => (
                        <span key={cap} className="text-xs" style={{ color: 'var(--color-accent)' }}>
                          • {cap}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* ── CTA button ── */}
                <button
                  className={`btn w-full ${isDisabled ? 'btn-ghost' : 'btn-primary'}`}
                  disabled={isDisabled}
                  tabIndex={-1}           /* card itself is already focusable */
                  aria-hidden="true"      /* screen readers use the card's role/label */
                  onClick={(e) => {
                    e.stopPropagation();
                    handleSelectAgent(agent);
                  }}
                  style={{ marginTop: 'auto' }}
                >
                  {isDisabled ? 'Coming Soon' : 'Select Agent →'}
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
