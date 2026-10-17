import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "../shell/PageHeader";
import {
  fetchOpsEvents,
  type OpsEventRow,
  type OpsEventsPayload,
} from "./eventsApi";
import "./EventsPage.css";

const HOUR_OPTIONS = [1, 6, 24, 72, 168] as const;

/** Read-only chronological timeline over ``state/events/ops.jsonl``. */
export function EventsPage() {
  const [hours, setHours] = useState(24);
  const [kind, setKind] = useState("");
  const [service, setService] = useState("");
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [payload, setPayload] = useState<OpsEventsPayload | null>(null);

  const load = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const next = await fetchOpsEvents({
        hours,
        kind: kind.trim() || undefined,
        service: service.trim() || undefined,
      });
      setPayload(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load events");
      setPayload(null);
    } finally {
      setBusy(false);
    }
  }, [hours, kind, service]);

  useEffect(() => {
    void load();
  }, [load]);

  const events = payload?.events ?? [];

  return (
    <div className="events-page">
      <PageHeader
        title="Events"
        subtitle="Host activity from apply, scale, purge, firewall, and alerts."
        actions={
          <button
            type="button"
            className="refresh"
            id="events-refresh"
            onClick={() => void load()}
            disabled={busy}
          >
            Refresh
          </button>
        }
      />
      <form
        className="events-filters"
        id="events-filters"
        onSubmit={(e) => {
          e.preventDefault();
          void load();
        }}
      >
        <label>
          Hours
          <select
            id="events-hours"
            value={hours}
            onChange={(e) => setHours(Number(e.target.value))}
          >
            {HOUR_OPTIONS.map((h) => (
              <option key={h} value={h}>
                {h === 168 ? "7 days" : `${h}h`}
              </option>
            ))}
          </select>
        </label>
        <label>
          Kind
          <input
            id="events-kind"
            type="text"
            placeholder="deploy.apply"
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            list="events-kind-suggestions"
          />
          <datalist id="events-kind-suggestions">
            <option value="deploy.apply" />
            <option value="deploy.redeploy" />
            <option value="scale.wake" />
            <option value="scale.idle_stop" />
            <option value="stack.purge" />
            <option value="firewall.apply" />
            <option value="gate.reload" />
            <option value="alert.fired" />
            <option value="alert.resolved" />
          </datalist>
        </label>
        <label>
          Service
          <input
            id="events-service"
            type="text"
            placeholder="demo-api"
            value={service}
            onChange={(e) => setService(e.target.value)}
          />
        </label>
        <button type="submit" className="btn-primary" id="events-apply-filters">
          Apply
        </button>
      </form>
      {error ? (
        <p className="error" id="events-error" role="alert">
          {error}
        </p>
      ) : null}
      {busy && !payload ? <p className="muted">Loading…</p> : null}
      {!busy && !error && events.length === 0 ? (
        <p className="muted" id="events-empty">
          No events in this window.
        </p>
      ) : null}
      {events.length > 0 ? (
        <ol className="events-timeline" id="events-timeline">
          {events.map((row) => (
            <EventRow key={row.id ?? `${row.ts}-${row.kind}`} row={row} />
          ))}
        </ol>
      ) : null}
    </div>
  );
}

function EventRow({ row }: { row: OpsEventRow }) {
  return (
    <li className="events-row">
      <time className="events-ts" dateTime={row.ts}>
        {formatTs(row.ts)}
      </time>
      <span className="events-kind">{row.kind}</span>
      <span className="events-service muted">{row.service || "—"}</span>
      <span className="events-summary">{row.summary}</span>
    </li>
  );
}

function formatTs(value: string): string {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}
