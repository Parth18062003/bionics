'use client';

import { useState } from 'react';

// ── Types ─────────────────────────────────────────────────────────────────

export interface ArtifactVersionSummary {
  id: string;
  version: number;
  created_at: string;
  content_hash: string | null;
  edit_message?: string;
}

export interface EditorToolbarProps {
  artifactName: string;
  artifactType: string;
  language: string;
  currentVersion: number;
  versions: ArtifactVersionSummary[];
  lastModified: string;
  author?: string;
  isEditing: boolean;
  hasUnsavedChanges: boolean;
  isDiffView: boolean;
  onToggleEditMode: () => void;
  onToggleDiffView: () => void;
  onSaveVersion: () => void;
  onVersionSelect: (version: number) => void;
  onCopy?: () => void;
}

// ── Badge Component ────────────────────────────────────────────────────────

function TypeBadge({ type }: { type: string }) {
  const typeLabels: Record<string, string> = {
    notebook: '📓 Notebook',
    pipeline: '🔀 Pipeline',
    job_config: '⏱️ Job',
    ingestion_config: '📥 Ingestion',
    source_code: '💻 Code',
    optimized_code: '✨ Optimized',
    validation_report: '✅ Validation',
    optimization_report: '📊 Report',
  };

  return (
    <span
      style={{
        padding: 'var(--space-xs) var(--space-sm)',
        background: 'var(--color-accent-muted)',
        color: 'var(--color-accent)',
        borderRadius: 'var(--radius-sm)',
        fontSize: 'var(--font-size-xs)',
        fontWeight: 500,
        textTransform: 'capitalize',
      }}
    >
      {typeLabels[type] || type}
    </span>
  );
}

function LanguageBadge({ language }: { language: string }) {
  const languageIcons: Record<string, string> = {
    python: '🐍',
    sql: '🗃️',
    json: '📋',
    scala: '☕',
    plaintext: '📝',
  };

  return (
    <span
      style={{
        padding: 'var(--space-xs) var(--space-sm)',
        background: 'var(--color-bg-tertiary)',
        color: 'var(--color-text-secondary)',
        borderRadius: 'var(--radius-sm)',
        fontSize: 'var(--font-size-xs)',
        fontFamily: 'var(--font-mono)',
      }}
    >
      {languageIcons[language] || '📄'} {language}
    </span>
  );
}

// ── Version Dropdown ───────────────────────────────────────────────────────

function VersionDropdown({
  versions,
  currentVersion,
  onSelect,
}: {
  versions: ArtifactVersionSummary[];
  currentVersion: number;
  onSelect: (version: number) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);

  const formatDate = (iso: string) => {
    try {
      return new Date(iso).toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return iso;
    }
  };

  if (versions.length === 0) {
    return (
      <span
        style={{
          padding: 'var(--space-xs) var(--space-sm)',
          color: 'var(--color-text-secondary)',
          fontSize: 'var(--font-size-sm)',
        }}
      >
        v{currentVersion}
      </span>
    );
  }

  return (
    <div style={{ position: 'relative' }}>
      <button
        className="btn btn-ghost btn-sm"
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-xs)',
          fontFamily: 'var(--font-mono)',
        }}
      >
        v{currentVersion}
        <span style={{ fontSize: 10 }}>▼</span>
      </button>

      {isOpen && (
        <>
          <div
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 10,
            }}
            onClick={() => setIsOpen(false)}
          />
          <div
            style={{
              position: 'absolute',
              top: '100%',
              left: 0,
              marginTop: 'var(--space-xs)',
              background: 'var(--color-bg-secondary)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-md)',
              boxShadow: '0 4px 12px rgba(0, 0, 0, 0.3)',
              zIndex: 20,
              minWidth: 180,
              maxHeight: 240,
              overflowY: 'auto',
            }}
          >
            {versions.map((v) => (
              <button
                key={v.id}
                onClick={() => {
                  onSelect(v.version);
                  setIsOpen(false);
                }}
                style={{
                  width: '100%',
                  padding: 'var(--space-sm) var(--space-md)',
                  textAlign: 'left',
                  background:
                    v.version === currentVersion
                      ? 'var(--color-accent-muted)'
                      : 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  color: 'var(--color-text-primary)',
                  fontSize: 'var(--font-size-sm)',
                }}
                onMouseEnter={(e) => {
                  if (v.version !== currentVersion) {
                    e.currentTarget.style.background = 'var(--color-bg-tertiary)';
                  }
                }}
                onMouseLeave={(e) => {
                  if (v.version !== currentVersion) {
                    e.currentTarget.style.background = 'transparent';
                  }
                }}
              >
                <span style={{ fontFamily: 'var(--font-mono)' }}>
                  v{v.version}
                </span>
                <span style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-xs)' }}>
                  {formatDate(v.created_at)}
                </span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ── Unsaved Changes Chip ───────────────────────────────────────────────────

function UnsavedChip() {
  return (
    <span
      style={{
        padding: 'var(--space-xs) var(--space-sm)',
        background: 'var(--color-warning-muted, #f59e0b20)',
        color: 'var(--color-warning, #f59e0b)',
        borderRadius: 'var(--radius-sm)',
        fontSize: 'var(--font-size-xs)',
        fontWeight: 500,
      }}
    >
      Unsaved changes
    </span>
  );
}

// ── Main Toolbar ───────────────────────────────────────────────────────────

export default function EditorToolbar({
  artifactName,
  artifactType,
  language,
  currentVersion,
  versions,
  lastModified,
  author,
  isEditing,
  hasUnsavedChanges,
  isDiffView,
  onToggleEditMode,
  onToggleDiffView,
  onSaveVersion,
  onVersionSelect,
  onCopy,
}: EditorToolbarProps) {
  const formatLastModified = (iso: string) => {
    try {
      return new Date(iso).toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return iso;
    }
  };

  return (
    <div
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 100,
        background: 'var(--color-bg-secondary)',
        borderBottom: '1px solid var(--color-border)',
        padding: 'var(--space-md) var(--space-lg)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 'var(--space-lg)',
        flexWrap: 'wrap',
      }}
    >
      {/* Left: Artifact info */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)', flexWrap: 'wrap' }}>
        <h1
          style={{
            fontSize: 'var(--font-size-lg)',
            fontWeight: 600,
            margin: 0,
            maxWidth: 280,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
          title={artifactName}
        >
          {artifactName}
        </h1>
        <TypeBadge type={artifactType} />
        <LanguageBadge language={language} />
        {hasUnsavedChanges && <UnsavedChip />}
      </div>

      {/* Center: Version selector */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
        <VersionDropdown
          versions={versions}
          currentVersion={currentVersion}
          onSelect={onVersionSelect}
        />
        <span
          style={{
            color: 'var(--color-text-secondary)',
            fontSize: 'var(--font-size-xs)',
          }}
        >
          {formatLastModified(lastModified)}
          {author && ` by ${author}`}
        </span>
      </div>

      {/* Right: Action buttons */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
        {onCopy && (
          <button
            className="btn btn-ghost btn-sm"
            onClick={onCopy}
            title="Copy content"
          >
            📋 Copy
          </button>
        )}

        <button
          className="btn btn-ghost btn-sm"
          onClick={onToggleDiffView}
          style={{
            background: isDiffView ? 'var(--color-accent-muted)' : undefined,
            color: isDiffView ? 'var(--color-accent)' : undefined,
          }}
          title="View diff between original and modified"
        >
          {isDiffView ? '📄 Hide Diff' : '📊 View Diff'}
        </button>

        <button
          className="btn btn-ghost btn-sm"
          onClick={onToggleEditMode}
          style={{
            background: isEditing ? 'var(--color-success-muted, #10b98120)' : undefined,
            color: isEditing ? 'var(--color-success)' : undefined,
          }}
          title={isEditing ? 'Switch to view mode' : 'Switch to edit mode'}
        >
          {isEditing ? '👁️ View Mode' : '✏️ Edit'}
        </button>

        <button
          className="btn btn-primary btn-sm"
          onClick={onSaveVersion}
          disabled={!hasUnsavedChanges}
          title="Save as new version"
        >
          💾 Save Version
        </button>
      </div>
    </div>
  );
}
