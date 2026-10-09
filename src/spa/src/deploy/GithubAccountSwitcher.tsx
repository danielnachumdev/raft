import type { GithubSession } from "./githubApi";
import "./GithubAccountSwitcher.css";

/** List connected GitHub accounts; select active, add, or logout one. */
export function GithubAccountSwitcher(props: {
  session: GithubSession;
  busy: boolean;
  onSelect: (accountId: string) => void;
  onLogoutOne: (accountId: string) => void;
  onLogoutActive: () => void;
}) {
  const { session, busy, onSelect, onLogoutOne, onLogoutActive } = props;
  const accounts = session.accounts ?? [];
  const activeId = session.active_account_id ?? null;
  const needsReauth = !session.authenticated && accounts.length > 0;

  return (
    <section className="deploy-panel" id="github-session">
      <h2>GitHub accounts</h2>
      <p className="muted">{session.hint}</p>
      {needsReauth ? (
        <p className="muted" id="github-reauth-hint">
          The active account session expired. Select another account or sign in
          again.
        </p>
      ) : null}
      <ul className="gh-account-list" id="github-account-list">
        {accounts.map((account) => {
          const selected = account.id === activeId;
          return (
            <li
              key={account.id}
              className={
                selected ? "gh-account-item is-active" : "gh-account-item"
              }
            >
              <button
                type="button"
                className="gh-account-select"
                disabled={busy || selected}
                onClick={() => onSelect(account.id)}
                id={`github-account-${account.id}`}
              >
                <span className="gh-account-login">{account.login}</span>
                {account.mock ? (
                  <span className="gh-account-tag">mock</span>
                ) : null}
                {account.expired ? (
                  <span className="gh-account-tag is-expired">expired</span>
                ) : null}
                {selected ? (
                  <span className="gh-account-tag is-active-tag">active</span>
                ) : null}
              </button>
              <button
                type="button"
                className="refresh gh-account-logout"
                disabled={busy}
                onClick={() => onLogoutOne(account.id)}
                id={`github-logout-${account.id}`}
              >
                Log out
              </button>
            </li>
          );
        })}
      </ul>
      <div className="gh-account-actions">
        <a
          className="refresh deploy-cta"
          href="/api/github/login"
          id="github-add-account"
        >
          Add account
        </a>
        {session.authenticated ? (
          <button
            type="button"
            className="refresh"
            onClick={onLogoutActive}
            disabled={busy}
            id="github-logout"
          >
            Log out active
          </button>
        ) : (
          <a
            className="refresh deploy-cta"
            href="/api/github/login"
            id="github-reauth"
          >
            Sign in again
          </a>
        )}
      </div>
    </section>
  );
}
