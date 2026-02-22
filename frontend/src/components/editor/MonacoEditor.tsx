'use client';

import { useRef, useCallback } from 'react';
import dynamic from 'next/dynamic';
import type { editor } from 'monaco-editor';

// Dynamic import to prevent SSR/hydration issues
const MonacoEditorComponent = dynamic(
  () => import('@monaco-editor/react').then((mod) => mod.default),
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
        <span style={{ marginLeft: 'var(--space-sm)' }}>Loading editor...</span>
      </div>
    ),
  }
);

// ── Types ─────────────────────────────────────────────────────────────────

export interface MonacoEditorProps {
  value: string;
  onChange?: (value: string) => void;
  language?: string;
  readOnly?: boolean;
  height?: string | number;
  showMinimap?: boolean;
  showLineNumbers?: boolean;
  theme?: string;
}

// ── Language Detection ─────────────────────────────────────────────────────

function detectLanguage(code: string, explicit?: string): string {
  if (explicit) return explicit;

  // Python/PySpark detection
  if (code.includes('def ') || code.includes('import ')) {
    if (code.includes('spark.') || code.includes('pyspark') || code.includes('SparkSession')) {
      return 'python';
    }
    return 'python';
  }

  // SQL detection
  if (code.includes('SELECT ') || code.includes('FROM ') || code.includes('CREATE TABLE')) {
    return 'sql';
  }

  // JSON detection
  if (code.trim().startsWith('{') || code.trim().startsWith('[')) {
    return 'json';
  }

  return 'plaintext';
}

// ── Theme Definition ───────────────────────────────────────────────────────

const EDITOR_THEME: editor.IStandaloneThemeData = {
  base: 'vs-dark',
  inherit: true,
  rules: [
    { token: 'comment', foreground: '6b7280' },
    { token: 'keyword', foreground: '818cf8' },
    { token: 'string', foreground: '10b981' },
    { token: 'number', foreground: 'f59e0b' },
    { token: 'type', foreground: '38bdf8' },
    { token: 'function', foreground: 'c084fc' },
    { token: 'variable', foreground: 'e5e7eb' },
  ],
  colors: {
    'editor.background': '#1a1a2e',
    'editor.foreground': '#e5e7eb',
    'editorLineNumber.foreground': '#4b5563',
    'editorLineNumber.activeForeground': '#9ca3af',
    'editor.lineHighlightBackground': '#2d2d44',
    'editor.selectionBackground': '#3b3b5c',
    'editor.inactiveSelectionBackground': '#2d2d44',
    'editorCursor.foreground': '#818cf8',
    'editorWhitespace.foreground': '#374151',
    'editorIndentGuide.background': '#374151',
    'editorIndentGuide.activeBackground': '#4b5563',
    'editor.findMatchBackground': '#3b3b5c',
    'editor.findMatchHighlightBackground': '#2d2d44',
  },
};

// ── Component ──────────────────────────────────────────────────────────────

export default function MonacoEditor({
  value,
  onChange,
  language,
  readOnly = false,
  height = '100%',
  showMinimap = true,
  showLineNumbers = true,
  theme = 'aadap-dark',
}: MonacoEditorProps) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);

  const handleEditorDidMount = useCallback(
    (editor: editor.IStandaloneCodeEditor, monaco: typeof import('monaco-editor')) => {
      editorRef.current = editor;

      // Define custom theme
      monaco.editor.defineTheme('aadap-dark', EDITOR_THEME);
      monaco.editor.setTheme('aadap-dark');

      // Focus the editor
      editor.focus();
    },
    []
  );

  const handleChange = useCallback(
    (value: string | undefined) => {
      if (onChange && value !== undefined) {
        onChange(value);
      }
    },
    [onChange]
  );

  const detectedLanguage = language || detectLanguage(value);

  return (
    <div style={{ height, width: '100%', overflow: 'hidden' }}>
      <MonacoEditorComponent
        height="100%"
        language={detectedLanguage}
        value={value}
        onChange={handleChange}
        onMount={handleEditorDidMount}
        theme={theme}
        options={{
          readOnly,
          minimap: { enabled: showMinimap },
          lineNumbers: showLineNumbers ? 'on' : 'off',
          fontSize: 14,
          fontFamily: 'var(--font-mono)',
          fontLigatures: true,
          wordWrap: 'on',
          automaticLayout: true,
          scrollBeyondLastLine: false,
          renderLineHighlight: 'all',
          cursorBlinking: 'smooth',
          cursorSmoothCaretAnimation: 'on',
          smoothScrolling: true,
          padding: { top: 16, bottom: 16 },
          scrollbar: {
            verticalScrollbarSize: 10,
            horizontalScrollbarSize: 10,
            useShadows: false,
          },
          overviewRulerLanes: 0,
          hideCursorInOverviewRuler: true,
          overviewRulerBorder: false,
        }}
      />
    </div>
  );
}
