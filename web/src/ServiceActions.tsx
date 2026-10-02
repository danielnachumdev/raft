import { useState } from "react";
import { postServiceAction, type ServiceAction } from "./api";

type Props = {
  service: string;
  disabled?: boolean;
  onDone: () => void;
};

/** Start / Stop / Redeploy controls for one Compose service. */
export function ServiceActions(props: Props) {
  const [busy, setBusy] = useState<ServiceAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const locked = props.disabled || busy !== null;

  const run = async (action: ServiceAction) => {
    if (!confirmAction(action, props.service)) return;
    setBusy(action);
    setError(null);
    setMessage(null);
    try {
      await postServiceAction(props.service, action);
      setMessage(`${labelFor(action)} succeeded.`);
      props.onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : `${labelFor(action)} failed.`);
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="panel">
      <h2>Actions</h2>
      <p className="muted actions-hint">
        Start and stop use Compose for this service only. Redeploy re-renders
        and cutovers a running app (or recreates the router). Gate redeploy is
        refused. Apps with scale-to-zero: stop marks idle-zero; start clears it.
      </p>
      <div className="actions-row">
        <ActionButton
          label="Start"
          action="start"
          busy={busy}
          disabled={locked}
          onClick={() => void run("start")}
        />
        <ActionButton
          label="Stop"
          action="stop"
          busy={busy}
          disabled={locked}
          danger
          onClick={() => void run("stop")}
        />
        <ActionButton
          label="Redeploy"
          action="redeploy"
          busy={busy}
          disabled={locked}
          onClick={() => void run("redeploy")}
        />
      </div>
      {message ? <p className="ok-msg" role="status">{message}</p> : null}
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  );
}

function ActionButton(props: {
  label: string;
  action: ServiceAction;
  busy: ServiceAction | null;
  disabled: boolean;
  danger?: boolean;
  onClick: () => void;
}) {
  const loading = props.busy === props.action;
  const className = [
    "action-btn",
    props.danger ? "action-btn-danger" : "",
    loading ? "is-loading" : "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <button
      type="button"
      className={className}
      disabled={props.disabled}
      aria-busy={loading}
      onClick={props.onClick}
    >
      {loading ? (
        <span className="spinner refresh-spinner" aria-hidden="true" />
      ) : null}
      {props.label}
    </button>
  );
}

function confirmAction(action: ServiceAction, service: string): boolean {
  if (action === "start") return true;
  if (action === "stop") {
    return window.confirm(
      `Stop ${service}? Traffic to this service will fail until it is started again.`,
    );
  }
  return window.confirm(
    `Redeploy ${service}? This re-renders and updates the service (brief disruption).`,
  );
}

function labelFor(action: ServiceAction): string {
  if (action === "start") return "Start";
  if (action === "stop") return "Stop";
  return "Redeploy";
}
