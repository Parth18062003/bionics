/**
 * AADAP — ChatTrigger Component
 * ================================
 * Floating action button to open the chat panel.
 * Uses CSS variables for consistent theming.
 */

'use client';

interface ChatTriggerProps {
  onClick: () => void;
  isOpen: boolean;
}

export function ChatTrigger({ onClick, isOpen }: ChatTriggerProps) {
  return (
    <button
      onClick={onClick}
      style={{
        position: 'fixed',
        bottom: 'var(--space-2xl)',
        right: 'var(--space-2xl)',
        width: '56px',
        height: '56px',
        background: 'var(--color-accent)',
        color: '#fff',
        borderRadius: 'var(--radius-full)',
        boxShadow: 'var(--shadow-lg)',
        border: 'none',
        cursor: 'pointer',
        zIndex: 30,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        transition: 'all var(--transition-fast)',
      }}
      title={isOpen ? 'Close chat' : 'Open chat'}
    >
      {isOpen ? (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M18 6L6 18M6 6l12 12" />
        </svg>
      ) : (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
      )}
    </button>
  );
}
