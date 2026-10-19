import { NumberField } from "../NumberField";
import { SectionCard } from "../SectionCard";
import { TextField } from "../TextField";
import type { SettingsDocument, SettingsSection } from "../settingsApi";

export function LoggingSection(props: {
  value: SettingsDocument["logging"];
  meta?: SettingsSection;
  onChange: (next: SettingsDocument["logging"]) => void;
}) {
  const v = props.value;
  const set = (patch: Partial<SettingsDocument["logging"]>) =>
    props.onChange({ ...v, ...patch });
  return (
    <SectionCard
      id="settings-logging"
      title="Logging"
      kind={props.meta?.kind ?? "always"}
      enabled
      source={props.meta?.source}
      hint="Host CLI file log under the data home. Terminal output stays plain text."
    >
      <div className="form-grid">
        <TextField
          id="logging-dir"
          label="Directory"
          value={v.dir}
          onChange={(dir) => set({ dir })}
          hint="Relative paths are under RAFT_DATA_HOME"
        />
        <TextField
          id="logging-file"
          label="File"
          value={v.file}
          onChange={(file) => set({ file })}
        />
        <label className="field" htmlFor="logging-level">
          Level
          <select
            id="logging-level"
            value={v.level}
            onChange={(e) => set({ level: e.target.value })}
          >
            {["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"].map((level) => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </select>
        </label>
        <NumberField
          id="logging-age"
          label="Retention max age (days)"
          value={v.retentionMaxAgeDays}
          min={1}
          onChange={(retentionMaxAgeDays) => set({ retentionMaxAgeDays })}
        />
        <NumberField
          id="logging-bytes"
          label="Retention max bytes"
          value={v.retentionMaxBytes}
          min={1}
          onChange={(retentionMaxBytes) => set({ retentionMaxBytes })}
        />
      </div>
    </SectionCard>
  );
}
