/**
 * AADAP — ChatMessage Component
 * ================================
 * Displays a single chat message with role-based styling.
 * Uses CSS variables for consistent theming.
 */

'use client';

import type { ChatMessage as ChatMessageType } from '@/types/chat';

interface ChatMessageProps {
  message: ChatMessageType;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';
  const isAssistant = message.role === 'assistant';

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        marginBottom: 'var(--space-lg)',
      }}
    >
      {/* Assistant avatar */}
      {isAssistant && (
        <div
          style={{
            width: '32px',
            height: '32px',
            borderRadius: 'var(--radius-md)',
            background: 'linear-gradient(135deg, var(--color-accent), #a78bfa)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '14px',
            fontWeight: 800,
            color: '#fff',
            marginRight: 'var(--space-md)',
            flexShrink: 0,
          }}
        >
          AI
        </div>
      )}

      <div
        style={{
          maxWidth: '75%',
          borderRadius: 'var(--radius-lg)',
          padding: 'var(--space-md) var(--space-lg)',
          background: isUser
            ? 'var(--color-accent)'
            : 'var(--color-bg-card)',
          color: isUser
            ? '#fff'
            : 'var(--color-text-primary)',
          border: isUser
            ? 'none'
            : '1px solid var(--color-border)',
          boxShadow: 'var(--shadow-sm)',
        }}
      >
        {/* Message content */}
        <div
          style={{
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            lineHeight: 1.6,
            fontSize: 'var(--font-size-base)',
          }}
        >
          {message.content}
        </div>

        {/* Timestamp */}
        <div
          style={{
            fontSize: 'var(--font-size-xs)',
            marginTop: 'var(--space-xs)',
            color: isUser
              ? 'rgba(255, 255, 255, 0.7)'
              : 'var(--color-text-tertiary)',
          }}
        >
          {new Date(message.timestamp).toLocaleTimeString()}
        </div>
      </div>

      {/* User avatar */}
      {isUser && (
        <div
          style={{
            width: '32px',
            height: '32px',
            borderRadius: 'var(--radius-md)',
            background: 'var(--color-bg-tertiary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '14px',
            fontWeight: 600,
            color: 'var(--color-text-secondary)',
            marginLeft: 'var(--space-md)',
            flexShrink: 0,
          }}
        >
          You
        </div>
      )}
    </div>
  );
}
