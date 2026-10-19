import { Link } from "react-router-dom";
import { NumberField } from "../NumberField";
import { SectionCard } from "../SectionCard";
import type { SettingsDocument } from "../settingsApi";

export function AlertsSection(props: {
  value: SettingsDocument["alerts"];
  onChange: (next: SettingsDocument["alerts"]) => void;
}) {
  const v = props.value;
  const set = (patch: Partial<SettingsDocument["alerts"]>) =>
    props.onChange({ ...v, ...patch });
  return (
    <SectionCard
      id="settings-alerts"
      title="Alerts"
      hint={
        <>
          Controller evaluation cadence. Rules live under{" "}
          <Link to="/settings/alerts">Settings → Alerts</Link> (
          <code>state/alerts/rules.yaml</code>).
        </>
      }
    >
      <label className="check">
        <input
          type="checkbox"
          checked={v.enabled}
          onChange={(e) => set({ enabled: e.target.checked })}
        />
        Enabled
      </label>
      <div className="form-grid">
        <NumberField
          id="alerts-interval"
          label="Interval (seconds)"
          value={v.intervalSeconds}
          min={15}
          step={0.1}
          onChange={(intervalSeconds) => set({ intervalSeconds })}
          hint="Minimum 15"
        />
        <NumberField
          id="alerts-timeout"
          label="Timeout (seconds)"
          value={v.timeoutSeconds}
          min={1}
          step={0.1}
          onChange={(timeoutSeconds) => set({ timeoutSeconds })}
        />
      </div>
    </SectionCard>
  );
}
