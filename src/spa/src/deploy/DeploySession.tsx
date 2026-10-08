import type { GithubSession } from "./githubApi";

export function DeploySession(props: {
  session: GithubSession | null;
  oauthError: string | null;
  busy: boolean;
  onLogout: () => void;
}) {
  const { session, oauthError, busy, onLogout } = props;
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
  if (!session.authenticated) {
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
  return (
    <section className="deploy-panel" id="github-session">
      <h2>Signed in</h2>
      <p>
        GitHub user <strong>{session.login}</strong>
        {session.mock ? " (mock)" : ""}
      </p>
      <p className="muted">{session.hint}</p>
      <button
        type="button"
        className="refresh"
        onClick={onLogout}
        disabled={busy}
        id="github-logout"
      >
        Log out
      </button>
    </section>
  );
}
