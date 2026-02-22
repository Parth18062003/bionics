/**
 * AADAP — LogViewer Component
 * ================================
 * Full log viewer with auto-scroll.
 */

'use client';

import { useRef, useEffect, useCallback, useState } from 'react';
import type { TaskLog, LogLevel } from '@/types/log';

interface LogViewerProps {
  logs: TaskLog[];
  isLoading?: boolean;
  total?: number;
  onCorrelationClick?: (correlationId: string) => void;
}

const LEVEL_CONFIG: Record<LogLevel, { bgColor: string; textColor: string; icon: string }> = {
  DEBUG: {
    bgColor: 'bg-gray-50 dark:bg-gray-900',
    textColor: 'text-gray-600 dark:text-gray-400',
    icon: '🐛',
  },
  INFO: {
    bgColor: 'bg-blue-50 dark:bg-blue-900/20',
    textColor: 'text-blue-600 dark:text-blue-400',
    icon: 'ℹ️',
  },
  WARNING: {
    bgColor: 'bg-amber-50 dark:bg-amber-900/20',
    textColor: 'text-amber-600 dark:text-amber-400',
    icon: '⚠️',
  },
  ERROR: {
    bgColor: 'bg-red-50 dark:bg-red-900/20',
    textColor: 'text-red-600 dark:text-red-400',
    icon: '❌',
  },
};

export function LogViewer({ logs, isLoading, total, onCorrelationClick }: LogViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [isPaused, setIsPaused] = useState(false);

  // Track scroll position
  const handleScroll = useCallback(() => {
    if (containerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
      const atBottom = scrollHeight - scrollTop - clientHeight < 50;
      setIsAtBottom(atBottom);
    }
  }, []);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (isAtBottom && logs.length > 0 && !isPaused) {
      containerRef.current?.scrollTo({
        top: containerRef.current.scrollHeight,
        behavior: 'smooth',
      });
    }
  }, [isAtBottom, logs.length, isPaused]);

  // Pause auto-scroll on user scroll
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleUserScroll = () => {
      if (containerRef.current) {
        const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
        const atBottom = scrollHeight - scrollTop - clientHeight > 100;
        if (atBottom) {
          setIsPaused(true);
        }
      }
    };

    container.addEventListener('scroll', handleUserScroll);
    return () => {
      container.removeEventListener('scroll', handleUserScroll);
    };
  }, []);

  const scrollToBottom = () => {
    if (containerRef.current) {
      containerRef.current.scrollTo({
        top: containerRef.current.scrollHeight,
        behavior: 'smooth',
      });
      setIsPaused(false);
      setIsAtBottom(true);
    }
  };

  if (isLoading && logs.length === 0) {
    return (
      <div className="space-y-2 p-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="animate-pulse rounded-lg bg-gray-200 dark:bg-gray-700 h-16 w-full" />
        ))}
      </div>
    );
  }

  return (
    <div className="relative h-full">
      {/* Jump to latest button */}
      {isPaused && (
        <button
          onClick={scrollToBottom}
          className="fixed bottom-20 right-8 z-40 bg-blue-500 text-white rounded-full px-4 py-2 shadow-lg hover:bg-blue-600 flex items-center gap-2 text-sm"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
          </svg>
          Jump to latest
        </button>
      )}

      {/* Logs list */}
      <div
        ref={containerRef}
        className="h-full overflow-y-auto p-4"
        onScroll={handleScroll}
      >
        <div className="space-y-2">
          {logs.map((log) => (
            <LogEntry
              key={log.id}
              log={log}
              onCorrelationClick={onCorrelationClick}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

// ── LogEntry Component ───────────────────────────────────────────────────────

interface LogEntryProps {
  log: TaskLog;
  onCorrelationClick?: (correlationId: string) => void;
}

function LogEntry({ log, onCorrelationClick }: LogEntryProps) {
  const [expanded, setExpanded] = useState(false);
  const config = LEVEL_CONFIG[log.level];
  const isLong = log.message.length > 100;
  const displayMessage = expanded || !isLong ? log.message : log.message.slice(0, 100) + '...';

  return (
    <div className={`flex items-start gap-3 p-3 rounded-lg ${config.bgColor}`}>
      {/* Level Icon */}
      <div className={`flex-shrink-0 ${config.textColor} text-lg`} title={log.level}>
        {config.icon}
      </div>

      {/* Timestamp */}
      <div className="flex-shrink-0 text-xs text-gray-500 dark:text-gray-400 w-28 font-mono">
        {new Date(log.timestamp).toLocaleTimeString()}
      </div>

      {/* Source */}
      {log.source && (
        <div className="flex-shrink-0 text-xs text-gray-400 dark:text-gray-500 w-24 truncate" title={log.source}>
          {log.source}
        </div>
      )}

      {/* Message */}
      <div className="flex-1 min-w-0">
        <p className={`text-sm ${config.textColor} whitespace-pre-wrap break-words`}>
          {displayMessage}
          {isLong && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="ml-2 text-xs text-blue-500 hover:text-blue-600"
            >
              {expanded ? 'Show less' : 'Show more'}
            </button>
          )}
        </p>
      </div>

      {/* Correlation ID Chip */}
      {log.correlation_id && onCorrelationClick && (
        <button
          onClick={() => onCorrelationClick(log.correlation_id!)}
          className="flex-shrink-0 px-2 py-1 text-xs text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-800 rounded hover:bg-gray-200 dark:hover:bg-gray-700 truncate max-w-32"
          title="Click to see related logs"
        >
          🔗 {log.correlation_id.slice(0, 8)}
        </button>
      )}
    </div>
  );
}
