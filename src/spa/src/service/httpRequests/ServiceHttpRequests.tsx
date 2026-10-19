import { useCallback, useEffect, useState } from "react";
import {
  DEFAULT_HTTP_REQUESTS_LIMIT,
  HTTP_REQUESTS_POLL_MS,
  fetchServiceHttpRequests,
  type HttpRequestsPayload,
} from "../../shared/api";
import { HttpRequestsTable } from "./HttpRequestsTable";
import "./ServiceHttpRequests.css";

const LIMIT_CHOICES = [50, 100, 200] as const;

/** Recent per-request HTTP rows for Host-routed Apps (not Trends aggregates). */
export function ServiceHttpRequests(props: {
  service: string;
  /** App name for firewall service prefill (Host-routed). */
  appName?: string | null;
  containerStatus: string;
  onEligibleChange?: (eligible: boolean) => void;
}) {
  const { onEligibleChange } = props;
  const [limit, setLimit] = useState<number>(DEFAULT_HTTP_REQUESTS_LIMIT);
  const [live, setLive] = useState(true);
  const [data, setData] = useState<HttpRequestsPayload | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const payload = await fetchServiceHttpRequests(props.service, limit);
      setData(payload);
      setError(null);
    } catch {
      setError("Failed to load HTTP requests.");
    } finally {
      setBusy(false);
    }
  }, [props.service, limit]);

  useEffect(() => {
    setBusy(true);
    void load();
  }, [load]);

  useEffect(() => {
    if (data) onEligibleChange?.(data.eligible);
  }, [data, onEligibleChange]);

  useEffect(() => {
    if (!live || !data?.eligible) return;
    const id = window.setInterval(() => void load(), HTTP_REQUESTS_POLL_MS);
    return () => window.clearInterval(id);
  }, [live, data?.eligible, load]);

  if (!busy && data && !data.eligible) {
    return null;
  }

  return (
    <section className="panel http-requests" aria-labelledby="http-requests-title">
      <div className="http-requests-head">
        <h2 id="http-requests-title">HTTP requests</h2>
        <HttpRequestsControls
          live={live}
          onLiveChange={setLive}
          limit={limit}
          onLimitChange={setLimit}
          busy={busy}
          onRefresh={() => void load()}
        />
      </div>
      <p className="http-requests-note">
        Per-request edge traffic for this App’s Host(s). Trends HTTP stays
        aggregate (RPS / latency / status classes). Query strings are not logged.
        Drag column edges to resize; click a row to expand full Path / User-Agent.
      </p>
      {data?.scaled_to_zero ? (
        <p className="http-requests-hint" role="status">
          App is scaled to zero — new proxied traffic will wake it.
        </p>
      ) : null}
      {!data?.scaled_to_zero && isNotRunning(props.containerStatus) ? (
        <p className="http-requests-hint" role="status">
          App is not running — showing recent edge rows if any remain in the
          access log.
        </p>
      ) : null}
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      {busy && !data ? (
        <p className="http-requests-empty">Loading requests…</p>
      ) : null}
      {data && data.eligible ? (
        <HttpRequestsTable
          rows={data.requests}
          appName={props.appName ?? null}
        />
      ) : null}
    </section>
  );
}

function HttpRequestsControls(props: {
  live: boolean;
  onLiveChange: (v: boolean) => void;
  limit: number;
  onLimitChange: (v: number) => void;
  busy: boolean;
  onRefresh: () => void;
}) {
  return (
    <div className="http-requests-controls">
      <label className="check http-requests-live">
        <input
          type="checkbox"
          checked={props.live}
          onChange={(e) => props.onLiveChange(e.target.checked)}
        />
        Live
      </label>
      <label className="http-requests-limit">
        Limit
        <select
          value={props.limit}
          disabled={props.busy}
          onChange={(e) => props.onLimitChange(Number(e.target.value))}
        >
          {LIMIT_CHOICES.map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
      </label>
      <button type="button" className="btn btn-sm" onClick={props.onRefresh}>
        Refresh
      </button>
    </div>
  );
}

function isNotRunning(status: string): boolean {
  const key = status.trim().toLowerCase();
  return key === "not running" || key === "exited" || key === "dead";
}
