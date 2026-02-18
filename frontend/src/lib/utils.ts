/**
 * AADAP — Shared Utility Functions
 * ==================================
 * Pure helper functions shared across all pages.
 */

/**
 * Format an ISO timestamp into a human-readable locale string.
 * Falls back to the raw ISO string on parse failure.
 */
export function formatTime(
  iso: string,
  options: Intl.DateTimeFormatOptions = {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }
): string {
  try {
    return new Date(iso).toLocaleString('en-US', options);
  } catch {
    return iso;
  }
}

/**
 * Format an ISO timestamp with seconds included.
 */
export function formatTimeWithSeconds(iso: string): string {
  return formatTime(iso, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

/**
 * Clamp a number between min and max (inclusive).
 */
export function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}
