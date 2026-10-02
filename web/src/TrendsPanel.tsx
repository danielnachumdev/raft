import { useCallback, useEffect, useMemo, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import {
  fetchMetrics,
  METRICS_POLL_MS,
  type MetricsAvailable,
  type MetricsPayload,
  type MetricsSeries,
} from "./api";
import { TrendsChart, type MetricKind } from "./TrendsChart";

const WINDOWS: { seconds: number; label: string }[] = [
  { seconds: 900, label: "15m" },
  { seconds: 3600, label: "1h" },
  { seconds: 21600, label: "6h" },
  { seconds: 86400, label: "24h" },
  { seconds: 604800, label: "7d" },
];

/** Live resource trends from /api/metrics (HTTP poll + since cursor). */
export function TrendsPanel() {
  const [windowSec, setWindowSec] = useState(3600);
  const [metric, setMetric] = useState<MetricKind>("cpu");
  const [aggregate, setAggregate] = useState(false);
  const [selected, setSelected] = useState<string[] | null>(null);
  const [series, setSeries] = useState<MetricsSeries[]>([]);
  const [available, setAvailable] = useState<MetricsAvailable[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadFull = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const payload = await fetchMetrics({ window: windowSec });
      applyFull(payload, setSeries, setAvailable, setCursor, setSelected);
    } catch {
      setError("Failed to load metrics history.");
    } finally {
      setBusy(false);
    }
  }, [windowSec]);

  useEffect(() => {
    void loadFull();
  }, [loadFull]);

  useEffect(() => {
    if (busy) return;
    const id = window.setInterval(() => {
      void pollIncremental(windowSec, cursor, setSeries, setCursor);
    }, METRICS_POLL_MS);
    return () => window.clearInterval(id);
  }, [windowSec, cursor, busy]);

  const activeIds = selected ?? available.map((a) => a.id);
  const visible = useMemo(
    () => series.filter((s) => activeIds.includes(s.id)),
    [series, activeIds],
  );

  return (
    <section className="panel trends" id="trends">
      <div className="trends-head">
        <h2>Trends</h2>
        <p className="muted trends-live" aria-live="polite">
          {busy ? "Loading…" : "Live · polls every 5s"}
        </p>
      </div>

      <TrendsControls
        windowSec={windowSec}
        metric={metric}
        aggregate={aggregate}
        available={available}
        activeIds={activeIds}
        busy={busy}
        onWindow={setWindowSec}
        onMetric={setMetric}
        onAggregate={setAggregate}
        onToggle={(id) => setSelected(toggleId(activeIds, id, available))}
      />

      {busy ? (
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
    </section>
  );
}

function TrendsBody(props: {
  error: string | null;
  series: MetricsSeries[];
  visible: MetricsSeries[];
  metric: MetricKind;
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
      metric={props.metric}
      aggregate={props.aggregate}
    />
  );
}

function TrendsControls(props: {
  windowSec: number;
  metric: MetricKind;
  aggregate: boolean;
  available: MetricsAvailable[];
  activeIds: string[];
  busy: boolean;
  onWindow: (n: number) => void;
  onMetric: (m: MetricKind) => void;
  onAggregate: (v: boolean) => void;
  onToggle: (id: string) => void;
}) {
  return (
    <div className="trends-controls">
      <label className="trends-field">
        <span>Range</span>
        <select
          value={props.windowSec}
          onChange={(e) => props.onWindow(Number(e.target.value))}
          aria-label="Time range"
          disabled={props.busy}
        >
          {WINDOWS.map((w) => (
            <option key={w.seconds} value={w.seconds}>
              {w.label}
            </option>
          ))}
        </select>
      </label>
      <label className="trends-field">
        <span>Metric</span>
        <select
          value={props.metric}
          onChange={(e) => props.onMetric(e.target.value as MetricKind)}
          aria-label="Metric type"
          disabled={props.busy}
        >
          <option value="cpu">CPU %</option>
          <option value="memory">Memory %</option>
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
      <div className="trends-services" role="group" aria-label="Services">
        {props.available.map((a) => (
          <label key={a.id} className="trends-chip">
            <input
              type="checkbox"
              checked={props.activeIds.includes(a.id)}
              onChange={() => props.onToggle(a.id)}
              disabled={props.busy}
            />
            {a.label}
          </label>
        ))}
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
  setCursor: (c: string | null) => void,
) {
  try {
    const payload = await fetchMetrics({
      window: windowSec,
      since: cursor ?? undefined,
    });
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
