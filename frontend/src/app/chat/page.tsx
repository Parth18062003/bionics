/**
 * AADAP — Chat Page
 * ====================
 * Dedicated chat page for conversational task creation.
 * Feels like an AI assistant guiding users through creating data engineering tasks.
 */

'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useChat } from '@/hooks/useChat';
import { ChatMessage } from '@/components/chat/ChatMessage';
import { ChatInput } from '@/components/chat/ChatInput';
import { RequirementsPanel } from '@/components/chat/RequirementsPanel';

export default function ChatPage() {
  const router = useRouter();
  const {
    session,
    isLoading,
    error,
    createSession,
    sendMessage,
    updateRequirements,
    createTask,
    resetSession,
  } = useChat();

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [taskCreated, setTaskCreated] = useState<{ taskId: string; redirectUrl: string } | null>(null);

  // Create session on mount
  useEffect(() => {
    if (!session) {
      createSession();
    }
  }, [session, createSession]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [session?.messages]);

  const handleCreateTask = async () => {
    setIsCreating(true);
    try {
      const result = await createTask();
      if (result) {
        setTaskCreated({ taskId: result.task_id, redirectUrl: result.redirect_url });
      }
    } finally {
      setIsCreating(false);
    }
  };

  // Task created success state
  if (taskCreated) {
    return (
      <div className="page-container animate-in">
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: 'calc(100vh - 200px)',
          }}
        >
          <div
            className="card"
            style={{
              maxWidth: '420px',
              textAlign: 'center',
              padding: 'var(--space-3xl)',
            }}
          >
            {/* Success Icon */}
            <div
              style={{
                width: '72px',
                height: '72px',
                background: 'var(--color-success-muted)',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto var(--space-xl)',
              }}
            >
              <svg
                width="36"
                height="36"
                viewBox="0 0 24 24"
                fill="none"
                stroke="var(--color-success)"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                <path d="M22 4L12 14.01l-3-3" />
              </svg>
            </div>

            <h2
              style={{
                fontSize: 'var(--font-size-xl)',
                fontWeight: 700,
                color: 'var(--color-text-primary)',
                marginBottom: 'var(--space-md)',
              }}
            >
              Task Created Successfully!
            </h2>
            <p
              style={{
                color: 'var(--color-text-secondary)',
                marginBottom: 'var(--space-2xl)',
              }}
            >
              Your data engineering task has been submitted to the platform.
            </p>

            {/* Task ID */}
            <div
              style={{
                background: 'var(--color-bg-tertiary)',
                borderRadius: 'var(--radius-md)',
                padding: 'var(--space-md) var(--space-lg)',
                marginBottom: 'var(--space-xl)',
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--font-size-sm)',
                color: 'var(--color-text-secondary)',
              }}
            >
              Task ID: {taskCreated.taskId.slice(0, 8)}...
            </div>

            {/* Actions */}
            <div
              style={{
                display: 'flex',
                gap: 'var(--space-md)',
              }}
            >
              <button
                onClick={() => router.push(taskCreated.redirectUrl)}
                className="btn btn-primary"
                style={{ flex: 1 }}
              >
                View Task →
              </button>
              <button
                onClick={() => {
                  setTaskCreated(null);
                  resetSession();
                  createSession();
                }}
                className="btn btn-ghost"
                style={{ flex: 1 }}
              >
                Create Another
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        display: 'flex',
        height: 'calc(100vh - var(--nav-height))',
      }}
    >
      {/* ── Chat Section ── */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          minWidth: 0,
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: 'var(--space-lg) var(--space-2xl)',
            borderBottom: '1px solid var(--color-border)',
            background: 'var(--color-bg-card)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)' }}>
            <Link
              href="/dashboard"
              style={{
                color: 'var(--color-text-secondary)',
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-xs)',
                fontSize: 'var(--font-size-sm)',
              }}
            >
              ← Dashboard
            </Link>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)' }}>
            <button
              onClick={() => {
                resetSession();
                createSession();
              }}
              className="btn btn-ghost btn-sm"
            >
              + New Chat
            </button>
          </div>
        </div>

        {/* Messages */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: 'var(--space-xl) var(--space-2xl)',
            background: 'var(--color-bg-secondary)',
          }}
        >
          {/* Welcome message when no messages */}
          {!session?.messages.length && !isLoading && (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                minHeight: '400px',
                textAlign: 'center',
                padding: 'var(--space-2xl)',
              }}
            >
              {/* AI Avatar */}
              <div
                style={{
                  width: '64px',
                  height: '64px',
                  background: 'linear-gradient(135deg, var(--color-accent), #a78bfa)',
                  borderRadius: 'var(--radius-lg)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '28px',
                  fontWeight: 800,
                  color: '#fff',
                  marginBottom: 'var(--space-xl)',
                  boxShadow: 'var(--shadow-glow)',
                }}
              >
                AI
              </div>

              <h1
                style={{
                  fontSize: 'var(--font-size-xl)',
                  fontWeight: 700,
                  color: 'var(--color-text-primary)',
                  marginBottom: 'var(--space-md)',
                }}
              >
                Create a New Task
              </h1>
              <p
                style={{
                  color: 'var(--color-text-secondary)',
                  maxWidth: '480px',
                  marginBottom: 'var(--space-2xl)',
                  lineHeight: 1.6,
                }}
              >
                Describe your data engineering task in natural language. I&apos;ll help you define the requirements and create a structured task for the agents to execute.
              </p>

              {/* Example prompts */}
              <div
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: 'var(--space-md)',
                  justifyContent: 'center',
                }}
              >
                {[
                  'Build a pipeline to ingest sales data from S3',
                  'Create a data quality validation job',
                  'Migrate customer data from legacy system',
                ].map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => sendMessage(prompt)}
                    style={{
                      padding: 'var(--space-md) var(--space-lg)',
                      background: 'var(--color-bg-card)',
                      border: '1px solid var(--color-border)',
                      borderRadius: 'var(--radius-lg)',
                      color: 'var(--color-text-secondary)',
                      fontSize: 'var(--font-size-sm)',
                      cursor: 'pointer',
                      transition: 'all var(--transition-fast)',
                    }}
                  >
                    &quot;{prompt}&quot;
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Message list */}
          {session?.messages.map((message, index) => (
            <ChatMessage key={index} message={message} />
          ))}

          {/* Loading indicator */}
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
                <div
                  style={{
                    display: 'flex',
                    gap: 'var(--space-xs)',
                  }}
                >
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

          {/* Error message */}
          {error && (
            <div
              className="error-banner"
              style={{
                margin: 'var(--space-lg) 0',
              }}
            >
              {error}
              <button
                onClick={() => createSession()}
                className="btn btn-ghost btn-sm"
                style={{ marginLeft: 'var(--space-md)' }}
              >
                Retry
              </button>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <ChatInput
          onSend={sendMessage}
          disabled={isLoading || !session}
          placeholder="Describe your data engineering task..."
        />
      </div>

      {/* ── Requirements Panel (right sidebar) ── */}
      <div
        style={{
          width: '380px',
          flexShrink: 0,
          borderTop: '1px solid var(--color-border)',
        }}
      >
        <RequirementsPanel
          requirements={session?.current_requirements ?? null}
          onUpdate={updateRequirements}
          onCreateTask={handleCreateTask}
          isCreating={isCreating}
        />
      </div>
    </div>
  );
}
