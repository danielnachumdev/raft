import type { ServiceAction } from "../shared/api";
import { actionAvailability } from "./actionAvailability";
import { ServiceActionConfirm } from "./ServiceActionConfirm";
import { useServiceActionRunner } from "./useServiceActionRunner";
import "./ServiceActions.css";
type Props = {
  service: string;
  status: string;
  disabled?: boolean;
  onDone: () => void;
};

/** Up / Down / Redeploy toolbar for one Compose service (page header). */
export function ServiceActions(props: Props) {
  const runner = useServiceActionRunner(
    props.service,
    props.onDone,
    props.disabled,
  );
  const { busy, locked, run } = runner;
  const avail = actionAvailability(props.status);

  return (
    <div className="actions-row" role="group" aria-label="Service actions">
      <ActionButton
        label="Up"
        action="up"
        busy={busy}
        disabled={locked || !avail.up.enabled}
        hint={avail.up.hint}
        onClick={() => void run("up")}
      />
      <ActionButton
        label="Down"
        action="down"
        busy={busy}
        disabled={locked || !avail.down.enabled}
        hint={avail.down.hint}
        danger
        onClick={() => void run("down")}
      />
      <ActionButton
        label="Redeploy"
        action="redeploy"
        busy={busy}
        disabled={locked || !avail.redeploy.enabled}
        hint={avail.redeploy.hint}
        onClick={() => void run("redeploy")}
      />
      <ServiceActionConfirm runner={runner} />
    </div>
  );
}

function ActionButton(props: {
  label: string;
  action: ServiceAction;
  busy: ServiceAction | null;
  disabled: boolean;
  hint: string;
  danger?: boolean;
  onClick: () => void;
}) {
  const loading = props.busy === props.action;
  const className = [
    "btn",
    props.danger ? "btn-danger" : "",
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
      title={props.hint}
      id={`service-${props.action}`}
      onClick={props.onClick}
    >
      {loading ? (
        <span className="spinner btn-spinner" aria-hidden="true" />
      ) : null}
      {props.label}
    </button>
  );
}
