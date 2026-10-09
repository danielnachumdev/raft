import type { GithubAccountPublic, GithubRepo } from "./githubApi";

export function DeployRepoPicker(props: {
  accounts: GithubAccountPublic[];
  accountId: string;
  onAccount: (accountId: string) => void;
  query: string;
  onQuery: (q: string) => void;
  repos: GithubRepo[];
  selected: GithubRepo | null;
  onSelect: (r: GithubRepo) => void;
  refValue: string;
  onRef: (r: string) => void;
  busy: boolean;
  onDeploy: () => void;
}) {
  const {
    accounts,
    accountId,
    onAccount,
    query,
    onQuery,
    repos,
    selected,
    onSelect,
    refValue,
    onRef,
    busy,
    onDeploy,
  } = props;
  const accountReady = Boolean(accountId);
  return (
    <section className="deploy-panel" id="repo-picker">
      <h2>Pick a repository</h2>
      <p className="muted">
        Repos you own or belong to (org / collaborator). Filter as you type.
      </p>
      <label className="deploy-label" htmlFor="github-view-as">
        View repos as
        <select
          id="github-view-as"
          value={accountId}
          disabled={busy || accounts.length === 0}
          onChange={(e) => onAccount(e.target.value)}
        >
          <option value="">Select an account…</option>
          {accounts.map((account) => (
            <option key={account.id} value={account.id}>
              {account.login}
              {account.mock ? " (mock)" : ""}
            </option>
          ))}
        </select>
      </label>
      {!accountReady ? (
        <p className="muted" id="repo-account-required">
          Choose which connected account to list repos from, then filter and
          pick a repository.
        </p>
      ) : null}
      <label className="deploy-label">
        Filter
        <input
          type="search"
          value={query}
          onChange={(e) => onQuery(e.target.value)}
          placeholder="Filter by owner/name"
          id="repo-search"
          disabled={!accountReady || busy}
        />
      </label>
      <ul className="repo-list" id="repo-list">
        {accountReady
          ? repos.map((repo) => (
              <li key={repo.full_name}>
                <button
                  type="button"
                  className={
                    selected?.full_name === repo.full_name
                      ? "repo-item is-selected"
                      : "repo-item"
                  }
                  onClick={() => onSelect(repo)}
                >
                  <span>{repo.full_name}</span>
                  <span className="muted">
                    {repo.private ? "private" : "public"} · {repo.default_branch}
                  </span>
                </button>
              </li>
            ))
          : null}
      </ul>
      {selected ? (
        <div className="deploy-confirm" id="deploy-confirm">
          <label className="deploy-label">
            Ref (branch or tag)
            <input
              type="text"
              value={refValue}
              onChange={(e) => onRef(e.target.value)}
              id="deploy-ref"
            />
          </label>
          <p className="muted">
            Manifest path: <code>.raft/app.yaml</code> only (v1).
          </p>
          <button
            type="button"
            className="refresh deploy-cta"
            disabled={busy}
            onClick={onDeploy}
            id="deploy-confirm-btn"
          >
            Deploy {selected.full_name}
          </button>
        </div>
      ) : null}
    </section>
  );
}
