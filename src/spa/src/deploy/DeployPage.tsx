import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { DeployProgress } from "./DeployProgress";
import { DeployRepoPicker } from "./DeployRepoPicker";
import { DeploySession } from "./DeploySession";
import {
  accountCount,
  fetchDeployJob,
  fetchGithubConfig,
  fetchGithubRepos,
  fetchGithubSession,
  logoutGithub,
  logoutGithubAccount,
  needsOauthSetup,
  oauthErrorFromSearch,
  selectGithubAccount,
  startGithubDeploy,
  type DeployJob,
  type GithubOauthConfig,
  type GithubRepo,
  type GithubSession,
} from "./githubApi";
import "./DeployPage.css";
import "./AddServicePage.css";

const POLL_MS = 1000;

/** GitHub OAuth → pick one repo → auto-deploy + CI PR + logs. */
export function DeployPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const oauthError = oauthErrorFromSearch(location.search);
  const [session, setSession] = useState<GithubSession | null>(null);
  const [config, setConfig] = useState<GithubOauthConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [repos, setRepos] = useState<GithubRepo[]>([]);
  const [selected, setSelected] = useState<GithubRepo | null>(null);
  const [ref, setRef] = useState("main");
  const [job, setJob] = useState<DeployJob | null>(null);
  const [busy, setBusy] = useState(false);
  const redirecting = useRef(false);
  const needsSetup = needsOauthSetup(session, oauthError);
  const activeId = session?.active_account_id ?? null;

  const refreshSession = useCallback(async () => {
    setError(null);
    try {
      const [nextSession, nextConfig] = await Promise.all([
        fetchGithubSession(),
        fetchGithubConfig(),
      ]);
      setSession(nextSession);
      setConfig(nextConfig);
    } catch {
      setError("Failed to load GitHub session.");
    }
  }, []);

  const clearRepoSelection = useCallback(() => {
    setSelected(null);
    setJob(null);
    setRepos([]);
    setQuery("");
  }, []);

  useEffect(() => {
    void refreshSession();
  }, [refreshSession]);

  useEffect(() => {
    // Auto-login only when zero connected accounts (not when expired rows exist).
    if (
      oauthError ||
      needsSetup ||
      !session ||
      accountCount(session) > 0 ||
      redirecting.current
    ) {
      return;
    }
    redirecting.current = true;
    window.location.assign("/api/github/login");
  }, [session, oauthError, needsSetup]);

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
  }, [session?.authenticated, activeId, query]);

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
      setSession(await logoutGithub());
      clearRepoSelection();
      redirecting.current = false;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Logout failed");
    } finally {
      setBusy(false);
    }
  };

  const onLogoutOne = async (accountId: string) => {
    setBusy(true);
    try {
      setSession(await logoutGithubAccount(accountId));
      clearRepoSelection();
      redirecting.current = false;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Logout failed");
    } finally {
      setBusy(false);
    }
  };

  const onSelectAccount = async (accountId: string) => {
    setBusy(true);
    setError(null);
    try {
      clearRepoSelection();
      setSession(await selectGithubAccount(accountId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Select account failed");
    } finally {
      setBusy(false);
    }
  };

  const onOauthSaved = async () => {
    redirecting.current = false;
    navigate("/deploy", { replace: true });
    await refreshSession();
    window.location.assign("/api/github/login");
  };

  const showRepos = Boolean(
    session?.authenticated && !oauthError && !needsSetup,
  );

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
        config={config}
        oauthError={oauthError}
        needsSetup={needsSetup}
        busy={busy}
        onLogout={() => void onLogout()}
        onLogoutOne={(id) => void onLogoutOne(id)}
        onSelectAccount={(id) => void onSelectAccount(id)}
        onBusy={setBusy}
        onSaved={() => void onOauthSaved()}
        onError={(message) => setError(message || null)}
      />

      {showRepos ? (
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
