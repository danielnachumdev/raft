import { useEffect, useMemo, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import {
  fetchMetrics,
  METRICS_POLL_MS,
  type MetricsAvailable,
  type MetricsPayload,
  type MetricsSeries,
} from "./api";
import { peekMetrics, putMetrics } from "./dashboardCache";
import { TrendsChart } from "./TrendsChart";
import {
  DEFAULT_RUNTIME_WINDOW,
  RUNTIME_METRICS,
  RUNTIME_WINDOWS,
  type RuntimeMetricDef,
  type RuntimeMetricId,
} from "./runtimeMetrics";

export type ScopeKind = "all" | "host" | "containers";

/** Historical resource trends from /api/metrics (HTTP poll + since cursor). */
export function TrendsPanel() {
  const [windowSec, setWindowSec] = useState(DEFAULT_RUNTIME_WINDOW);
  const [metricId, setMetricId] = useState<RuntimeMetricId>("cpu_percent");
  const [aggregate, setAggregate] = useState(false);
  const [scope, setScope] = useState<ScopeKind>("all");
  const [selected, setSelected] = useState<string[] | null>(null);
  const [series, setSeries] = useState<MetricsSeries[]>(() => {
    return peekMetrics(DEFAULT_RUNTIME_WINDOW)?.series ?? [];
  });
  const [available, setAvailable] = useState<MetricsAvailable[]>(() => {
    return peekMetrics(DEFAULT_RUNTIME_WINDOW)?.available ?? [];
  });
  const [cursor, setCursor] = useState<string | null>(() => {
    return peekMetrics(DEFAULT_RUNTIME_WINDOW)?.cursor ?? null;
  });
  const [busy, setBusy] = useState(
    () => peekMetrics(DEFAULT_RUNTIME_WINDOW) === null,
  );
  const metric =
    RUNTIME_METRICS.find((m) => m.id === metricId) ?? RUNTIME_METRICS[0];
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const cached = peekMetrics(windowSec);
    if (cached) {
      setSeries(cached.series);
      setAvailable(cached.available);
      setCursor(cached.cursor);
      setSelected(null);
    } else {
      setSeries([]);
      setAvailable([]);
      setCursor(null);
      setSelected(null);
    }
    setBusy(true);
    setError(null);
    void (async () => {
      try {
        const payload = await fetchMetrics({ window: windowSec });
        if (cancelled) return;
        putMetrics(windowSec, payload);
        applyFull(payload, setSeries, setAvailable, setCursor, setSelected);
      } catch {
        if (!cancelled && !cached) {
          setError("Failed to load metrics history.");
        }
      } finally {
        if (!cancelled) setBusy(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [windowSec]);

  useEffect(() => {
    if (busy) return;
    const id = window.setInterval(() => {
      void pollIncremental(windowSec, cursor, setSeries, setAvailable, setCursor);
    }, METRICS_POLL_MS);
    return () => window.clearInterval(id);
  }, [windowSec, cursor, busy]);

  const catalog = useMemo(
    () => available.filter((a) => matchesScope(a.kind, a.id, scope)),
    [available, scope],
  );
  const activeIds = selected ?? catalog.map((a) => a.id);
  const showingAll =
    selected === null ||
    (catalog.length > 0 && activeIds.length === catalog.length);
  const visible = useMemo(() => {
    const scoped = series.filter((s) => matchesScope(s.kind, s.id, scope));
    // selected === null → all in scope (do not require available ∩ series).
    if (selected === null) return scoped;
    return scoped.filter((s) => selected.includes(s.id));
  }, [series, selected, scope]);

  const showColdLoad = busy && series.length === 0;

  return (
    <section className="panel trends" id="trends">
      <div className="panel-head">
        <h2>Trends</h2>
        <p className="muted panel-kind" aria-live="polite">
          {showColdLoad
            ? "Loading…"
            : busy
              ? "Updating…"
              : "Historical · recorded metrics"}
        </p>
      </div>

      <div className="trends-layout">
        <TrendsFilters
          windowSec={windowSec}
          metric={metric}
          aggregate={aggregate}
          scope={scope}
          available={catalog}
          activeIds={activeIds}
          showingAll={showingAll}
          busy={busy}
          onWindow={setWindowSec}
          onMetric={setMetricId}
          onAggregate={setAggregate}
          onScope={(next) => {
            setScope(next);
            setSelected(null);
          }}
          onToggle={(id) => setSelected(toggleId(activeIds, id, catalog))}
          onShowAll={() => setSelected(null)}
          onClearAll={() => setSelected([])}
        />
        <div className="trends-main">
          {showColdLoad ? (
            <div
              className="trends-loading"
              role="status"
              aria-busy="true"
              id="trends-loading"
            >
              <span className="spinner" aria-hidden="true" />
              <p>Loading metrics…</p>
            </div>
          ) : (
            <TrendsBody
              error={error}
              series={series}
              visible={visible}
              metric={metric}
              aggregate={aggregate}
            />
          )}
        </div>
      </div>
    </section>
  );
}

function TrendsBody(props: {
  error: string | null;
  series: MetricsSeries[];
  visible: MetricsSeries[];
  metric: RuntimeMetricDef;
  aggregate: boolean;
}) {
  if (props.error) {
    return (
      <p className="error" role="alert">
        {props.error}
      </p>
    );
  }
  if (props.series.length === 0) {
    return (
      <p className="muted">
        No metrics samples yet. The controller writes{" "}
        <code>state/metrics/resources.jsonl</code> on its metrics interval.
      </p>
    );
  }
  if (props.visible.length === 0) {
    return <p className="muted">Select at least one service to plot.</p>;
  }
  return (
    <TrendsChart
      series={props.visible}
      metric={props.metric.id}
      unit={props.metric.unit}
      aggregate={props.aggregate}
    />
  );
}

function TrendsFilters(props: {
  windowSec: number;
  metric: RuntimeMetricDef;
  aggregate: boolean;
  scope: ScopeKind;
  available: MetricsAvailable[];
  activeIds: string[];
  showingAll: boolean;
  busy: boolean;
  onWindow: (n: number) => void;
  onMetric: (m: RuntimeMetricId) => void;
  onAggregate: (v: boolean) => void;
  onScope: (s: ScopeKind) => void;
  onToggle: (id: string) => void;
  onShowAll: () => void;
  onClearAll: () => void;
}) {
  return (
    <aside className="trends-sidebar" aria-label="Trend filters">
      <label className="trends-field">
        <span>Range</span>
        <select
          value={props.windowSec}
          onChange={(e) => props.onWindow(Number(e.target.value))}
          aria-label="Time range"
          disabled={props.busy}
        >
          {RUNTIME_WINDOWS.map((w) => (
            <option key={w.seconds} value={w.seconds}>
              {w.label}
            </option>
          ))}
        </select>
      </label>
      <label className="trends-field">
        <span>Metric</span>
        <select
          value={props.metric.id}
          onChange={(e) =>
            props.onMetric(e.target.value as RuntimeMetricId)
          }
          aria-label="Metric type"
          disabled={props.busy}
        >
          {RUNTIME_METRICS.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label}
            </option>
          ))}
        </select>
      </label>
      <label className="trends-field">
        <span>View</span>
        <select
          value={props.aggregate ? "aggregate" : "per"}
          onChange={(e) => props.onAggregate(e.target.value === "aggregate")}
          aria-label="Series view"
          disabled={props.busy}
        >
          <option value="per">Per service</option>
          <option value="aggregate">Aggregate avg</option>
        </select>
      </label>
      <label className="trends-field">
        <span>Scope</span>
        <select
          value={props.scope}
          onChange={(e) => props.onScope(e.target.value as ScopeKind)}
          aria-label="Host or containers"
          disabled={props.busy}
        >
          <option value="all">Host + services</option>
          <option value="containers">Services only</option>
          <option value="host">Host only</option>
        </select>
      </label>
      <ServicesFilter
        available={props.available}
        activeIds={props.activeIds}
        showingAll={props.showingAll}
        busy={props.busy}
        onToggle={props.onToggle}
        onShowAll={props.onShowAll}
        onClearAll={props.onClearAll}
      />
    </aside>
  );
}

function ServicesFilter(props: {
  available: MetricsAvailable[];
  activeIds: string[];
  showingAll: boolean;
  busy: boolean;
  onToggle: (id: string) => void;
  onShowAll: () => void;
  onClearAll: () => void;
}) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return props.available;
    return props.available.filter(
      (a) =>
        a.label.toLowerCase().includes(q) || a.id.toLowerCase().includes(q),
    );
  }, [props.available, query]);
  const noneSelected = props.activeIds.length === 0;

  return (
    <div className="trends-services-block">
      <div className="trends-services-head">
        <span className="trends-services-title">Services</span>
        <div className="trends-services-actions">
          <button
            type="button"
            className="trends-clear-all"
            onClick={props.onClearAll}
            disabled={
              props.busy || noneSelected || props.available.length === 0
            }
          >
            Clear all
          </button>
          <button
            type="button"
            className="trends-show-all"
            onClick={props.onShowAll}
            disabled={
              props.busy || props.showingAll || props.available.length === 0
            }
          >
            Show all
          </button>
        </div>
      </div>
      <input
        type="search"
        className="trends-services-search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search services"
        aria-label="Search services"
        disabled={props.busy}
      />
      <div className="trends-services-list" role="group" aria-label="Services">
        {filtered.length === 0 ? (
          <p className="muted trends-services-empty">No matching services</p>
        ) : (
          filtered.map((a) => (
            <label key={a.id} className="trends-chip">
              <input
                type="checkbox"
                checked={props.activeIds.includes(a.id)}
                onChange={() => props.onToggle(a.id)}
                disabled={props.busy}
              />
              <span className="trends-chip-label">{a.label}</span>
            </label>
          ))
        )}
      </div>
    </div>
  );
}

function applyFull(
  payload: MetricsPayload,
  setSeries: (s: MetricsSeries[]) => void,
  setAvailable: (a: MetricsAvailable[]) => void,
  setCursor: (c: string | null) => void,
  setSelected: (s: string[] | null) => void,
) {
  setSeries(payload.series);
  setAvailable(payload.available);
  setCursor(payload.cursor);
  setSelected(null);
}

async function pollIncremental(
  windowSec: number,
  cursor: string | null,
  setSeries: Dispatch<SetStateAction<MetricsSeries[]>>,
  setAvailable: (a: MetricsAvailable[]) => void,
  setCursor: (c: string | null) => void,
) {
  try {
    const payload = await fetchMetrics({
      window: windowSec,
      since: cursor ?? undefined,
    });
    if (payload.available.length) setAvailable(payload.available);
    if (!payload.series.length) return;
    setSeries((prev) => mergeSeries(prev, payload.series));
    if (payload.cursor) setCursor(payload.cursor);
  } catch {
    /* keep last good chart on transient poll errors */
  }
}

function mergeSeries(prev: MetricsSeries[], delta: MetricsSeries[]): MetricsSeries[] {
  const map = new Map(prev.map((s) => [s.id, { ...s, points: [...s.points] }]));
  for (const s of delta) {
    const cur = map.get(s.id);
    if (!cur) {
      map.set(s.id, { ...s, points: [...s.points] });
      continue;
    }
    const seen = new Set(cur.points.map((p) => p.t));
    for (const p of s.points) {
      if (!seen.has(p.t)) cur.points.push(p);
    }
  }
  return [...map.values()];
}

function toggleId(
  active: string[],
  id: string,
  available: MetricsAvailable[],
): string[] {
  if (active.includes(id)) {
    return active.filter((x) => x !== id);
  }
  const next = [...active, id];
  return available.map((a) => a.id).filter((x) => next.includes(x));
}

function matchesScope(kind: string, id: string, scope: ScopeKind): boolean {
  const isHost = kind === "host" || id === "host";
  if (scope === "all") return true;
  if (scope === "host") return isHost;
  return !isHost;
}
