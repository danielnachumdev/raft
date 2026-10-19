import { NumberField } from "../NumberField";
import { SectionCard } from "../SectionCard";
import type { SettingsDocument } from "../settingsApi";

export function MetricsSection(props: {
  value: SettingsDocument["metrics"];
  onChange: (next: SettingsDocument["metrics"]) => void;
}) {
  const v = props.value;
  const set = (patch: Partial<SettingsDocument["metrics"]>) =>
    props.onChange({ ...v, ...patch });
  return (
    <SectionCard
      id="settings-metrics"
      title="Metrics"
      hint="Controller sampling for resources.jsonl and http.jsonl under state/metrics/."
    >
      <div className="form-grid">
        <NumberField
          id="metrics-interval"
          label="Interval (seconds)"
          value={v.intervalSeconds}
          min={1}
          step={0.1}
          onChange={(intervalSeconds) => set({ intervalSeconds })}
        />
        <NumberField
          id="metrics-timeout"
          label="Timeout (seconds)"
          value={v.timeoutSeconds}
          min={1}
          step={0.1}
          onChange={(timeoutSeconds) => set({ timeoutSeconds })}
        />
        <NumberField
          id="metrics-batch"
          label="Batch size"
          value={v.batchSize}
          min={1}
          onChange={(batchSize) => set({ batchSize })}
        />
        <NumberField
          id="metrics-flush"
          label="Flush (seconds)"
          value={v.flushSeconds}
          min={1}
          step={0.1}
          onChange={(flushSeconds) => set({ flushSeconds })}
        />
        <NumberField
          id="metrics-age"
          label="Retention max age (days)"
          value={v.retentionMaxAgeDays}
          min={1}
          onChange={(retentionMaxAgeDays) => set({ retentionMaxAgeDays })}
        />
        <NumberField
          id="metrics-bytes"
          label="Retention max bytes"
          value={v.retentionMaxBytes}
          min={1}
          onChange={(retentionMaxBytes) => set({ retentionMaxBytes })}
        />
      </div>
    </SectionCard>
  );
}
