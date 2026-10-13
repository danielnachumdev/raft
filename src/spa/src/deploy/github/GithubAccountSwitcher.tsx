import { githubLoginHref, type GithubSession } from "./index.ts";
import "./GithubAccountSwitcher.css";

/** Connected GitHub identities: per-row delete and + to add another. */
export function GithubAccountSwitcher(props: {
  session: GithubSession;
  busy: boolean;
  onDeleteOne: (accountId: string) => void;
}) {
  const { session, busy, onDeleteOne } = props;
  const accounts = session.accounts ?? [];
  const hasExpired = accounts.some((a) => a.expired);

  return (
    <section className="deploy-panel" id="github-session">
      <h2>Connected accounts</h2>
      <p className="muted">{session.hint}</p>
      {hasExpired ? (
        <p className="muted" id="github-reauth-hint">
          An account session expired. Delete it or add the account again, then
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
              className="gh-account-delete"
              disabled={busy}
              onClick={() => onDeleteOne(account.id)}
              id={`github-delete-${account.id}`}
              title={`Delete ${account.login}`}
              aria-label={`Delete ${account.login}`}
            >
              <TrashIcon />
            </button>
          </li>
        ))}
        <li className="gh-account-item gh-account-add-row">
          <a
            className="gh-account-add"
            href={githubLoginHref({ add: true })}
            id="github-add-account"
            title="Add GitHub account"
            aria-label="Add GitHub account"
          >
            <PlusIcon />
          </a>
        </li>
      </ul>
    </section>
  );
}

function PlusIcon() {
  return (
    <svg
      className="gh-account-plus"
      viewBox="0 0 16 16"
      width="16"
      height="16"
      aria-hidden="true"
    >
      <path
        fill="currentColor"
        d="M8 2a.75.75 0 0 1 .75.75v4.5h4.5a.75.75 0 0 1 0 1.5h-4.5v4.5a.75.75 0 0 1-1.5 0v-4.5h-4.5a.75.75 0 0 1 0-1.5h4.5v-4.5A.75.75 0 0 1 8 2z"
      />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg
      className="gh-account-trash"
      viewBox="0 0 16 16"
      width="16"
      height="16"
      aria-hidden="true"
    >
      <path
        fill="currentColor"
        d="M6.5 1a.5.5 0 0 0-.5.5V2H2.5a.5.5 0 0 0 0 1H3v10a1.5 1.5 0 0 0 1.5 1.5h7A1.5 1.5 0 0 0 13 13V3h.5a.5.5 0 0 0 0-1H10v-.5a.5.5 0 0 0-.5-.5h-3zM5 3h6v10a.5.5 0 0 1-.5.5h-5A.5.5 0 0 1 5 13V3zm1.5 2a.5.5 0 0 0-.5.5v6a.5.5 0 0 0 1 0v-6a.5.5 0 0 0-.5-.5zm3 0a.5.5 0 0 0-.5.5v6a.5.5 0 0 0 1 0v-6a.5.5 0 0 0-.5-.5z"
      />
    </svg>
  );
}
