import type { GithubOauthConfig, GithubSession } from "./github/index.ts";
import { accountCount, githubLoginHref } from "./github/index.ts";
import { GithubAccountSwitcher } from "./github/GithubAccountSwitcher";
import { OauthSetupPanel } from "./oauth/OauthSetupPanel";

export function DeploySession(props: {
  session: GithubSession | null;
  config: GithubOauthConfig | null;
  oauthError: string | null;
  needsSetup: boolean;
  forceInstructions: boolean;
  busy: boolean;
  onDeleteOne: (accountId: string) => void;
  onBusy: (busy: boolean) => void;
  onSaved: () => void;
  onContinueConfigured: () => void;
  onError: (message: string) => void;
}) {
  const {
    session,
    config,
    oauthError,
    needsSetup,
    forceInstructions,
    busy,
    onDeleteOne,
    onBusy,
    onSaved,
    onContinueConfigured,
    onError,
  } = props;
  if (needsSetup || forceInstructions) {
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
          alreadyConfigured={
            !needsSetup && session?.oauth_configured === true
          }
          onBusy={onBusy}
          onSaved={onSaved}
          onContinue={onContinueConfigured}
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
        <a
          className="refresh btn-primary deploy-cta"
          href={githubLoginHref()}
          id="oauth-retry"
        >
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
        onDeleteOne={onDeleteOne}
      />
    );
  }
  return (
    <section className="deploy-panel" id="github-login">
      <h2>Connect GitHub</h2>
      <p className="muted">{session.hint}</p>
      <p className="muted">
        Scopes: <code>{session.scopes || "read:user repo workflow"}</code>
      </p>
      <a
        className="refresh btn-primary deploy-cta"
        href={githubLoginHref()}
        id="github-continue"
      >
        Continue to GitHub
      </a>
    </section>
  );
}
