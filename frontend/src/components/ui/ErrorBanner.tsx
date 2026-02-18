/**
 * ErrorBanner — inline destructive alert strip.
 */

interface ErrorBannerProps {
  message: string;
}

export function ErrorBanner({ message }: ErrorBannerProps) {
  return (
    <div className="error-banner" role="alert" aria-live="assertive">
      <span aria-hidden="true">⚠</span>
      {message}
    </div>
  );
}
