import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  DASHBOARD_DOCUMENT_TITLE,
  type StatusPayload,
} from "../shared/api/index.ts";
import { peekStatus, refreshStatus } from "../shared/dashboardCache";
import { LiveIndicator } from "../shared/chrome/LiveIndicator";
import { showSkeleton, StackStatusSkeleton } from "../shared/chrome/skeleton";
import { EmptyState, ErrorState } from "../shared/chrome/StateViews";
import { DashboardSection } from "./DashboardSection";
import { DeferredTrends } from "./DeferredTrends";
import { PageHeader } from "./PageHeader";
import { RegistryIssues } from "./RegistryIssues";
import { StatusMetaLabel } from "./StatusMetaLabel";
import { StatusSummary } from "./StatusSummary";
import { bindStatusPolling, tabIsVisible } from "./statusPolling";

/** Main dashboard: cached paint, quiet poll while visible, then background refresh. */
export function Dashboard() {
  const [data, setData] = useState<StatusPayload | null>(() => peekStatus());
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(() => peekStatus() === null);
  const [updating, setUpdating] = useState(false);
  const [fetchedAt, setFetchedAt] = useState<number | null>(null);
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
        setError("Failed to load status. Refresh and try again.");
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
    document.title = DASHBOARD_DOCUMENT_TITLE;
  }, []);

  const quietReload = useCallback(() => void load({ quiet: true }), [load]);
  const summaryRows = useMemo(
    () => (data ? [...data.control_plane, ...data.apps] : []),
    [data],
  );

  return (
    <>
      <PageHeader
        title="Stack status"
        meta={
          <>
            <LiveIndicator
              isLive={statusLive}
              label={statusLive ? "Live" : "Paused · tab hidden"}
            />
            <StatusMetaLabel updating={updating} fetchedAt={fetchedAt} />
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

      {showSkeleton(busy, data !== null) ? (
        <StackStatusSkeleton label="Loading status…" id="status-loading" />
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
          <StatusSummary rows={summaryRows} />
          <DashboardSection
            title="Apps"
            id="status-apps"
            rows={data.apps}
            empty={APPS_EMPTY}
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

      <DeferredTrends hasStatusData={data !== null} />
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
      Deploy one from GitHub, or ask an admin to add a service.
    </EmptyState>
  );
}

/** Module-level so memoized ``DashboardSection`` keeps equal props across renders. */
const APPS_EMPTY = <AppsEmpty />;
