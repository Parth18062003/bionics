/**
 * LoadingPage — full-viewport centred loading indicator.
 */

interface LoadingPageProps {
  message?: string;
}

export function LoadingPage({ message = 'Loading…' }: LoadingPageProps) {
  return (
    <div className="loading-page" role="status" aria-live="polite" aria-label={message}>
      <div className="loading-spinner" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}
