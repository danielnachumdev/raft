import type { GithubSession } from "./githubApi";
import "./GithubAccountSwitcher.css";

/** Connected GitHub identities: per-row logout and + to add another. */
export function GithubAccountSwitcher(props: {
  session: GithubSession;
  busy: boolean;
  onLogoutOne: (accountId: string) => void;
}) {
  const { session, busy, onLogoutOne } = props;
  const accounts = session.accounts ?? [];
  const hasExpired = accounts.some((a) => a.expired);

  return (
    <section className="deploy-panel" id="github-session">
      <div className="gh-accounts-header">
        <h2>Connected accounts</h2>
        <a
          className="gh-account-add"
          href="/api/github/login"
          id="github-add-account"
          title="Add GitHub account"
          aria-label="Add GitHub account"
        >
          +
        </a>
      </div>
      <p className="muted">{session.hint}</p>
      {hasExpired ? (
        <p className="muted" id="github-reauth-hint">
          An account session expired. Log it out or add the account again, then
          pick which account to browse repos as.
        </p>
      ) : null}
      <ul className="gh-account-list" id="github-account-list">
        {accounts.map((account) => (
          <li key={account.id} className="gh-account-item">
            <div className="gh-account-meta" id={`github-account-${account.id}`}>
              <span className="gh-account-login">{account.login}</span>
              {account.mock ? (
                <span className="gh-account-tag">mock</span>
              ) : null}
              {account.expired ? (
                <span className="gh-account-tag is-expired">expired</span>
              ) : null}
            </div>
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
        ))}
      </ul>
    </section>
  );
}
