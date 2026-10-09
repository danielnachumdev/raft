import type { GithubOauthConfig, GithubSession } from "./githubApi";
import { accountCount } from "./githubApi";
import { GithubAccountSwitcher } from "./GithubAccountSwitcher";
import { OauthSetupPanel } from "./OauthSetupPanel";

export function DeploySession(props: {
  session: GithubSession | null;
  config: GithubOauthConfig | null;
  oauthError: string | null;
  needsSetup: boolean;
  busy: boolean;
  onLogout: () => void;
  onLogoutOne: (accountId: string) => void;
  onSelectAccount: (accountId: string) => void;
  onBusy: (busy: boolean) => void;
  onSaved: () => void;
  onError: (message: string) => void;
}) {
  const {
    session,
    config,
    oauthError,
    needsSetup,
    busy,
    onLogout,
    onLogoutOne,
    onSelectAccount,
    onBusy,
    onSaved,
    onError,
  } = props;
  if (needsSetup) {
    return (
      <>
        {oauthError ? (
          <p className="error" role="alert" id="oauth-error-message">
            {oauthError}
          </p>
        ) : null}
        <OauthSetupPanel
          session={session}
          config={config}
          busy={busy}
          onBusy={onBusy}
          onSaved={onSaved}
          onError={onError}
        />
      </>
    );
  }
  if (oauthError) {
    return (
      <section className="deploy-panel" id="github-oauth-error">
        <h2>GitHub authorization failed</h2>
        <p className="error" role="alert" id="oauth-error-message">
          {oauthError}
        </p>
        <p className="muted">
          Serve stays on localhost. Fix OAuth settings or grant the requested
          scopes, then try again.
        </p>
        <a className="refresh deploy-cta" href="/api/github/login" id="oauth-retry">
          Try GitHub login again
        </a>
      </section>
    );
  }
  if (!session) {
    return <p className="muted">Loading session…</p>;
  }
  if (accountCount(session) > 0) {
    return (
      <GithubAccountSwitcher
        session={session}
        busy={busy}
        onSelect={onSelectAccount}
        onLogoutOne={onLogoutOne}
        onLogoutActive={onLogout}
      />
    );
  }
  return (
    <section className="deploy-panel" id="github-login">
      <h2>Connecting to GitHub…</h2>
      <p className="muted">{session.hint}</p>
      <p className="muted">
        Scopes: <code>{session.scopes || "read:user repo workflow"}</code>
      </p>
      <a className="refresh deploy-cta" href="/api/github/login">
        Continue to GitHub
      </a>
    </section>
  );
}
