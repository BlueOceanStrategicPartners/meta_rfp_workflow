import { errorMessage } from "../../lib/adminApi";
import { IconAlert, IconRefresh } from "./AdminIcons";

type Props = {
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  /** Shown above the server message, e.g. "We couldn't load the overview." */
  errorTitle?: string;
  loadingText?: string;
  compact?: boolean;
};

/** Spinner while loading, or an error with "Try again". Renders nothing otherwise. */
export default function LoadState({
  loading,
  error,
  onRetry,
  errorTitle = "We couldn't load this.",
  loadingText = "Loading…",
  compact,
}: Props) {
  if (error) {
    return (
      <div
        role="alert"
        className={`admin-card flex flex-col items-center gap-3 text-center ${compact ? "px-3 py-4" : "px-4 py-10"}`}
      >
        <span className="admin-danger-text" aria-hidden>
          <IconAlert size={20} />
        </span>
        <div>
          <p className="admin-fg text-sm font-medium">{errorTitle}</p>
          <p className="admin-muted mt-1 text-xs">{errorMessage(error)}</p>
        </div>
        {onRetry ? (
          <button type="button" className="studio-btn-secondary" onClick={onRetry}>
            <IconRefresh />
            Try again
          </button>
        ) : null}
      </div>
    );
  }
  if (loading) {
    return (
      <div
        role="status"
        aria-live="polite"
        className={`flex flex-col items-center justify-center gap-3 ${compact ? "py-4" : "py-12"}`}
      >
        <div className="admin-spinner" aria-hidden />
        <p className="admin-muted text-xs">{loadingText}</p>
      </div>
    );
  }
  return null;
}

/** Small inline "updating" indicator for background polls. */
export function RefreshingDot({ active }: { active: boolean }) {
  if (!active) return null;
  return (
    <span className="admin-faint inline-flex items-center gap-1.5 text-[11px]" role="status">
      <span className="admin-spinner admin-spinner--sm" aria-hidden />
      Updating
    </span>
  );
}
