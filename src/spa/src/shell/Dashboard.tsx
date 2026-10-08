import { useCallback, useEffect, useRef, useState } from "react";
import {
  documentTitleForHost,
  STATUS_POLL_MS,
  type StatusPayload,
  type StatusRow,
} from "../shared/api";
import { peekStatus, refreshStatus } from "../shared/dashboardCache";
import { LiveIndicator } from "../chrome/LiveIndicator";
import { ThemeToggle } from "../chrome/ThemeToggle";
import { StatusTable } from "../status/StatusTable";
import { TrendsPanel } from "../trends/panel/TrendsPanel";

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
          <a className="refresh" href="/deploy" id="nav-deploy">
            Deploy from GitHub
          </a>
          <ThemeToggle />
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

      {data ? (
        <>
          <Section
            title="Control plane"
            rows={data.control_plane}
            empty="No control-plane services."
            storageKey="raft-serve-status-control-plane"
            isLive={statusLive}
            onActionDone={() => void load({ quiet: true })}
          />
          <Section
            title="Apps"
            rows={data.apps}
            empty="No applied apps."
            storageKey="raft-serve-status-apps"
            isLive={statusLive}
            onActionDone={() => void load({ quiet: true })}
          />
        </>
      ) : null}

      <TrendsPanel />
    </div>
  );
}

function Section(props: {
  title: string;
  rows: StatusRow[];
  empty: string;
  storageKey: string;
  isLive: boolean;
  onActionDone: () => void;
}) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{props.title}</h2>
        <LiveIndicator
          isLive={props.isLive}
          label={props.isLive ? undefined : "Paused · tab hidden"}
        />
      </div>
      <StatusTable
        rows={props.rows}
        empty={props.empty}
        storageKey={props.storageKey}
        onActionDone={props.onActionDone}
      />
    </section>
  );
}

/** Interval poll while visible; refetch once when the tab becomes visible again. */
function bindStatusPolling(
  onTick: () => void,
  onLiveChange: (live: boolean) => void,
): () => void {
  let timer: number | undefined;

  const clear = () => {
    if (timer !== undefined) {
      window.clearInterval(timer);
      timer = undefined;
    }
  };

  const arm = () => {
    clear();
    if (!tabIsVisible()) {
      onLiveChange(false);
      return;
    }
    timer = window.setInterval(onTick, STATUS_POLL_MS);
    onLiveChange(true);
  };

  const onVisibility = () => {
    if (tabIsVisible()) {
      onTick();
      arm();
      return;
    }
    clear();
    onLiveChange(false);
  };

  arm();
  document.addEventListener("visibilitychange", onVisibility);
  return () => {
    clear();
    document.removeEventListener("visibilitychange", onVisibility);
  };
}

function tabIsVisible(): boolean {
  return document.visibilityState === "visible";
}

function statusMetaLabel(opts: {
  updating: boolean;
  fetchedAt: number | null;
  now: number;
}): string | null {
  if (opts.updating) return "Updating…";
  if (opts.fetchedAt === null) return null;
  return formatUpdatedAgo(opts.fetchedAt, opts.now);
}

function formatUpdatedAgo(fetchedAt: number, now: number): string {
  const sec = Math.max(0, Math.floor((now - fetchedAt) / 1000));
  if (sec < 5) return "Updated just now";
  if (sec < 60) return `Updated ${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `Updated ${min}m ago`;
  return `Updated ${Math.floor(min / 60)}h ago`;
}
