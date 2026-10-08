import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  fetchDeployJob,
  fetchGithubRepos,
  fetchGithubSession,
  logoutGithub,
  startGithubDeploy,
  type DeployJob,
  type GithubRepo,
  type GithubSession,
} from "./githubApi";
import "./DeployPage.css";

const POLL_MS = 1000;

/** Temporary GitHub login → pick one repo → auto-deploy + next steps. */
export function DeployPage() {
  const [session, setSession] = useState<GithubSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [repos, setRepos] = useState<GithubRepo[]>([]);
  const [selected, setSelected] = useState<GithubRepo | null>(null);
  const [ref, setRef] = useState("main");
  const [job, setJob] = useState<DeployJob | null>(null);
  const [busy, setBusy] = useState(false);

  const refreshSession = useCallback(async () => {
    setError(null);
    try {
      setSession(await fetchGithubSession());
    } catch {
      setError("Failed to load GitHub session.");
    }
  }, []);

  useEffect(() => {
    void refreshSession();
  }, [refreshSession]);

  useEffect(() => {
    if (!session?.authenticated) {
      setRepos([]);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const list = await fetchGithubRepos(query);
        if (!cancelled) setRepos(list);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to list repos");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [session?.authenticated, query]);

  useEffect(() => {
    if (!job || job.status === "succeeded" || job.status === "failed") return;
    const id = window.setInterval(() => {
      void fetchDeployJob(job.id)
        .then(setJob)
        .catch((err) =>
          setError(err instanceof Error ? err.message : "Deploy poll failed"),
        );
    }, POLL_MS);
    return () => window.clearInterval(id);
  }, [job]);

  const onSelect = (repo: GithubRepo) => {
    setSelected(repo);
    setRef(repo.default_branch || "main");
    setJob(null);
  };

  const onDeploy = async () => {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      setJob(await startGithubDeploy(selected.full_name, ref));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Deploy failed to start");
    } finally {
      setBusy(false);
    }
  };

  const onLogout = async () => {
    setBusy(true);
    try {
      await logoutGithub();
      setSession(await fetchGithubSession());
      setSelected(null);
      setJob(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Logout failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page deploy-page">
      <header className="header">
        <div>
          <p className="brand">raft</p>
          <h1>Deploy from GitHub</h1>
          <p className="muted header-updating">
            Temporary login for repo selection and deploy assist. Serve stays
            localhost / SSH tunnel — not a public multi-user console.
          </p>
        </div>
        <Link className="refresh" to="/">
          Stack status
        </Link>
      </header>

      {error ? (
        <p className="error" role="alert" id="deploy-error">
          {error}
        </p>
      ) : null}

      <SessionPanel
        session={session}
        busy={busy}
        onLogout={() => void onLogout()}
      />

      {session?.authenticated ? (
        <>
          <RepoPicker
            query={query}
            onQuery={setQuery}
            repos={repos}
            selected={selected}
            onSelect={onSelect}
            refValue={ref}
            onRef={setRef}
            busy={busy}
            onDeploy={() => void onDeploy()}
          />
          {job ? <DeployProgress job={job} /> : null}
        </>
      ) : null}
    </div>
  );
}

function SessionPanel(props: {
  session: GithubSession | null;
  busy: boolean;
  onLogout: () => void;
}) {
  const { session, busy, onLogout } = props;
  if (!session) {
    return <p className="muted">Loading session…</p>;
  }
  if (!session.authenticated) {
    return (
      <section className="deploy-panel" id="github-login">
        <h2>Sign in with GitHub</h2>
        <p className="muted">{session.hint}</p>
        <p className="muted">
          Scopes requested: <code>{session.scopes || "read:user repo"}</code>{" "}
          (private repo listing; deploy keys are pasted manually).
        </p>
        <a className="refresh deploy-cta" href="/api/github/login">
          {session.mock ? "Continue with mock GitHub" : "Sign in with GitHub"}
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

function RepoPicker(props: {
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

function DeployProgress(props: { job: DeployJob }) {
  const { job } = props;
  return (
    <section className="deploy-panel" id="deploy-progress">
      <h2>Deploy progress</h2>
      <p>
        Status: <strong id="deploy-status">{job.status}</strong>
        {job.app_name ? (
          <>
            {" "}
            · app <code>{job.app_name}</code>
          </>
        ) : null}
      </p>
      <ul className="deploy-steps">
        {job.steps.map((step) => (
          <li key={step.name}>
            <strong>{step.name}</strong> — {step.status}
            {step.detail ? <span className="muted"> ({step.detail})</span> : null}
          </li>
        ))}
      </ul>
      {job.error ? (
        <p className="error" role="alert" id="deploy-job-error">
          {job.error}
        </p>
      ) : null}
      {job.deploy_pubkey ? (
        <div className="deploy-pubkey" id="deploy-pubkey">
          <p className="muted">
            Public deploy key (safe to copy; never share private keys):
          </p>
          <code className="deploy-pubkey-value">{job.deploy_pubkey}</code>
        </div>
      ) : null}
      {job.next_steps.length > 0 ? (
        <div className="next-steps" id="next-steps">
          <h3>Additional steps</h3>
          <p className="muted">
            Only what raft cannot do automatically (secrets, host paths, DNS/TLS).
          </p>
          <ul>
            {job.next_steps.map((step) => (
              <li key={step.title}>
                <strong>{step.title}</strong>
                <p>{step.body}</p>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
