import type { ReactNode } from "react";

/** Panel-sized spinner while a page or section loads. */
export function LoadingState(props: { label: string; id?: string }) {
  return (
    <div className="loading" role="status" aria-busy="true" id={props.id}>
      <span className="spinner" aria-hidden="true" />
      <p>{props.label}</p>
    </div>
  );
}

/** Page-level load failure; offers Retry when the caller can reload. */
export function ErrorState(props: {
  message: string;
  id?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="error-state" role="alert" id={props.id}>
      <p>{props.message}</p>
      {props.onRetry ? (
        <button type="button" className="btn btn-sm" onClick={props.onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}

/** Dashed placeholder for an empty collection: title, guidance, optional CTA. */
export function EmptyState(props: {
  title: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
  id?: string;
  className?: string;
}) {
  const className = props.className
    ? `empty-state ${props.className}`
    : "empty-state";
  return (
    <div className={className} id={props.id}>
      <p className="empty-state-title">{props.title}</p>
      {props.children ? <p className="muted">{props.children}</p> : null}
      {props.action}
    </div>
  );
}
