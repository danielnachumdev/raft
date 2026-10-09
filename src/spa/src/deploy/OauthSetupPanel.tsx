import { useState, type FormEvent } from "react";
import {
  saveGithubConfig,
  type GithubOauthConfig,
  type GithubSession,
} from "./githubApi";
import { CopyableValue } from "./OauthSetupCopy";
import { resolveOauthSetupHints } from "./oauthSetupHints";
import "./OauthSetupPanel.css";

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
  const hints = resolveOauthSetupHints(config, session);

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
        Create a GitHub OAuth App for this localhost serve bind, then paste the
        Client ID and Client Secret below. Values are written to{" "}
        <code>{hints.settings_path}</code> and reloaded here — no CLI-only dance.
        Login later requests scopes <code>{hints.scopes}</code>.
      </p>
      <ol className="oauth-setup-steps">
        <li>
          Open{" "}
          <a
            className="oauth-inline-link"
            href={hints.oauth_app_url}
            target="_blank"
            rel="noreferrer"
            id="oauth-app-create-link"
          >
            Create GitHub OAuth App
          </a>
          . Text fields may be prefilled; if empty, use the values below.
        </li>
        <FieldStep
          label="Application name"
          value={hints.application_name}
          id="oauth-application-name"
        />
        <FieldStep
          label="Homepage URL"
          value={hints.homepage_url}
          id="oauth-homepage-url"
        />
        <FieldStep
          label="Application description"
          value={hints.description}
          id="oauth-description"
        />
        <FieldStep
          label="Authorization callback URL"
          value={hints.callback_url}
          id="oauth-callback-url"
        />
        <li>
          Leave <strong>Enable Device Flow</strong>{" "}
          <em>{hints.enable_device_flow ? "on" : "off (unset)"}</em> — raft uses
          the browser redirect flow, not device codes.
        </li>
        <li>
          Leave{" "}
          <strong>Expire user access tokens</strong>{" "}
          <em>
            {hints.expire_user_access_tokens ? "on" : "off (unset)"}
          </em>{" "}
          (GitHub may label this{" "}
          <strong>Expire user authorization tokens</strong>). Raft stores a
          short-lived serve session and does not refresh expiring GitHub tokens
          yet.
        </li>
        <li>
          Click <strong>Register application</strong>, then paste Client ID and
          Client Secret below (or use mock mode).
        </li>
      </ol>
      <p className="oauth-setup-links">
        <a
          className="refresh deploy-cta"
          href={hints.docs_url}
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

function FieldStep(props: { label: string; value: string; id: string }) {
  return (
    <li>
      Fill in <strong>{props.label}</strong> ={" "}
      <CopyableValue value={props.value} id={props.id} />
    </li>
  );
}
