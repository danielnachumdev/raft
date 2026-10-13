import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  documentTitleForHost,
  type StatusPayload,
} from "../shared/api/index.ts";
import { peekStatus, refreshStatus } from "../shared/dashboardCache";
import { ThemeToggle } from "../chrome/ThemeToggle";
import { TrendsPanel } from "../trends/panel/TrendsPanel";
import { DashboardSection } from "./DashboardSection";
import { PurgeButton } from "./PurgeButton";
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

  return (
    <div className="page">
      <header className="header">
        <div>
          <p className="brand">raft</p>
          <h1>Stack status</h1>
          {metaLabel ? (
            <p className="muted header-updating" aria-live="polite">
              {metaLabel}
            </p>
          ) : null}
        </div>
        <div className="header-actions">
          <ThemeToggle />
          <Link
            className="refresh"
            to="/settings/edge-access"
            id="nav-edge-access"
          >
            Firewall
          </Link>
          <Link
            className="refresh"
            to="/settings/notifications"
            id="nav-notifications"
          >
            Notifications
          </Link>
          <PurgeButton />
          <button
            type="button"
            className={busy ? "refresh is-loading" : "refresh"}
            onClick={() => void load()}
            disabled={busy || updating}
            aria-busy={busy || updating}
            aria-label="Refresh status"
            id="status-refresh"
          >
            {busy ? (
              <span className="spinner refresh-spinner" aria-hidden="true" />
            ) : null}
            Refresh
          </button>
        </div>
      </header>

      {busy && data === null ? (
        <div
          className="loading"
          role="status"
          aria-busy="true"
          id="status-loading"
        >
          <span className="spinner" aria-hidden="true" />
          <p>Loading status…</p>
        </div>
      ) : null}

      {error ? (
        <p className="error" role="alert" id="status-error">
          {error}
        </p>
      ) : null}

      {data?.registry_issues && data.registry_issues.length > 0 ? (
        <section className="panel registry-issues" id="registry-issues">
          <div className="panel-head">
            <h2>Invalid App manifests</h2>
          </div>
          <p className="muted">
            These files under <code>state/apps/</code> were skipped so other
            services keep working. Fix or remove them, then refresh. Apply/deploy
            still rejects bad YAML with a clear error.
          </p>
          <ul className="registry-issue-list">
            {data.registry_issues.map((issue) => (
              <li key={issue.file}>
                <code>{issue.file}</code>
                <p className="error" role="alert">
                  {issue.error}
                </p>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {data ? (
        <>
          <DashboardSection
            title="Control plane"
            rows={data.control_plane}
            empty="No control-plane services."
            storageKey="raft-serve-status-control-plane"
            isLive={statusLive}
            onActionDone={() => void load({ quiet: true })}
          />
          <DashboardSection
            title="Apps"
            rows={data.apps}
            empty="No applied apps."
            storageKey="raft-serve-status-apps"
            isLive={statusLive}
            onActionDone={() => void load({ quiet: true })}
            addHref="/add-service"
          />
        </>
      ) : null}

      <TrendsPanel />
    </div>
  );
}
