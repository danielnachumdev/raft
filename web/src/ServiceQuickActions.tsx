import type { KeyboardEvent, MouseEvent, ReactNode } from "react";
import { Link } from "react-router-dom";
import { serviceLogsPath, type ServiceAction } from "./api";
import { ServiceActionConfirm } from "./ServiceActionConfirm";
import { useServiceActionRunner } from "./useServiceActionRunner";

type Props = {
  service: string;
  name: string;
  onDone: () => void;
};

/** Icon quick actions for a status-table row (logs + start/stop/redeploy). */
export function ServiceQuickActions(props: Props) {
  const runner = useServiceActionRunner(props.service, props.onDone);
  const { busy, error, locked, run } = runner;

  return (
    <div className="quick-actions" onClick={stopRowNav} onKeyDown={stopRowNav}>
      <Link
        to={serviceLogsPath(props.service)}
        className="quick-action"
        aria-label={`View logs for ${props.name}`}
        title="Logs"
        onClick={stopRowNav}
      >
        <IconLogs />
      </Link>
      <QuickActionButton
        action="start"
        label={`Start ${props.name}`}
        title="Start"
        busy={busy}
        disabled={locked}
        onClick={() => void run("start")}
      >
        <IconPlay />
      </QuickActionButton>
      <QuickActionButton
        action="stop"
        label={`Stop ${props.name}`}
        title="Stop"
        busy={busy}
        disabled={locked}
        danger
        onClick={() => void run("stop")}
      >
        <IconStop />
      </QuickActionButton>
      <QuickActionButton
        action="redeploy"
        label={`Redeploy ${props.name}`}
        title="Redeploy"
        busy={busy}
        disabled={locked}
        onClick={() => void run("redeploy")}
      >
        <IconRestart />
      </QuickActionButton>
      {error ? (
        <p className="quick-actions-error" role="alert" title={error}>
          {error}
        </p>
      ) : null}
      <ServiceActionConfirm runner={runner} />
    </div>
  );
}

function QuickActionButton(props: {
  action: ServiceAction;
  label: string;
  title: string;
  busy: ServiceAction | null;
  disabled: boolean;
  danger?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  const loading = props.busy === props.action;
  const className = [
    "quick-action",
    props.danger ? "quick-action-danger" : "",
    loading ? "is-loading" : "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <button
      type="button"
      className={className}
      disabled={props.disabled}
      aria-label={props.label}
      title={props.title}
      aria-busy={loading}
      onClick={(event) => {
        stopRowNav(event);
        props.onClick();
      }}
    >
      {loading ? (
        <span className="spinner refresh-spinner" aria-hidden="true" />
      ) : (
        props.children
      )}
    </button>
  );
}

function stopRowNav(event: MouseEvent | KeyboardEvent) {
  event.stopPropagation();
}

function IconLogs() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
      <path
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"
      />
    </svg>
  );
}

function IconPlay() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
      <path fill="currentColor" d="M8 5v14l11-7z" />
    </svg>
  );
}

function IconStop() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
      <rect x="6" y="6" width="12" height="12" rx="1" fill="currentColor" />
    </svg>
  );
}

function IconRestart() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
      <path
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M21 12a9 9 0 1 1-2.64-6.36M21 3v6h-6"
      />
    </svg>
  );
}
