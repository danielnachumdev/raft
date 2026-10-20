import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { LiveIndicator } from "../chrome/LiveIndicator";
import type { StatusPayload } from "../shared/api/index.ts";
import { peekStatus, refreshStatus } from "../shared/dashboardCache";
import { PageHeader } from "../shell/PageHeader";
import { bindStatusPolling } from "../shell/statusPolling";
import { fetchOpsEvents, type OpsEventsPayload } from "./eventsApi";
import { EventsFilters } from "./EventsFilters";
import { DEFAULT_EVENTS_QUERY, type EventsQuery } from "./eventsView";
import { EventsTimeline } from "./EventsTimeline";
import "./EventsPage.css";

const EVENTS_POLL_MS = 15_000;

/** Chronological timeline over ``state/events/ops.jsonl``; quiet poll while visible. */
export function EventsPage() {
  const [query, setQuery] = useState<EventsQuery>(DEFAULT_EVENTS_QUERY);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [payload, setPayload] = useState<OpsEventsPayload | null>(null);
  const [live, setLive] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const services = useKnownServices();
  const queryRef = useRef(query);

  const load = useCallback(async (opts?: { quiet?: boolean }) => {
    if (!opts?.quiet) setBusy(true);
    try {
      const q = queryRef.current;
      setPayload(
        await fetchOpsEvents({
          hours: q.hours,
          kind: q.kind || undefined,
          service: q.service || undefined,
        }),
      );
      setError(null);
    } catch (err) {
      if (!opts?.quiet) setPayload(null);
      setError(err instanceof Error ? err.message : "Failed to load events");
    } finally {
      setNow(Date.now());
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void load({ quiet: true });
  }, [load]);

  useEffect(
    () => bindStatusPolling(() => void load({ quiet: true }), setLive, EVENTS_POLL_MS),
    [load],
  );

  const events = payload?.events ?? [];
  const applyQuery = (next: EventsQuery) => {
    queryRef.current = next;
    setQuery(next);
    void load();
  };

  return (
    <div className="events-page">
      <PageHeader
        title="Events"
        subtitle="Host activity from deploys, scaling, service actions, the firewall, and alerts."
        meta={<LiveIndicator isLive={live} label={live ? "Live" : "Paused · tab hidden"} />}
        actions={
          <button
            type="button"
            className={busy ? "btn is-loading" : "btn"}
            id="events-refresh"
            onClick={() => void load()}
            disabled={busy}
            aria-busy={busy}
          >
            {busy ? <span className="spinner btn-spinner" aria-hidden="true" /> : null}
            Refresh
          </button>
        }
      />
      <section className="panel" id="events-panel">
        <div className="panel-head">
          <h2>
            Timeline
            {payload ? <span className="panel-count">{events.length}</span> : null}
          </h2>
        </div>
        <EventsFilters query={query} services={services.names} onChange={applyQuery} />
        {error ? (
          <p className="callout callout-bad error" id="events-error" role="alert">
            {error}
          </p>
        ) : null}
        {busy && !payload ? (
          <div className="loading" role="status">
            <span className="spinner" aria-hidden="true" />
            <p>Loading events…</p>
          </div>
        ) : null}
        {payload && events.length === 0 ? <EventsEmpty filtered={query.kind !== "" || query.service !== ""} /> : null}
        {events.length > 0 ? (
          <EventsTimeline rows={events} now={now} knownServices={services.ids} />
        ) : null}
      </section>
    </div>
  );
}

function EventsEmpty(props: { filtered: boolean }) {
  return (
    <div className="empty-state" id="events-empty">
      <p>
        <strong>No events in this window.</strong>
      </p>
      <p className="muted">
        {props.filtered
          ? "Try a wider window or clear the filters."
          : "Deploys, scaling, service actions, firewall saves, and alerts appear here as they happen."}
      </p>
    </div>
  );
}

/** Compose ids known to /api/status (for links + service suggestions). */
function useKnownServices(): { ids: Set<string>; names: string[] } {
  const [status, setStatus] = useState<StatusPayload | null>(() => peekStatus());
  useEffect(() => {
    void refreshStatus()
      .then(setStatus)
      .catch(() => undefined);
  }, []);
  return useMemo(() => {
    const rows = status ? [...status.apps, ...status.control_plane] : [];
    const names = rows.map((r) => r.service).sort();
    return { ids: new Set(names), names };
  }, [status]);
}
