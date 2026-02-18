'use client';

import { Suspense, useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { createTask, getMarketplaceAgent } from '@/api/client';
import type { AgentCatalogEntry } from '@/api/types';
import { ErrorBanner, LoadingPage, PageHeader } from '@/components/ui';
import { clamp } from '@/lib/utils';

/* ─────────────────────────────────────────────────────────────────────────
   Inner form — uses useSearchParams, so it must live inside <Suspense>.
   ───────────────────────────────────────────────────────────────────────── */
function NewTaskForm() {
  const router       = useRouter();
  const searchParams = useSearchParams();
  const agentParam   = searchParams.get('agent');

  const [title, setTitle]                       = useState('');
  const [description, setDescription]           = useState('');
  const [priority, setPriority]                 = useState(0);
  const [environment, setEnvironment]           = useState('SANDBOX');
  const [autoExecute, setAutoExecute]           = useState(false);
  const [selectedLanguage, setSelectedLanguage] = useState('');
  const [submitting, setSubmitting]             = useState(false);
  const [error, setError]                       = useState<string | null>(null);

  const [agent, setAgent]               = useState<AgentCatalogEntry | null>(null);
  const [agentLoading, setAgentLoading] = useState(!!agentParam);

  useEffect(() => {
    if (!agentParam) return;
    getMarketplaceAgent(agentParam)
      .then((a) => {
        setAgent(a);
        if (a.languages.length > 0) setSelectedLanguage(a.languages[0]);
      })
      .catch(() => setError(`Agent "${agentParam}" not found`))
      .finally(() => setAgentLoading(false));
  }, [agentParam]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;

    setSubmitting(true);
    setError(null);

    try {
      const task = await createTask({
        title:        title.trim(),
        description:  description.trim() || undefined,
        priority,
        environment,
        agent_type:   agent?.id,
        language:     selectedLanguage || agent?.languages[0],
        auto_execute: autoExecute,
      });
      router.push(`/tasks/${task.id}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create task';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  if (agentLoading) return <LoadingPage message="Loading agent…" />;

  const isProd = environment === 'PRODUCTION';

  return (
    <>
      {error && <ErrorBanner message={error} />}

      {/* ── Selected Agent Banner ── */}
      {agent && (
        <div
          className="card mb-xl"
          style={{
            maxWidth: 640,
            padding: 'var(--space-lg)',
            borderLeft: '3px solid var(--color-accent)',
          }}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-md">
              <div
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: 'var(--radius-sm)',
                  background: 'var(--color-accent-muted)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '1rem',
                  flexShrink: 0,
                }}
                aria-hidden="true"
              >
                {agent.icon}
              </div>
              <div>
                <div className="font-semibold" style={{ fontSize: 'var(--font-size-base)' }}>
                  {agent.name}
                </div>
                <div className="text-xs text-secondary mt-xs">
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

          {agent.capabilities.length > 0 && (
            <div className="flex items-center gap-sm mt-md flex-wrap">
              {agent.capabilities.map((cap) => (
                <span key={cap} className="text-xs" style={{ color: 'var(--color-accent)' }}>
                  • {cap}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Form ── */}
      <div className="card" style={{ maxWidth: 640 }}>
        <form onSubmit={handleSubmit} className="flex flex-col gap-xl" noValidate>
          {/* Title */}
          <div className="form-group">
            <label htmlFor="task-title" className="form-label">
              Task Title{' '}
              <span aria-hidden="true" style={{ color: 'var(--color-danger)' }}>*</span>
            </label>
            <input
              id="task-title"
              type="text"
              className="form-input"
              placeholder="e.g., Optimise customer_orders ETL pipeline"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              maxLength={512}
              autoFocus
              aria-required="true"
            />
          </div>

          {/* Description */}
          <div className="form-group">
            <label htmlFor="task-description" className="form-label">
              Description
            </label>
            <textarea
              id="task-description"
              className="form-textarea"
              placeholder="Describe what needs to be done, any constraints, expected outcomes…"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={5}
            />
          </div>

          {/* Environment + Priority */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-xl)' }}>
            <div className="form-group">
              <label htmlFor="task-environment" className="form-label">
                Environment
              </label>
              <select
                id="task-environment"
                className="form-select"
                value={environment}
                onChange={(e) => setEnvironment(e.target.value)}
              >
                <option value="SANDBOX">Sandbox</option>
                <option value="PRODUCTION">Production</option>
              </select>
              {isProd && (
                <div
                  style={{
                    marginTop: 'var(--space-sm)',
                    padding: 'var(--space-sm) var(--space-md)',
                    background: 'var(--color-warning-muted)',
                    border: '1px solid rgba(245,158,11,0.25)',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: 'var(--font-size-xs)',
                    color: '#fbbf24',
                  }}
                  role="alert"
                >
                  ⚠ Production tasks may require human approval for write/destructive
                  operations (INV-01).
                </div>
              )}
            </div>

            <div className="form-group">
              <label htmlFor="task-priority" className="form-label">
                Priority (0–10)
              </label>
              <input
                id="task-priority"
                type="number"
                className="form-input"
                value={priority}
                onChange={(e) => setPriority(clamp(Number(e.target.value), 0, 10))}
                min={0}
                max={10}
              />
            </div>
          </div>

          {/* Language selector */}
          {agent && agent.languages.length > 1 && (
            <div className="form-group">
              <label htmlFor="task-language" className="form-label">
                Language
              </label>
              <select
                id="task-language"
                className="form-select"
                value={selectedLanguage}
                onChange={(e) => setSelectedLanguage(e.target.value)}
              >
                {agent.languages.map((lang) => (
                  <option key={lang} value={lang}>
                    {lang.charAt(0).toUpperCase() + lang.slice(1)}
                  </option>
                ))}
              </select>
              <div className="text-xs text-secondary mt-xs">
                Target language for code generation on {agent.platform}.
              </div>
            </div>
          )}

          {/* Auto-execute toggle */}
          <div className="form-group">
            <label className="flex items-start gap-md" style={{ cursor: 'pointer' }}>
              <input
                type="checkbox"
                id="auto-execute"
                checked={autoExecute}
                onChange={(e) => setAutoExecute(e.target.checked)}
                style={{
                  width: 18,
                  height: 18,
                  marginTop: 2,
                  accentColor: 'var(--color-accent)',
                  cursor: 'pointer',
                  flexShrink: 0,
                }}
              />
              <div>
                <div className="font-medium" style={{ fontSize: 'var(--font-size-base)' }}>
                  Execute Immediately
                </div>
                <div className="text-xs text-secondary mt-xs">
                  {agent?.platform === 'Microsoft Fabric'
                    ? 'Automatically run the full pipeline: LLM code generation → safety analysis → Fabric notebook execution.'
                    : 'Automatically run the full pipeline: LLM code generation → safety analysis → Databricks execution.'}
                </div>
              </div>
            </label>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-md mt-lg">
            <button
              type="submit"
              className="btn btn-primary"
              disabled={submitting || !title.trim()}
            >
              {submitting ? (
                <>
                  <div
                    className="loading-spinner"
                    style={{ width: 16, height: 16 }}
                    aria-hidden="true"
                  />
                  Submitting…
                </>
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
    </>
  );
}

/* ─────────────────────────────────────────────────────────────────────────
   Page shell — wraps the form in <Suspense> as required by Next.js App
   Router when useSearchParams() is used in a client component.
   ───────────────────────────────────────────────────────────────────────── */
export default function NewTaskPage() {
  return (
    <div className="page-container animate-in">
      <PageHeader
        title="Submit New Task"
        subtitle="Describe the data engineering task for autonomous AI execution."
      />
      <Suspense fallback={<LoadingPage message="Loading…" />}>
        <NewTaskForm />
      </Suspense>
    </div>
  );
}
