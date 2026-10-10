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
  filterGithubRepos,
  logoutGithubAccount,
  needsOauthSetup,
  oauthErrorFromSearch,
  selectGithubAccount,
  startGithubDeploy,
  usableAccounts,
  type DeployJob,
  type GithubOauthConfig,
  type GithubRepo,
  type GithubSession,
} from "./github/githubApi";
import "./DeployPage.css";
import "./AddServicePage.css";

const POLL_MS = 1000;

/** GitHub OAuth → pick account → pick repo → auto-deploy + CI PR + logs. */
export function DeployPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const oauthError = oauthErrorFromSearch(location.search);
  const [session, setSession] = useState<GithubSession | null>(null);
  const [config, setConfig] = useState<GithubOauthConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [allRepos, setAllRepos] = useState<GithubRepo[]>([]);
  const [selected, setSelected] = useState<GithubRepo | null>(null);
  const [ref, setRef] = useState("main");
  const [job, setJob] = useState<DeployJob | null>(null);
  const [busy, setBusy] = useState(false);
  const [viewAsId, setViewAsId] = useState("");
  const redirecting = useRef(false);
  const needsSetup = needsOauthSetup(session, oauthError);
  const browseAccounts = usableAccounts(session);
  const browseIdsKey = browseAccounts.map((a) => a.id).join(",");

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
    setAllRepos([]);
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
    const ids = new Set(browseIdsKey ? browseIdsKey.split(",") : []);
    if (viewAsId && !ids.has(viewAsId)) {
      setViewAsId("");
      clearRepoSelection();
    }
  }, [browseIdsKey, viewAsId, clearRepoSelection]);

  useEffect(() => {
    if (!viewAsId || !session?.authenticated) {
      setAllRepos([]);
      return;
    }
    if (session.active_account_id !== viewAsId) {
      setAllRepos([]);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const list = await fetchGithubRepos();
        if (!cancelled) setAllRepos(list);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to list repos");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [session?.authenticated, session?.active_account_id, viewAsId]);

  const repos = filterGithubRepos(allRepos, query);

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

  const onLogoutOne = async (accountId: string) => {
    setBusy(true);
    try {
      const next = await logoutGithubAccount(accountId);
      setSession(next);
      if (viewAsId === accountId) {
        setViewAsId("");
      }
      clearRepoSelection();
      redirecting.current = false;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Logout failed");
    } finally {
      setBusy(false);
    }
  };

  const onViewAs = async (accountId: string) => {
    clearRepoSelection();
    setViewAsId(accountId);
    if (!accountId) return;
    setBusy(true);
    setError(null);
    try {
      setSession(await selectGithubAccount(accountId));
    } catch (err) {
      setViewAsId("");
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
    accountCount(session) > 0 && !oauthError && !needsSetup,
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
        onLogoutOne={(id) => void onLogoutOne(id)}
        onBusy={setBusy}
        onSaved={() => void onOauthSaved()}
        onError={(message) => setError(message || null)}
      />

      {showRepos ? (
        <>
          <DeployRepoPicker
            accounts={browseAccounts}
            accountId={viewAsId}
            onAccount={(id) => void onViewAs(id)}
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
