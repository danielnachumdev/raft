import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { PageHeader } from "../../app/PageHeader";
import { toast } from "../../shared/chrome/toast";
import { userFacingError } from "../../shared/userFacingError.ts";
import { DeployProgress } from "./DeployProgress";
import { DeployRepoPicker } from "./DeployRepoPicker";
import { DeploySession } from "./DeploySession";
import { DeploySteps } from "./DeploySteps";
import {
  clearPersistedDeployJob,
  isDeployInFlight,
  persistDeployJob,
  readPersistedDeployJobId,
} from "./model/jobPersistence";
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
  DEFAULT_MANIFEST_PATH,
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
  const [manifestPath, setManifestPath] = useState(DEFAULT_MANIFEST_PATH);
  const [job, setJob] = useState<DeployJob | null>(null);
  const [busy, setBusy] = useState(false);
  const [viewAsId, setViewAsId] = useState("");
  const prevJobStatus = useRef<string | null>(null);
  const needsSetup = needsOauthSetup(session, oauthError);
  const browseAccounts = usableAccounts(session);
  const browseIdsKey = browseAccounts.map((a) => a.id).join(",");
  const installing = isDeployInFlight(job);
  const controlsBusy = busy || installing;

  const refreshSession = useCallback(async (opts?: { refresh?: boolean }) => {
    setError(null);
    try {
      const [nextSession, nextConfig] = await Promise.all([
        fetchGithubSession({ refresh: opts?.refresh ?? true }),
        fetchGithubConfig(),
      ]);
      const usable = usableAccounts(nextSession);
      const activeId = nextSession.active_account_id || "";
      const activeOk = usable.some((account) => account.id === activeId);
      if (usable.length > 0 && !activeOk) {
        const picked = await selectGithubAccount(usable[0].id);
        setSession(picked);
        setViewAsId(usable[0].id);
      } else {
        setSession(nextSession);
        if (activeOk) {
          setViewAsId(activeId);
        }
      }
      setConfig(nextConfig);
    } catch {
      setError("Failed to load GitHub session.");
    }
  }, []);

  const clearRepoSelection = useCallback(() => {
    setSelected(null);
    setJob(null);
    clearPersistedDeployJob();
    prevJobStatus.current = null;
    setAllRepos([]);
    setQuery("");
    setManifestPath(DEFAULT_MANIFEST_PATH);
  }, []);

  useEffect(() => {
    void refreshSession({ refresh: true });
  }, [refreshSession]);

  useEffect(() => {
    const id = readPersistedDeployJobId();
    if (!id) return;
    let cancelled = false;
    void (async () => {
      try {
        const restored = await fetchDeployJob(id);
        if (cancelled) return;
        setJob(restored);
        persistDeployJob(restored);
        if (isDeployInFlight(restored)) {
          toast.regular({
            message: `Resuming installation for ${restored.full_name}…`,
            href: "/deploy",
            linkLabel: "View progress",
          });
        }
      } catch {
        if (!cancelled) clearPersistedDeployJob();
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!job) {
      prevJobStatus.current = null;
      return;
    }
    persistDeployJob(job);
    const prev = prevJobStatus.current;
    prevJobStatus.current = job.status;
    if (prev !== "pending" && prev !== "running") return;
    if (job.status === "succeeded") {
      toast.good({
        message: job.app_name
          ? `Installed ${job.app_name}.`
          : `Installed ${job.full_name}.`,
        href: job.app_name ? `/service/${encodeURIComponent(job.app_name)}` : "/deploy",
        linkLabel: job.app_name ? "View service" : "View progress",
      });
      return;
    }
    if (job.status === "failed") {
      toast.bad({
        message: `Installation needs attention for ${job.full_name}.`,
        href: "/deploy",
        linkLabel: "View details",
      });
    }
  }, [job]);

  useEffect(() => {
    const ids = new Set(browseIdsKey ? browseIdsKey.split(",") : []);
    if (viewAsId && !ids.has(viewAsId)) {
      setViewAsId("");
      clearRepoSelection();
    }
  }, [browseIdsKey, viewAsId, clearRepoSelection]);

  useEffect(() => {
    const activeId = session?.active_account_id || "";
    const usableIds = new Set(browseIdsKey ? browseIdsKey.split(",") : []);
    if (!viewAsId || !usableIds.has(activeId) || activeId !== viewAsId) {
      setAllRepos([]);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const list = await fetchGithubRepos({ refresh: true });
        if (!cancelled) setAllRepos(list);
      } catch (err) {
        if (!cancelled) {
          setError(userFacingError(err, "Failed to list repos"));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [browseIdsKey, session?.active_account_id, viewAsId]);

  const repos = filterGithubRepos(allRepos, query);

  useEffect(() => {
    if (!job || job.status === "succeeded" || job.status === "failed") return;
    const id = window.setInterval(() => {
      void fetchDeployJob(job.id)
        .then(setJob)
        .catch((err) =>
          setError(userFacingError(err, "Deploy poll failed")),
        );
    }, POLL_MS);
    return () => window.clearInterval(id);
  }, [job]);

  const onSelect = (repo: GithubRepo) => {
    setSelected(repo);
    setRef(repo.default_branch || "main");
    setJob(null);
    clearPersistedDeployJob();
    prevJobStatus.current = null;
  };

  const onDeploy = async () => {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const next = await startGithubDeploy(
        selected.full_name,
        ref,
        manifestPath,
      );
      prevJobStatus.current = next.status;
      setJob(next);
      persistDeployJob(next);
      toast.regular({
        message: `Installing ${next.full_name}… You can leave this page.`,
        href: "/deploy",
        linkLabel: "Open progress",
        durationMs: 6500,
      });
    } catch (err) {
      setError(userFacingError(err, "Deploy failed to start"));
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
      setError(userFacingError(err, "Delete failed"));
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
      setError(userFacingError(err, "Select account failed"));
    } finally {
      setBusy(false);
    }
  };

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
        busy={controlsBusy}
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
            manifestPath={manifestPath}
            onManifestPath={setManifestPath}
            busy={controlsBusy}
            onDeploy={() => void onDeploy()}
          />
          {job ? (
            <DeployProgress
              job={job}
              busy={controlsBusy}
              onContinue={() => void onDeploy()}
            />
          ) : null}
        </>
      ) : null}
    </div>
  );
}
