import { Link } from "react-router-dom";
import type { AlertStatusPayload } from "./alertsApi";

/** Stale / document-error / no-channel callouts above the alert panels. */
export function AlertCallouts(props: { status: AlertStatusPayload | null; hasChannels: boolean }) {
  return (
    <>
      {props.status?.stale ? (
        <div className="callout callout-warn" id="alerts-stale">
          The controller has not evaluated alerts recently. Run <code>raft doctor</code>, then{" "}
          <code>raft up</code> if the controller is missing its <code>state/alerts</code> mount.
        </div>
      ) : null}
      {props.status?.documentError ? (
        <div className="callout callout-bad" id="alerts-document-error">
          {props.status.documentError}
        </div>
      ) : null}
      {!props.hasChannels ? (
        <div className="callout callout-warn" id="alerts-no-channels">
          Alerts will evaluate but nothing will be delivered. Add a channel in{" "}
          <Link to="/settings/notifications">Notifications</Link>.
        </div>
      ) : null}
    </>
  );
}

export function RulesEmpty() {
  return (
    <div className="empty-state" id="alerts-empty">
      <p>
        <strong>No alert rules yet.</strong>
      </p>
      <p className="muted">
        Use <em>Add rule</em>, import an exported file, or run <code>raft alerts apply --file rules.yaml</code> on the
        host.
      </p>
    </div>
  );
}
