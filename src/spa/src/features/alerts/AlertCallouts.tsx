import { Link } from "react-router-dom";
import { EmptyState } from "../../shared/chrome/StateViews";
import type { AlertStatusPayload } from "./alertsApi";

/** Stale / document-error / no-channel callouts above the alert panels. */
export function AlertCallouts(props: { status: AlertStatusPayload | null; hasChannels: boolean }) {
  return (
    <>
      {props.status?.stale ? (
        <div className="callout callout-warn" id="alerts-stale">
          Alerts have not been evaluated recently.
        </div>
      ) : null}
      {props.status?.documentError ? (
        <div className="callout callout-bad" id="alerts-document-error">
          Alert configuration could not be loaded.
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
      Apply a recommendation above, or use <em>Add rule</em>.
    </EmptyState>
  );
}
