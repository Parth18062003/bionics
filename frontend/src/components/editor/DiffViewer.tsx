'use client';

import { useRef, useCallback, useState, useMemo } from 'react';
import dynamic from 'next/dynamic';
import type { editor } from 'monaco-editor';

// Dynamic import to prevent SSR/hydration issues
const DiffEditorComponent = dynamic(
  () => import('@monaco-editor/react').then((mod) => mod.DiffEditor),
  {
    ssr: false,
    loading: () => (
      <div
        style={{
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#1a1a2e',
          borderRadius: 'var(--radius-md)',
          color: 'var(--color-text-secondary)',
        }}
      >
        <div className="loading-spinner" aria-hidden="true" />
        <span style={{ marginLeft: 'var(--space-sm)' }}>Loading diff viewer...</span>
      </div>
    ),
  }
);

// ── Types ─────────────────────────────────────────────────────────────────

export interface DiffViewerProps {
  originalContent: string;
  modifiedContent: string;
  language?: string;
  height?: string | number;
  readOnly?: boolean;
  onModifiedChange?: (value: string) => void;
  showStats?: boolean;
}

export interface DiffStats {
  added: number;
  removed: number;
  unchanged: number;
}

// ── Theme Definition ───────────────────────────────────────────────────────

const DIFF_THEME: editor.IStandaloneThemeData = {
  base: 'vs-dark',
  inherit: true,
  rules: [
    { token: 'comment', foreground: '6b7280' },
    { token: 'keyword', foreground: '818cf8' },
    { token: 'string', foreground: '10b981' },
    { token: 'number', foreground: 'f59e0b' },
    { token: 'type', foreground: '38bdf8' },
    { token: 'function', foreground: 'c084fc' },
  ],
  colors: {
    'editor.background': '#1a1a2e',
    'editor.foreground': '#e5e7eb',
    'editorLineNumber.foreground': '#4b5563',
    'editorLineNumber.activeForeground': '#9ca3af',
    'editor.lineHighlightBackground': '#2d2d44',
    'diffEditor.insertedTextBackground': '#10b98120',
    'diffEditor.insertedLineBackground': '#10b98115',
    'diffEditor.removedTextBackground': '#ef444420',
    'diffEditor.removedLineBackground': '#ef444415',
    'diffEditor.border': '#374151',
  },
};

// ── Diff Stats Component ───────────────────────────────────────────────────

function DiffStatsDisplay({ stats }: { stats: DiffStats }) {
  return (
    <div
      style={{
        display: 'flex',
        gap: 'var(--space-lg)',
        padding: 'var(--space-sm) var(--space-md)',
        background: 'var(--color-bg-tertiary)',
        borderRadius: 'var(--radius-sm)',
        fontSize: 'var(--font-size-sm)',
        marginBottom: 'var(--space-md)',
      }}
    >
      <span style={{ color: 'var(--color-success)' }}>
        +{stats.added} added
      </span>
      <span style={{ color: 'var(--color-error)' }}>
        -{stats.removed} removed
      </span>
      <span style={{ color: 'var(--color-text-secondary)' }}>
        {stats.unchanged} unchanged
      </span>
    </div>
  );
}

// ── Language Detection ─────────────────────────────────────────────────────

function detectLanguage(code: string, explicit?: string): string {
  if (explicit) return explicit;

  if (code.includes('def ') || code.includes('import ')) {
    if (code.includes('spark.') || code.includes('pyspark')) {
      return 'python';
    }
    return 'python';
  }

  if (code.includes('SELECT ') || code.includes('FROM ')) {
    return 'sql';
  }

  if (code.trim().startsWith('{') || code.trim().startsWith('[')) {
    return 'json';
  }

  return 'plaintext';
}

// ── Main Component ─────────────────────────────────────────────────────────

export default function DiffViewer({
  originalContent,
  modifiedContent,
  language,
  height = '100%',
  readOnly = true,
  onModifiedChange,
  showStats = true,
}: DiffViewerProps) {
  const [computedStats, setComputedStats] = useState<DiffStats>({
    added: 0,
    removed: 0,
    unchanged: 0,
  });

  const editorRef = useRef<editor.IStandaloneDiffEditor | null>(null);
  const onModifiedChangeRef = useRef(onModifiedChange);

  // Keep ref updated
  onModifiedChangeRef.current = onModifiedChange;

  // Calculate diff stats from the editor
  const calculateDiffStats = useCallback((diffEditor: editor.IStandaloneDiffEditor) => {
    const modifiedEditor = diffEditor.getModifiedEditor();
    const originalEditor = diffEditor.getOriginalEditor();

    const originalLines = originalEditor.getModel()?.getLinesContent() || [];
    const modifiedLines = modifiedEditor.getModel()?.getLinesContent() || [];

    // Simple line-by-line comparison for stats
    const maxLen = Math.max(originalLines.length, modifiedLines.length);
    let added = 0;
    let removed = 0;
    let unchanged = 0;

    const originalSet = new Set(originalLines);
    const modifiedSet = new Set(modifiedLines);

    for (let i = 0; i < maxLen; i++) {
      const origLine = originalLines[i];
      const modLine = modifiedLines[i];

      if (origLine === undefined) {
        added++;
      } else if (modLine === undefined) {
        removed++;
      } else if (origLine === modLine) {
        unchanged++;
      } else {
        // Line changed - count as one removal and one addition
        if (!modifiedSet.has(origLine)) removed++;
        if (!originalSet.has(modLine)) added++;
      }
    }

    setComputedStats({ added, removed, unchanged });
  }, []);

  const handleEditorDidMount = useCallback(
    (diffEditor: editor.IStandaloneDiffEditor, monaco: typeof import('monaco-editor')) => {
      editorRef.current = diffEditor;

      // Define custom theme
      monaco.editor.defineTheme('aadap-diff-dark', DIFF_THEME);
      monaco.editor.setTheme('aadap-diff-dark');

      // Calculate initial diff stats
      calculateDiffStats(diffEditor);

      // Listen for changes in the modified editor
      const modifiedEditor = diffEditor.getModifiedEditor();
      modifiedEditor.onDidChangeModelContent(() => {
        const value = modifiedEditor.getValue();
        if (onModifiedChangeRef.current) {
          onModifiedChangeRef.current(value);
        }
        calculateDiffStats(diffEditor);
      });
    },
    [calculateDiffStats]
  );

  const detectedLanguage = useMemo(
    () => language || detectLanguage(originalContent || modifiedContent),
    [language, originalContent, modifiedContent]
  );

  return (
    <div style={{ height, width: '100%', display: 'flex', flexDirection: 'column' }}>
      {showStats && (
        <DiffStatsDisplay stats={computedStats} />
      )}
      <div style={{ flex: 1, minHeight: 0 }}>
        <DiffEditorComponent
          height="100%"
          language={detectedLanguage}
          original={originalContent || ''}
          modified={modifiedContent || ''}
          onMount={handleEditorDidMount}
          theme="aadap-diff-dark"
          options={{
            readOnly: readOnly,
            originalEditable: false,
            renderSideBySide: true,
            enableSplitViewResizing: false,
            minimap: { enabled: true },
            lineNumbers: 'on',
            fontSize: 14,
            fontFamily: 'var(--font-mono)',
            wordWrap: 'on',
            automaticLayout: true,
            scrollBeyondLastLine: false,
            renderLineHighlight: 'all',
            ignoreTrimWhitespace: false,
            renderIndicators: true,
            diffWordWrap: 'on',
            padding: { top: 12, bottom: 12 },
            scrollbar: {
              verticalScrollbarSize: 10,
              horizontalScrollbarSize: 10,
              useShadows: false,
            },
          }}
        />
      </div>
    </div>
  );
}

export { DiffStatsDisplay };
