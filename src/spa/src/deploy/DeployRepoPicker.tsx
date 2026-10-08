import type { GithubRepo } from "./githubApi";

export function DeployRepoPicker(props: {
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
  return (
    <section className="deploy-panel" id="repo-picker">
      <h2>Pick a repository</h2>
      <label className="deploy-label">
        Search
        <input
          type="search"
          value={query}
          onChange={(e) => onQuery(e.target.value)}
          placeholder="Filter repos"
          id="repo-search"
        />
      </label>
      <ul className="repo-list" id="repo-list">
        {repos.map((repo) => (
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
        ))}
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
