import { NumberField } from "../NumberField";
import { SectionCard } from "../SectionCard";
import { TextField } from "../TextField";
import { SECRET_MASK, type SettingsDocument } from "../settingsApi";

export function GithubSection(props: {
  value: SettingsDocument["github"];
  onChange: (next: SettingsDocument["github"]) => void;
}) {
  const v = props.value;
  const set = (patch: Partial<SettingsDocument["github"]>) =>
    props.onChange({ ...v, ...patch });
  return (
    <SectionCard
      id="settings-github"
      title="GitHub"
      hint="OAuth for Add service. RAFT_GITHUB_* env vars override this file when set. Prefer the Add service flow to paste credentials."
    >
      <div className="form-grid">
        <TextField
          id="github-client-id"
          label="Client ID"
          value={v.clientId ?? ""}
          onChange={(clientId) => set({ clientId: clientId.trim() || null })}
          placeholder="Iv1.example"
        />
        <TextField
          id="github-client-secret"
          label="Client secret"
          type="password"
          value={v.clientSecret ?? ""}
          onChange={(clientSecret) =>
            set({ clientSecret: clientSecret.trim() || null })
          }
          hint={`Leave as ${SECRET_MASK} to keep the stored secret`}
        />
        <NumberField
          id="github-ttl"
          label="Session TTL (seconds)"
          value={v.sessionTtlSeconds}
          min={60}
          onChange={(sessionTtlSeconds) => set({ sessionTtlSeconds })}
        />
      </div>
    </SectionCard>
  );
}
