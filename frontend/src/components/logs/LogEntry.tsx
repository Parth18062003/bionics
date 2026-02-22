/**
 * AADAP — LogEntry Component
 * ============================
 * Displays a single log entry with level styling and expand functionality.
 */

'use client';

import { useState } from 'react';
import type { TaskLog, LogLevel } from '@/types/log';

interface LogEntryProps {
  log: TaskLog;
  onCorrelationClick?: (correlationId: string) => void;
}

const LEVEL_CONFIG: Record<LogLevel, { color: string; bgColor: string; icon: string }> = {
  DEBUG: {
    color: 'text-gray-600',
    bgColor: 'bg-gray-50 dark:bg-gray-900',
    icon: '🐛',
  },
  INFO: {
    color: 'text-blue-600',
    bgColor: 'bg-blue-50 dark:bg-blue-900/20',
    icon: 'ℹ️',
  },
  WARNING: {
    color: 'text-amber-600',
    bgColor: 'bg-amber-50 dark:bg-amber-900/20',
    icon: '⚠️',
  },
  ERROR: {
    color: 'text-red-600',
    bgColor: 'bg-red-50 dark:bg-red-900/20',
    icon: '❌',
  },
};

export function LogEntry({ log, onCorrelationClick }: LogEntryProps) {
  const [expanded, setExpanded] = useState(false);
  const config = LEVEL_CONFIG[log.level];
  const isLong = log.message.length > 100;
  const displayMessage = expanded ? log.message : log.message.slice(0, 100) + (isLong ? '...' : '');

  return (
    <div className={`flex items-start gap-3 p-3 rounded ${config.bgColor}`}>
      {/* Level Icon */}
      <div className={`flex-shrink-0 ${config.color} text-lg`} title={log.level}>
        {config.icon}
      </div>

      {/* Timestamp */}
      <div className="flex-shrink-0 text-xs text-gray-500 dark:text-gray-400 w-28">
        {new Date(log.timestamp).toLocaleTimeString()}
      </div>

      {/* Source */}
      {log.source && (
        <div className="flex-shrink-0 text-xs text-gray-400 dark:text-gray-500 w-24 truncate" title={`Source: ${log.source}`}>
          {log.source}
        </div>
      )}

      {/* Message */}
      <div className="flex-1 min-w-0">
        <p className={`text-sm ${config.color} whitespace-pre-wrap break-words`}>
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
