import { NumberField } from "../NumberField";
import { SectionCard } from "../SectionCard";
import { TextField } from "../TextField";
import type { SettingsDocument } from "../settingsApi";

export function AcmeSection(props: {
  value: SettingsDocument["acme"];
  onChange: (next: SettingsDocument["acme"]) => void;
}) {
  const v = props.value;
  const set = (patch: Partial<SettingsDocument["acme"]>) =>
    props.onChange({ ...v, ...patch });
  return (
    <SectionCard
      id="settings-acme"
      title="ACME"
      hint="Let's Encrypt HTTP-01 for tls: acme apps. Use ops@example.com in docs/fixtures only."
    >
      <div className="form-grid">
        <TextField
          id="acme-email"
          label="Email"
          value={v.email ?? ""}
          onChange={(email) => set({ email: email.trim() || null })}
          placeholder="ops@example.com"
        />
        <TextField
          id="acme-directory"
          label="Directory URL"
          value={v.directory}
          onChange={(directory) => set({ directory })}
        />
        <NumberField
          id="acme-renew"
          label="Renew days before expiry"
          value={v.renewDaysBeforeExpiry}
          min={1}
          onChange={(renewDaysBeforeExpiry) => set({ renewDaysBeforeExpiry })}
        />
        <TextField
          id="acme-challenge"
          label="Challenge"
          value={v.challenge}
          onChange={(challenge) => set({ challenge })}
          hint="Only http-01 in v1"
        />
      </div>
    </SectionCard>
  );
}
