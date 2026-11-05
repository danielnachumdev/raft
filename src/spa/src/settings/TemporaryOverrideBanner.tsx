import {
  TEMPORARY_OVERRIDE_TITLE,
  temporaryOverrideGuidance,
  temporaryOverrideLead,
} from "./temporaryOverrideMessages";

/**
 * Page-level warning: Settings Save is a temporary host override wiped by
 * the next GitOps sync of host/settings.yaml (CD overwrite — raft does not
 * auto-revert).
 */
export function TemporaryOverrideBanner() {
  return (
    <aside
      className="callout callout-warn settings-temp-override"
      id="settings-temp-override"
      role="status"
    >
      <h2>{TEMPORARY_OVERRIDE_TITLE}</h2>
      <p>{temporaryOverrideLead()}</p>
      <p className="settings-temp-override-guidance">{temporaryOverrideGuidance()}</p>
    </aside>
  );
}
