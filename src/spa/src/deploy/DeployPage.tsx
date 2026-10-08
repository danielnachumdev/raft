import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { DeployProgress } from "./DeployProgress";
import { DeployRepoPicker } from "./DeployRepoPicker";
import { DeploySession } from "./DeploySession";
import {
  fetchDeployJob,
  fetchGithubRepos,
  fetchGithubSession,
  logoutGithub,
  oauthErrorFromSearch,
  startGithubDeploy,
  type DeployJob,
  type GithubRepo,
  type GithubSession,
} from "./githubApi";
import "./DeployPage.css";
import "./AddServicePage.css";

const POLL_MS = 1000;

/** GitHub OAuth → pick one repo → auto-deploy + CI PR + logs. */
export function DeployPage() {
  const location = useLocation();
  const oauthError = oauthErrorFromSearch(location.search);
  const [session, setSession] = useState<GithubSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [repos, setRepos] = useState<GithubRepo[]>([]);
  const [selected, setSelected] = useState<GithubRepo | null>(null);
  const [ref, setRef] = useState("main");
  const [job, setJob] = useState<DeployJob | null>(null);
  const [busy, setBusy] = useState(false);
  const redirecting = useRef(false);

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
    if (oauthError || !session || session.authenticated || redirecting.current) {
      return;
    }
    redirecting.current = true;
    window.location.assign("/api/github/login");
  }, [session, oauthError]);

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
      redirecting.current = false;
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
          <h1>Add from GitHub</h1>
          <p className="muted header-updating">
            Temporary login for repo selection, deploy, and CI setup. Serve stays
            localhost / SSH tunnel.
          </p>
        </div>
        <div className="header-actions">
          <Link className="refresh" to="/add-service">
            Add new service
          </Link>
          <Link className="refresh" to="/">
            Stack status
          </Link>
        </div>
      </header>

      {error ? (
        <p className="error" role="alert" id="deploy-error">
          {error}
        </p>
      ) : null}

      <DeploySession
        session={session}
        oauthError={oauthError}
        busy={busy}
        onLogout={() => void onLogout()}
      />

      {session?.authenticated && !oauthError ? (
        <>
          <DeployRepoPicker
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
