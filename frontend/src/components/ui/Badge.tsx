/**
 * Badge — semantic status chip used throughout the application.
 *
 * Usage:
 *   <Badge color="#6366f1">In Development</Badge>
 *   <Badge color="#10b981" dot>Completed</Badge>
 *   <Badge bg="var(--color-warning-muted)" color="var(--color-warning)">Pending</Badge>
 */

import React from 'react';

interface BadgeProps {
  /** Text/hex color for the badge label and dot. */
  color?: string;
  /** Explicit background override.  Defaults to `${color}20`. */
  bg?: string;
  /** Render a small pulsing dot before the label. */
  dot?: boolean;
  /** Extra inline styles forwarded to the root element. */
  style?: React.CSSProperties;
  className?: string;
  children: React.ReactNode;
}

export function Badge({
  color,
  bg,
  dot = false,
  style,
  className = '',
  children,
}: BadgeProps) {
  const background = bg ?? (color ? `${color}20` : 'var(--color-bg-tertiary)');
  const textColor = color ?? 'var(--color-text-secondary)';

  return (
    <span
      className={`badge ${className}`}
      style={{ background, color: textColor, ...style }}
    >
      {dot && (
        <span
          className="badge-dot"
          style={{ background: textColor }}
          aria-hidden="true"
        />
      )}
      {children}
    </span>
  );
}

/** Convenience wrapper that maps a task/approval state to colours automatically. */
interface StateBadgeProps {
  state: string;
  stateColors: Record<string, string>;
  stateLabels: Record<string, string>;
}

export function StateBadge({ state, stateColors, stateLabels }: StateBadgeProps) {
  const color = stateColors[state] ?? '#6b7280';
  return (
    <Badge color={color} dot>
      {stateLabels[state] ?? state}
    </Badge>
  );
}

/** Environment badge — Production = red, others = cyan. */
export function EnvBadge({ env }: { env: string }) {
  const isProd = env === 'PRODUCTION';
  return (
    <Badge
      bg={isProd ? 'var(--color-danger-muted)' : 'var(--color-info-muted)'}
      color={isProd ? 'var(--color-danger)' : 'var(--color-info)'}
    >
      {env}
    </Badge>
  );
}
