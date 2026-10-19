import { NumberField } from "../NumberField";
import { SectionCard } from "../SectionCard";
import type { SettingsDocument } from "../settingsApi";

export function HealingSection(props: {
  value: SettingsDocument["healing"];
  onChange: (next: SettingsDocument["healing"]) => void;
}) {
  const v = props.value;
  const set = (patch: Partial<SettingsDocument["healing"]>) =>
    props.onChange({ ...v, ...patch });
  return (
    <SectionCard
      id="settings-healing"
      title="Healing"
      hint="Controller self-heal for Apps (never the gate). Separate from per-app scale-to-zero."
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
          id="heal-interval"
          label="Interval (seconds)"
          value={v.intervalSeconds}
          min={1}
          step={0.1}
          onChange={(intervalSeconds) => set({ intervalSeconds })}
        />
        <NumberField
          id="heal-timeout"
          label="Timeout (seconds)"
          value={v.timeoutSeconds}
          min={1}
          step={0.1}
          onChange={(timeoutSeconds) => set({ timeoutSeconds })}
        />
        <NumberField
          id="heal-fail"
          label="Fail threshold"
          value={v.failThreshold}
          min={1}
          onChange={(failThreshold) => set({ failThreshold })}
        />
        <NumberField
          id="heal-cooldown"
          label="Cooldown (seconds)"
          value={v.cooldownSeconds}
          min={1}
          step={0.1}
          onChange={(cooldownSeconds) => set({ cooldownSeconds })}
        />
        <NumberField
          id="heal-restarts"
          label="Max restarts"
          value={v.maxRestarts}
          min={0}
          onChange={(maxRestarts) => set({ maxRestarts })}
        />
        <NumberField
          id="heal-escalate"
          label="Escalate after restarts"
          value={v.escalateAfterRestarts}
          min={0}
          onChange={(escalateAfterRestarts) => set({ escalateAfterRestarts })}
        />
      </div>
    </SectionCard>
  );
}
