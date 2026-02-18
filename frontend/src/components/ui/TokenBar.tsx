/**
 * TokenBar — visual progress bar for LLM token budget consumption.
 */

interface TokenBarProps {
  used: number;
  budget: number;
}

export function TokenBar({ used, budget }: TokenBarProps) {
  const pct = budget > 0 ? Math.round((used / budget) * 100) : 0;
  const fillColor =
    pct > 90
      ? 'var(--color-danger)'
      : pct > 70
      ? 'var(--color-warning)'
      : 'var(--color-accent)';

  return (
    <div>
      <div
        className="token-bar-track"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Token usage ${pct}%`}
      >
        <div
          className="token-bar-fill"
          style={{ width: `${Math.min(pct, 100)}%`, background: fillColor }}
        />
      </div>
      <div className="token-bar-label">
        {used.toLocaleString()} / {budget.toLocaleString()} tokens ({pct}%)
      </div>
    </div>
  );
}
