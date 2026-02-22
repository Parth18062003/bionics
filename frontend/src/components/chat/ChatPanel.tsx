/**
 * AADAP — ChatPanel Component
 * ==============================
 * Slide-out chat panel accessible from any page.
 * Uses CSS variables for consistent theming.
 */

'use client';

import { useEffect, useRef } from 'react';
import Link from 'next/link';
import { useChat } from '@/hooks/useChat';
import { ChatMessage } from '@/components/chat/ChatMessage';
import { ChatInput } from '@/components/chat/ChatInput';

interface ChatPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export function ChatPanel({ isOpen, onClose }: ChatPanelProps) {
  const {
    session,
    isLoading,
    error,
    createSession,
    sendMessage,
  } = useChat();

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Create session on mount
  useEffect(() => {
    if (!session && isOpen) {
      createSession();
    }
  }, [session, isOpen, createSession]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [session?.messages]);

  // Close on escape
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          background: 'var(--color-bg-overlay)',
          zIndex: 40,
        }}
      />

      {/* Panel */}
      <div
        style={{
          position: 'fixed',
          right: 0,
          top: 0,
          height: '100%',
          width: '380px',
          maxWidth: '100vw',
          background: 'var(--color-bg-card)',
          boxShadow: 'var(--shadow-lg)',
          zIndex: 50,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: 'var(--space-lg)',
            borderBottom: '1px solid var(--color-border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                background: 'linear-gradient(135deg, var(--color-accent), #a78bfa)',
                borderRadius: 'var(--radius-sm)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '14px',
                fontWeight: 800,
                color: '#fff',
              }}
            >
              AI
            </div>
            <h2
              style={{
                fontSize: 'var(--font-size-lg)',
                fontWeight: 600,
                color: 'var(--color-text-primary)',
              }}
            >
              Quick Chat
            </h2>
          </div>
          <button
            onClick={onClose}
            style={{
              padding: 'var(--space-sm)',
              background: 'transparent',
              border: 'none',
              color: 'var(--color-text-secondary)',
              cursor: 'pointer',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Messages */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: 'var(--space-lg)',
            background: 'var(--color-bg-secondary)',
          }}
        >
          {!session?.messages.length && !isLoading && (
            <div
              style={{
                textAlign: 'center',
                color: 'var(--color-text-secondary)',
                padding: 'var(--space-2xl) var(--space-lg)',
              }}
            >
              <p style={{ fontSize: 'var(--font-size-sm)', marginBottom: 'var(--space-md)' }}>
                Describe your task and I&apos;ll help you create it.
              </p>
              <p style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-tertiary)' }}>
                Use the full chat page for complex tasks with requirements editing.
              </p>
            </div>
          )}
          {session?.messages.map((message, index) => (
            <ChatMessage key={index} message={message} />
          ))}
          {isLoading && (
            <div
              style={{
                display: 'flex',
                justifyContent: 'flex-start',
                marginBottom: 'var(--space-lg)',
              }}
            >
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
              <div
                style={{
                  background: 'var(--color-bg-card)',
                  border: '1px solid var(--color-border)',
                  borderRadius: 'var(--radius-lg)',
                  padding: 'var(--space-md) var(--space-lg)',
                }}
              >
                <div style={{ display: 'flex', gap: 'var(--space-xs)' }}>
                  <span
                    style={{
                      width: '8px',
                      height: '8px',
                      background: 'var(--color-accent)',
                      borderRadius: '50%',
                      animation: 'bounce 1s infinite',
                      animationDelay: '0ms',
                    }}
                  />
                  <span
                    style={{
                      width: '8px',
                      height: '8px',
                      background: 'var(--color-accent)',
                      borderRadius: '50%',
                      animation: 'bounce 1s infinite',
                      animationDelay: '150ms',
                    }}
                  />
                  <span
                    style={{
                      width: '8px',
                      height: '8px',
                      background: 'var(--color-accent)',
                      borderRadius: '50%',
                      animation: 'bounce 1s infinite',
                      animationDelay: '300ms',
                    }}
                  />
                </div>
              </div>
            </div>
          )}
          {error && (
            <div
              className="error-banner"
              style={{
                margin: 'var(--space-md) 0',
                fontSize: 'var(--font-size-sm)',
              }}
            >
              {error}
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <ChatInput
          onSend={sendMessage}
          disabled={isLoading || !session}
          placeholder="Describe your task..."
        />

        {/* Link to full chat */}
        <div
          style={{
            padding: 'var(--space-md)',
            borderTop: '1px solid var(--color-border)',
            textAlign: 'center',
          }}
        >
          <Link
            href="/chat"
            style={{
              fontSize: 'var(--font-size-sm)',
              color: 'var(--color-accent)',
            }}
          >
            Open full chat →
          </Link>
        </div>
      </div>
    </>
  );
}
