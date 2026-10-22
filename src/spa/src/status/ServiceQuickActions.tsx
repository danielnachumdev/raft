import type { KeyboardEvent, MouseEvent, ReactNode } from "react";
import { Link } from "react-router-dom";
import { serviceLogsPath, type ServiceAction } from "../shared/api";
import { actionAvailability } from "../service/actionAvailability";
import { ServiceActionConfirm } from "../service/ServiceActionConfirm";
import { useServiceActionRunner } from "../service/useServiceActionRunner";
import "./ServiceQuickActions.css";
type Props = {
  service: string;
  name: string;
  status: string;
  onDone: () => void;
};

/** Icon quick actions for a status-table row (logs + up/down/redeploy). */
export function ServiceQuickActions(props: Props) {
  const runner = useServiceActionRunner(props.service, props.onDone);
  const { busy, locked, run } = runner;
  const avail = actionAvailability(props.status);

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
        action="up"
        label={`Up ${props.name}`}
        title={avail.up.enabled ? "Up" : avail.up.hint}
        busy={busy}
        disabled={locked || !avail.up.enabled}
        onClick={() => void run("up")}
      >
        <IconPlay />
      </QuickActionButton>
      <QuickActionButton
        action="down"
        label={`Down ${props.name}`}
        title={avail.down.enabled ? "Down" : avail.down.hint}
        busy={busy}
        disabled={locked || !avail.down.enabled}
        danger
        onClick={() => void run("down")}
      >
        <IconStop />
      </QuickActionButton>
      <QuickActionButton
        action="redeploy"
        label={`Redeploy ${props.name}`}
        title={avail.redeploy.hint}
        busy={busy}
        disabled={locked || !avail.redeploy.enabled}
        onClick={() => void run("redeploy")}
      >
        <IconRedeploy />
      </QuickActionButton>
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
        <span className="spinner btn-spinner" aria-hidden="true" />
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

/** Layers + down arrow — generation refresh, not power restart. */
function IconRedeploy() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
      <path
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 2 2 7l10 5 10-5-10-5zM2 12l10 5 10-5M2 17l10 5 10-5"
      />
    </svg>
  );
}
