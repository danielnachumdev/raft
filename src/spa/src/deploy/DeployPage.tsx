import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { PageHeader } from "../shell/PageHeader";
import { DeployProgress } from "./DeployProgress";
import { DeployRepoPicker } from "./DeployRepoPicker";
import { DeploySession } from "./DeploySession";
import { DeploySteps } from "./DeploySteps";
import { currentStep } from "./model/wizardSteps";
import {
  accountCount,
  deleteGithubAccount,
  fetchDeployJob,
  fetchGithubConfig,
  fetchGithubRepos,
  fetchGithubSession,
  filterGithubRepos,
  forceOauthInstructions,
  githubLoginHref,
  needsOauthSetup,
  oauthErrorFromSearch,
  selectGithubAccount,
  startGithubDeploy,
  usableAccounts,
  type DeployJob,
  type GithubOauthConfig,
  type GithubRepo,
  type GithubSession,
} from "./github/index.ts";
import "./DeployPage.css";
import "./AddServicePage.css";

const POLL_MS = 1000;

/** GitHub OAuth → pick account → pick repo → auto-deploy + CI PR + logs. */
export function DeployPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const oauthError = oauthErrorFromSearch(location.search);
  const showInstructions = forceOauthInstructions(location.search);
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

  const onDeleteOne = async (accountId: string) => {
    setBusy(true);
    try {
      const next = await deleteGithubAccount(accountId);
      setSession(next);
      if (viewAsId === accountId) {
        setViewAsId("");
      }
      clearRepoSelection();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
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

  const autoPickedRef = useRef("");
  useEffect(() => {
    const ids = browseIdsKey ? browseIdsKey.split(",") : [];
    if (viewAsId || ids.length !== 1 || autoPickedRef.current === ids[0]) return;
    autoPickedRef.current = ids[0];
    void onViewAs(ids[0]);
  });

  const onOauthSaved = async () => {
    navigate("/deploy", { replace: true });
    await refreshSession();
    window.location.assign(githubLoginHref());
  };

  const onContinueConfigured = () => {
    navigate("/deploy", { replace: true });
  };

  const showRepos = Boolean(
    accountCount(session) > 0 &&
      !oauthError &&
      !needsSetup &&
      !showInstructions,
  );

  return (
    <div className="deploy-page">
      <PageHeader
        crumbs={[
          { label: "Status", to: "/" },
          { label: "Add a service", to: "/add-service" },
        ]}
        title="Add from GitHub"
        subtitle="Connect GitHub, pick a repository, and raft deploys it and opens a CI PR."
      />

      <DeploySteps current={currentStep(accountCount(session) > 0, selected, job)} />

      {error ? (
        <p className="callout callout-bad error" role="alert" id="deploy-error">
          {error}
        </p>
      ) : null}

      <DeploySession
        session={session}
        config={config}
        oauthError={oauthError}
        needsSetup={needsSetup}
        forceInstructions={showInstructions}
        busy={busy}
        onDeleteOne={(id) => void onDeleteOne(id)}
        onBusy={setBusy}
        onSaved={() => void onOauthSaved()}
        onContinueConfigured={onContinueConfigured}
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
