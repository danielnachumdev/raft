import { NumberField } from "../NumberField";
import { SectionCard } from "../SectionCard";
import type { SettingsDocument, SettingsSection } from "../settingsApi";

export function ServiceLogsSection(props: {
  value: SettingsDocument["serviceLogs"];
  meta?: SettingsSection;
  enabled: boolean;
  onEnabledChange: (enabled: boolean) => void;
  onChange: (next: SettingsDocument["serviceLogs"]) => void;
}) {
  const v = props.value;
  const set = (patch: Partial<SettingsDocument["serviceLogs"]>) =>
    props.onChange({ ...v, ...patch });
  return (
    <SectionCard
      id="settings-service-logs"
      title="Service logs"
      kind={props.meta?.kind ?? "flag"}
      enabled={props.enabled}
      source={props.meta?.source}
      onEnabledChange={props.onEnabledChange}
      hint="Retained Compose stdout under state/service-logs/ (0600). May contain secrets."
    >
      <div className="settings-checks">
        <label className="check">
          <input
            type="checkbox"
            checked={v.includeEdge}
            onChange={(e) => set({ includeEdge: e.target.checked })}
          />
          Include edge (gate / router / controller / dashboard)
        </label>
      </div>
      <div className="form-grid">
        <NumberField
          id="slog-interval"
          label="Interval (seconds)"
          value={v.intervalSeconds}
          min={1}
          step={0.1}
          onChange={(intervalSeconds) => set({ intervalSeconds })}
        />
        <NumberField
          id="slog-timeout"
          label="Timeout (seconds)"
          value={v.timeoutSeconds}
          min={1}
          step={0.1}
          onChange={(timeoutSeconds) => set({ timeoutSeconds })}
        />
        <NumberField
          id="slog-age"
          label="Retention max age (days)"
          value={v.retentionMaxAgeDays}
          min={1}
          onChange={(retentionMaxAgeDays) => set({ retentionMaxAgeDays })}
        />
        <NumberField
          id="slog-bytes"
          label="Retention max bytes"
          value={v.retentionMaxBytes}
          min={1}
          onChange={(retentionMaxBytes) => set({ retentionMaxBytes })}
        />
      </div>
    </SectionCard>
  );
}
