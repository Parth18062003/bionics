/**
 * AADAP — ChatInput Component
 * ==============================
 * Text input for chat messages with auto-resize.
 * Uses CSS variables for consistent theming.
 */

'use client';

import { useState, useRef, useEffect } from 'react';

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function ChatInput({ onSend, disabled = false, placeholder = 'Type your message...' }: ChatInputProps) {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 120) + 'px';
    }
  }, [value]);

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (trimmed && !disabled) {
      onSend(trimmed);
      setValue('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-end',
        gap: 'var(--space-md)',
        padding: 'var(--space-lg)',
        background: 'var(--color-bg-card)',
        borderTop: '1px solid var(--color-border)',
      }}
    >
      <textarea
        ref={textareaRef}
        style={{
          flex: 1,
          padding: 'var(--space-md) var(--space-lg)',
          fontSize: 'var(--font-size-base)',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg)',
          resize: 'none',
          background: 'var(--color-bg-input)',
          color: 'var(--color-text-primary)',
          fontFamily: 'var(--font-family)',
          lineHeight: 1.5,
          outline: 'none',
          transition: 'border-color var(--transition-fast), box-shadow var(--transition-fast)',
        }}
        rows={1}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        onFocus={(e) => {
          e.target.style.borderColor = 'var(--color-border-focus)';
          e.target.style.boxShadow = '0 0 0 3px var(--color-accent-muted)';
        }}
        onBlur={(e) => {
          e.target.style.borderColor = 'var(--color-border)';
          e.target.style.boxShadow = 'none';
        }}
        placeholder={placeholder}
        disabled={disabled}
      />
      <button
        onClick={handleSubmit}
        disabled={disabled || !value.trim()}
        style={{
          padding: 'var(--space-md) var(--space-lg)',
          borderRadius: 'var(--radius-lg)',
          border: 'none',
          background: disabled || !value.trim()
            ? 'var(--color-bg-tertiary)'
            : 'var(--color-accent)',
          color: disabled || !value.trim()
            ? 'var(--color-text-tertiary)'
            : '#fff',
          cursor: disabled || !value.trim()
            ? 'not-allowed'
            : 'pointer',
          transition: 'all var(--transition-fast)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          opacity: disabled || !value.trim() ? 0.5 : 1,
        }}
        title="Send message"
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M22 2L11 13" />
          <path d="M22 2L15 22L11 13L2 9L22 2Z" />
        </svg>
      </button>
    </div>
  );
}
