import { Link } from "react-router-dom";
import { EmptyState } from "../chrome/StateViews";
import type { AlertStatusPayload } from "./alertsApi";

/** Stale / document-error / no-channel callouts above the alert panels. */
export function AlertCallouts(props: { status: AlertStatusPayload | null; hasChannels: boolean }) {
  return (
    <>
      {props.status?.stale ? (
        <div className="callout callout-warn" id="alerts-stale">
          The controller has not evaluated alerts recently. Run <code>raft doctor</code>, then{" "}
          <code>raft up</code> if the controller is missing its <code>host/alerts</code> mount.
        </div>
      ) : null}
      {props.status?.documentError ? (
        <div className="callout callout-bad" id="alerts-document-error">
          {props.status.documentError}
        </div>
      ) : null}
      {!props.hasChannels ? (
        <div className="callout callout-warn" id="alerts-no-channels">
          Rules still evaluate without channels; delivery starts once you add one in{" "}
          <Link to="/settings/notifications">Notifications</Link>.
        </div>
      ) : null}
    </>
  );
}

export function RulesEmpty() {
  return (
    <EmptyState id="alerts-empty" title="No alert rules yet.">
      Apply a recommendation above, use <em>Add rule</em>, import an export, or run{" "}
      <code>raft alerts apply --file rules.yaml</code> on the host. Channels are not required to create a
      rule.
    </EmptyState>
  );
}
