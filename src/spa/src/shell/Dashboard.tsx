import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  documentTitleForHost,
  type StatusPayload,
} from "../shared/api/index.ts";
import { peekStatus, refreshStatus } from "../shared/dashboardCache";
import { LiveIndicator } from "../chrome/LiveIndicator";
import { EmptyState, ErrorState, LoadingState } from "../chrome/StateViews";
import { TrendsDashboard } from "../trends/dashboard/ui/TrendsDashboard";
import { DashboardSection } from "./DashboardSection";
import { PageHeader } from "./PageHeader";
import { RegistryIssues } from "./RegistryIssues";
import { StatusSummary } from "./StatusSummary";
import { statusMetaLabel } from "./statusMeta";
import { bindStatusPolling, tabIsVisible } from "./statusPolling";

/** Main dashboard: cached paint, quiet poll while visible, then background refresh. */
export function Dashboard() {
  const [data, setData] = useState<StatusPayload | null>(() => peekStatus());
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(() => peekStatus() === null);
  const [updating, setUpdating] = useState(false);
  const [fetchedAt, setFetchedAt] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [statusLive, setStatusLive] = useState(() => tabIsVisible());
  const dataRef = useRef<StatusPayload | null>(null);
  const inFlightRef = useRef(false);

  useEffect(() => {
    dataRef.current = data;
  }, [data]);

  const load = useCallback(async (opts?: { quiet?: boolean }) => {
    const quiet = opts?.quiet === true;
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    if (quiet) {
      setUpdating(true);
    } else {
      setBusy(true);
      setError(null);
    }
    try {
      setData(await refreshStatus());
      setFetchedAt(Date.now());
      if (quiet) setError(null);
    } catch {
      if (!quiet || dataRef.current === null) {
        setError("Failed to load status. Refresh or check raft serve.");
      }
    } finally {
      inFlightRef.current = false;
      setBusy(false);
      setUpdating(false);
    }
  }, []);

  useEffect(() => {
    void load({ quiet: peekStatus() !== null });
  }, [load]);

  useEffect(() => {
    return bindStatusPolling(() => void load({ quiet: true }), setStatusLive);
  }, [load]);

  useEffect(() => {
    if (fetchedAt === null) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [fetchedAt]);

  useEffect(() => {
    document.title = documentTitleForHost(data?.host?.hostname);
  }, [data]);

  const metaLabel = statusMetaLabel({ updating, fetchedAt, now });
  const hostname = data?.host?.hostname;
  const quietReload = () => void load({ quiet: true });

  return (
    <>
      <PageHeader
        title="Stack status"
        subtitle={
          typeof hostname === "string" && hostname ? (
            <>
              Host <code>{hostname}</code>
            </>
          ) : undefined
        }
        meta={
          <>
            <LiveIndicator
              isLive={statusLive}
              label={statusLive ? "Live" : "Paused · tab hidden"}
            />
            {metaLabel ? (
              <span className="muted" aria-live="polite">
                {metaLabel}
              </span>
            ) : null}
          </>
        }
        actions={
          <>
            <button
              type="button"
              className={busy ? "btn is-loading" : "btn"}
              onClick={() => void load()}
              disabled={busy || updating}
              aria-busy={busy || updating}
              aria-label="Refresh status"
              id="status-refresh"
            >
              {busy ? (
                <span className="spinner btn-spinner" aria-hidden="true" />
              ) : null}
              Refresh
            </button>
          </>
        }
      />

      {busy && data === null ? (
        <LoadingState label="Loading status…" id="status-loading" />
      ) : null}

      {error ? (
        <ErrorState
          message={error}
          id="status-error"
          onRetry={() => void load()}
        />
      ) : null}

      <RegistryIssues issues={data?.registry_issues ?? []} />

      {data ? (
        <>
          <StatusSummary rows={[...data.control_plane, ...data.apps]} />
          <DashboardSection
            title="Apps"
            id="status-apps"
            rows={data.apps}
            empty={<AppsEmpty />}
            storageKey="raft-serve-status-apps"
            onActionDone={quietReload}
          />
          <DashboardSection
            title="Control plane"
            id="status-control-plane"
            rows={data.control_plane}
            empty="No control-plane services."
            storageKey="raft-serve-status-control-plane"
            onActionDone={quietReload}
          />
        </>
      ) : null}

      <TrendsDashboard />
    </>
  );
}

function AppsEmpty() {
  return (
    <EmptyState
      id="apps-empty"
      title="No apps applied yet."
      action={
        <Link className="btn btn-primary" to="/add-service">
          Add your first service
        </Link>
      }
    >
      Deploy one from GitHub here, or from a service repo run{" "}
      <code>raft apply --file .raft/app.yaml</code>.
    </EmptyState>
  );
}
