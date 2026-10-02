import { useCallback, useEffect, useState } from "react";
import {
  documentTitleForHost,
  type StatusPayload,
  type StatusRow,
} from "./api";
import { peekStatus, refreshStatus } from "./dashboardCache";
import { StatusTable } from "./StatusTable";
import { TrendsPanel } from "./TrendsPanel";

/** Main dashboard: status tables + trends (cached paint, then background refresh). */
export function Dashboard() {
  const [data, setData] = useState<StatusPayload | null>(() => peekStatus());
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(() => peekStatus() === null);

  const load = useCallback(async (opts?: { quiet?: boolean }) => {
    const quiet = opts?.quiet === true;
    setBusy(true);
    setError(null);
    try {
      setData(await refreshStatus());
    } catch {
      if (!quiet || peekStatus() === null) {
        setError("Failed to load status. Refresh or check raft serve.");
      }
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void load({ quiet: peekStatus() !== null });
  }, [load]);

  useEffect(() => {
    document.title = documentTitleForHost(data?.host?.hostname);
  }, [data]);

  const updating = busy && data !== null;

  return (
    <div className="page">
      <header className="header">
        <div>
          <p className="brand">raft</p>
          <h1>Stack status</h1>
          {updating ? (
            <p className="muted header-updating" aria-live="polite">
              Updating…
            </p>
          ) : null}
        </div>
        <button
          type="button"
          className={busy ? "refresh is-loading" : "refresh"}
          onClick={() => void load()}
          disabled={busy}
          aria-busy={busy}
          aria-label="Refresh status"
          id="status-refresh"
        >
          {busy ? (
            <span className="spinner refresh-spinner" aria-hidden="true" />
          ) : null}
          Refresh
        </button>
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
            onActionDone={() => void load()}
          />
          <Section
            title="Apps"
            rows={data.apps}
            empty="No applied apps."
            onActionDone={() => void load()}
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
  onActionDone: () => void;
}) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{props.title}</h2>
        <p className="muted panel-kind">Live · current snapshot</p>
      </div>
      <StatusTable
        rows={props.rows}
        empty={props.empty}
        onActionDone={props.onActionDone}
      />
    </section>
  );
}
