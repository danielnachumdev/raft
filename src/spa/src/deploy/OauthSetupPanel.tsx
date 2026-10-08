import { useState, type FormEvent } from "react";
import {
  saveGithubConfig,
  type GithubOauthConfig,
  type GithubSession,
} from "./githubApi";
import "./OauthSetupPanel.css";

const FALLBACK_OAUTH_APP = "https://github.com/settings/applications/new";
const FALLBACK_DOCS =
  "https://github.com/danielnachumdev/raft/blob/main/docs/serve-github-deploy.md";

/** Instructions + paste-in controls when GitHub OAuth is missing. */
export function OauthSetupPanel(props: {
  session: GithubSession | null;
  config: GithubOauthConfig | null;
  busy: boolean;
  onBusy: (busy: boolean) => void;
  onSaved: () => void;
  onError: (message: string) => void;
}) {
  const { session, config, busy, onBusy, onSaved, onError } = props;
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [mock, setMock] = useState(false);
  const docsUrl = config?.docs_url || session?.docs_url || FALLBACK_DOCS;
  const appUrl =
    config?.oauth_app_url || session?.oauth_app_url || FALLBACK_OAUTH_APP;
  const callback =
    config?.callback_url ||
    session?.callback_url ||
    "http://127.0.0.1:8787/api/github/callback";
  const scopes = config?.scopes || session?.scopes || "read:user repo workflow";

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    onBusy(true);
    onError("");
    try {
      await saveGithubConfig({
        clientId: mock ? undefined : clientId,
        clientSecret: mock ? undefined : clientSecret,
        mock,
      });
      onSaved();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to save OAuth settings");
    } finally {
      onBusy(false);
    }
  };

  return (
    <section className="deploy-panel oauth-setup" id="github-oauth-setup">
      <h2>Set up GitHub OAuth</h2>
      <p className="muted">
        Serve needs a GitHub OAuth App (localhost callback) before Add from
        GitHub can sign you in. Values are written to{" "}
        <code>{config?.settings_path || "~/.raft/settings.yaml"}</code> and
        reloaded in this process — no CLI-only dance.
      </p>
      <ol className="oauth-setup-steps">
        <li>
          Create an OAuth App on GitHub (Developer settings).
        </li>
        <li>
          Set <strong>Authorization callback URL</strong> to{" "}
          <code id="oauth-callback-url">{callback}</code>
        </li>
        <li>
          Request scopes: <code>{scopes}</code>
        </li>
        <li>Paste the Client ID and Client Secret below, then save.</li>
      </ol>
      <p className="oauth-setup-links">
        <a
          className="refresh deploy-cta"
          href={appUrl}
          target="_blank"
          rel="noreferrer"
          id="oauth-app-create-link"
        >
          Create GitHub OAuth App
        </a>
        <a
          className="refresh deploy-cta"
          href={docsUrl}
          target="_blank"
          rel="noreferrer"
          id="oauth-setup-docs-link"
        >
          Setup guide
        </a>
      </p>
      <form className="oauth-setup-form" onSubmit={(e) => void onSubmit(e)}>
        <label className="deploy-label oauth-mock-toggle">
          <span>
            <input
              type="checkbox"
              checked={mock}
              disabled={busy}
              onChange={(e) => setMock(e.target.checked)}
              id="oauth-mock"
            />{" "}
            Use mock mode (local fixture repos; no OAuth App)
          </span>
        </label>
        {!mock ? (
          <>
            <label className="deploy-label">
              Client ID
              <input
                id="oauth-client-id"
                autoComplete="off"
                value={clientId}
                disabled={busy}
                onChange={(e) => setClientId(e.target.value)}
                placeholder="Iv1.…"
                required
              />
            </label>
            <label className="deploy-label">
              Client secret
              <input
                id="oauth-client-secret"
                type="password"
                autoComplete="off"
                value={clientSecret}
                disabled={busy}
                onChange={(e) => setClientSecret(e.target.value)}
                placeholder="Paste client secret"
                required
              />
            </label>
          </>
        ) : null}
        <button
          type="submit"
          className="refresh"
          disabled={busy}
          id="oauth-save-config"
        >
          {busy ? "Saving…" : "Save and continue"}
        </button>
      </form>
    </section>
  );
}
