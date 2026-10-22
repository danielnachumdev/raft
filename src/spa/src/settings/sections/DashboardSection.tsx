import { NumberField } from "../NumberField";
import { SectionCard } from "../SectionCard";
import { TextField } from "../TextField";
import { SECRET_MASK, type SettingsDocument, type SettingsSection } from "../settingsApi";

export function DashboardSection(props: {
  value: SettingsDocument["dashboard"];
  meta?: SettingsSection;
  enabled: boolean;
  onEnabledChange: (enabled: boolean) => void;
  onChange: (next: SettingsDocument["dashboard"]) => void;
}) {
  const v = props.value;
  const set = (patch: Partial<SettingsDocument["dashboard"]>) =>
    props.onChange({ ...v, ...patch });
  const setAuth = (patch: Partial<SettingsDocument["dashboard"]["auth"]>) =>
    set({ auth: { ...v.auth, ...patch } });
  const setOauth = (
    patch: Partial<SettingsDocument["dashboard"]["auth"]["oauth"]>,
  ) => setAuth({ oauth: { ...v.auth.oauth, ...patch } });

  return (
    <SectionCard
      id="settings-dashboard"
      title="Dashboard"
      kind={props.meta?.kind ?? "flag"}
      enabled={props.enabled}
      source={props.meta?.source}
      onEnabledChange={props.onEnabledChange}
      hint={
        <>
          Always-on <code>raft-dashboard</code> Compose membership. After
          enabling (or changing auth / TLS / publicHost), save then{" "}
          <code>raft render</code> and Start / Redeploy — settings save alone
          does not start the container. OAuth:{" "}
          <code>host/secrets/dashboard/oauth.env</code> needs{" "}
          <code>OAUTH2_PROXY_CLIENT_ID</code>,{" "}
          <code>OAUTH2_PROXY_CLIENT_SECRET</code>,{" "}
          <code>OAUTH2_PROXY_COOKIE_SECRET</code>,{" "}
          <code>OAUTH2_PROXY_REDIRECT_URL</code> plus an allowlist file.
        </>
      }
    >
      <div className="form-grid">
        <NumberField
          id="dashboard-port"
          label="Port"
          value={v.port}
          min={1}
          onChange={(port) => set({ port })}
        />
        <TextField
          id="dashboard-host"
          label="Public host"
          value={v.publicHost ?? ""}
          onChange={(publicHost) =>
            set({ publicHost: publicHost.trim() || null })
          }
          placeholder="ops.example.com"
          hint="Leave empty for localhost-only. When set, auth.mode must be password, oauth, or external (not none)."
        />
        <label className="field" htmlFor="dashboard-tls">
          TLS
          <select
            id="dashboard-tls"
            value={v.tls}
            onChange={(e) => set({ tls: e.target.value })}
          >
            <option value="off">off (HTTP only)</option>
            <option value="origin">origin (PEMs on host)</option>
            <option value="acme">acme (Let&apos;s Encrypt)</option>
          </select>
          <span className="form-hint">
            origin PEMs:{" "}
            <code>~/.raft/services/raft-dashboard/certs/origin.{"{pem,key}"}</code>
          </span>
        </label>
        <label className="field" htmlFor="dashboard-auth-mode">
          Auth mode
          <select
            id="dashboard-auth-mode"
            value={v.auth.mode}
            onChange={(e) => setAuth({ mode: e.target.value })}
          >
            <option value="none">none (localhost only)</option>
            <option value="password">password</option>
            <option value="oauth">oauth (oauth2-proxy)</option>
            <option value="external">external (forward auth)</option>
          </select>
        </label>
        <TextField
          id="dashboard-password-hash"
          label="Password hash"
          type="password"
          value={v.auth.passwordHash ?? ""}
          onChange={(passwordHash) =>
            setAuth({ passwordHash: passwordHash.trim() || null })
          }
          hint={`Leave as ${SECRET_MASK} to keep stored hash; plaintext (≥8 chars) is hashed on save`}
        />
        <TextField
          id="dashboard-verify-url"
          label="Verify URL (external)"
          value={v.auth.verifyUrl ?? ""}
          onChange={(verifyUrl) =>
            setAuth({ verifyUrl: verifyUrl.trim() || null })
          }
          hint="Forward-auth verify endpoint when mode is external"
        />
        <TextField
          id="dashboard-signin-url"
          label="Sign-in URL (external)"
          value={v.auth.signInUrl ?? ""}
          onChange={(signInUrl) =>
            setAuth({ signInUrl: signInUrl.trim() || null })
          }
        />
        <TextField
          id="dashboard-identity-header"
          label="Identity header"
          value={v.auth.identityHeader}
          onChange={(identityHeader) => setAuth({ identityHeader })}
        />
        <label className="field" htmlFor="dashboard-oauth-provider">
          OAuth provider
          <select
            id="dashboard-oauth-provider"
            value={v.auth.oauth.provider}
            onChange={(e) => setOauth({ provider: e.target.value })}
          >
            <option value="google">google</option>
            <option value="oidc">oidc</option>
          </select>
        </label>
        <TextField
          id="dashboard-oauth-issuer"
          label="OIDC issuer URL"
          value={v.auth.oauth.issuerUrl ?? ""}
          onChange={(issuerUrl) =>
            setOauth({ issuerUrl: issuerUrl.trim() || null })
          }
        />
        <TextField
          id="dashboard-oauth-allowlist"
          label="OAuth allowlist file"
          value={v.auth.oauth.allowlistFile ?? ""}
          onChange={(allowlistFile) =>
            setOauth({
              allowlistFile:
                allowlistFile.trim() ||
                "host/secrets/dashboard/oauth-allowlist.txt",
            })
          }
          hint="One identity per line under the data home (mode 0600)"
        />
      </div>
    </SectionCard>
  );
}
