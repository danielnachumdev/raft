import { useEffect, useMemo, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  YAxis,
} from "recharts";
import {
  fetchMetrics,
  METRICS_POLL_MS,
  type GraphEvent,
  type MetricsSeries,
} from "./api";
import {
  formatTooltipTime,
  mergeTimedRows,
  toEpochMs,
} from "./chartTimeScale";
import { graphEventMarkers } from "./GraphEventMarkers";
import { eventsForSeries, withEventRows } from "./graphEvents";
import {
  DEFAULT_RUNTIME_WINDOW,
  formatRuntimeValue,
  RUNTIME_METRICS,
  RUNTIME_WINDOWS,
  runtimePointValue,
  type RuntimeMetricDef,
  type RuntimeMetricId,
  yAxisUnit,
} from "./runtimeMetrics";
import { timeScaleXAxis } from "./TimeScaleXAxis";

type ChartRow = {
  ts: number;
  t: string;
  label: string;
  value: number | null;
};

/** Per-service Runtime history charts (same /api/metrics as Trends). */
export function ServiceRuntimeTrends(props: { service: string }) {
  const [windowSec, setWindowSec] = useState(DEFAULT_RUNTIME_WINDOW);
  const [metricId, setMetricId] = useState<RuntimeMetricId>("cpu_percent");
  const [series, setSeries] = useState<MetricsSeries | null>(null);
  const [events, setEvents] = useState<GraphEvent[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const metric =
    RUNTIME_METRICS.find((m) => m.id === metricId) ?? RUNTIME_METRICS[0];

  useEffect(() => {
    let cancelled = false;
    setBusy(true);
    setError(null);
    setSeries(null);
    setEvents([]);
    setCursor(null);
    void (async () => {
      try {
        const payload = await fetchMetrics({
          window: windowSec,
          services: [props.service],
        });
        if (cancelled) return;
        const match =
          payload.series.find((s) => s.id === props.service) ?? null;
        setSeries(match);
        setEvents(payload.events ?? []);
        setCursor(payload.cursor);
      } catch {
        if (!cancelled) setError("Failed to load runtime metrics.");
      } finally {
        if (!cancelled) setBusy(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [props.service, windowSec]);

  useEffect(() => {
    if (busy) return;
    const id = window.setInterval(() => {
      void pollServiceMetrics(
        props.service,
        windowSec,
        cursor,
        setSeries,
        setCursor,
        setEvents,
      );
    }, METRICS_POLL_MS);
    return () => window.clearInterval(id);
  }, [props.service, windowSec, cursor, busy]);

  const markers = useMemo(
    () => eventsForSeries(events, series ? [series] : []),
    [events, series],
  );
  const rows = useMemo(
    () =>
      withEventRows(buildRows(series, metric.id), markers, (t, label) => ({
        ts: toEpochMs(t) ?? 0,
        t,
        label,
        value: null,
      })),
    [series, metric.id, markers],
  );
  const showCold = busy && series === null && !error;

  return (
    <section className="panel service-runtime-trends">
      <div className="panel-head">
        <h2>Runtime trends</h2>
        <p className="muted panel-kind" aria-live="polite">
          {showCold
            ? "Loading…"
            : busy
              ? "Updating…"
              : "Historical · recorded metrics"}
        </p>
      </div>
      <div className="service-runtime-controls">
        <label className="trends-field">
          <span>Range</span>
          <select
            value={windowSec}
            onChange={(e) => setWindowSec(Number(e.target.value))}
            aria-label="Time range"
            disabled={busy && series === null}
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
            value={metric.id}
            onChange={(e) => setMetricId(e.target.value as RuntimeMetricId)}
            aria-label="Runtime metric"
            disabled={busy && series === null}
          >
            {RUNTIME_METRICS.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <RuntimeTrendsBody
        error={error}
        showCold={showCold}
        series={series}
        rows={rows}
        metric={metric}
        windowSec={windowSec}
        events={markers}
      />
    </section>
  );
}

function RuntimeTrendsBody(props: {
  error: string | null;
  showCold: boolean;
  series: MetricsSeries | null;
  rows: ChartRow[];
  metric: RuntimeMetricDef;
  windowSec: number;
  events: GraphEvent[];
}) {
  if (props.error) {
    return (
      <p className="error" role="alert">
        {props.error}
      </p>
    );
  }
  if (props.showCold) {
    return (
      <div className="trends-loading" role="status" aria-busy="true">
        <span className="spinner" aria-hidden="true" />
        <p>Loading metrics…</p>
      </div>
    );
  }
  if (!props.series || props.series.points.length === 0) {
    return (
      <p className="muted">
        No metrics samples yet for this service. The controller writes{" "}
        <code>state/metrics/resources.jsonl</code> on its metrics interval.
      </p>
    );
  }
  if (props.rows.every((r) => r.value === null)) {
    return (
      <p className="muted">
        No samples for {props.metric.label} in this window (older JSONL may
        omit newer Runtime fields).
      </p>
    );
  }
  return (
    <ServiceRuntimeChart
      rows={props.rows}
      metric={props.metric}
      windowSec={props.windowSec}
      events={props.events}
    />
  );
}

function ServiceRuntimeChart(props: {
  rows: ChartRow[];
  metric: RuntimeMetricDef;
  windowSec: number;
  events: GraphEvent[];
}) {
  const unit = yAxisUnit(props.metric.unit);
  return (
    <div
      className="trends-chart"
      role="img"
      aria-label={`${props.metric.label} trend chart`}
    >
      <ResponsiveContainer width="100%" height={260}>
        <LineChart
          data={props.rows}
          margin={{ top: 8, right: 12, left: 0, bottom: 0 }}
        >
          <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" />
          {timeScaleXAxis(props.windowSec)}
          <YAxis
            tick={{ fill: "var(--muted)", fontSize: 11 }}
            unit={unit || undefined}
            width={56}
            domain={[0, "auto"]}
            tickFormatter={(v: number) =>
              props.metric.unit === "bytes"
                ? formatRuntimeValue(v, "bytes")
                : String(v)
            }
          />
          <Tooltip
            contentStyle={{
              background: "var(--panel)",
              border: "1px solid var(--line)",
              borderRadius: "0.4rem",
            }}
            labelFormatter={(_, payload) => {
              const row = payload?.[0]?.payload as ChartRow | undefined;
              return row?.t ? formatTooltipTime(row.t) : "";
            }}
            formatter={(value: number | string) => [
              formatRuntimeValue(Number(value), props.metric.unit),
              props.metric.label,
            ]}
          />
          <Line
            type="monotone"
            dataKey="value"
            name={props.metric.label}
            stroke="#0f6b5c"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
            connectNulls={false}
          />
          {graphEventMarkers(props.events)}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function buildRows(
  series: MetricsSeries | null,
  metric: RuntimeMetricId,
): ChartRow[] {
  if (!series) return [];
  const points = series.points
    .map((p) => {
      const ts = toEpochMs(p.t);
      if (ts === null) return null;
      return { ts, t: p.t, value: runtimePointValue(p, metric) };
    })
    .filter((p): p is NonNullable<typeof p> => p !== null);
  return mergeTimedRows([{ key: "value", points }]) as ChartRow[];
}

async function pollServiceMetrics(
  service: string,
  windowSec: number,
  cursor: string | null,
  setSeries: Dispatch<SetStateAction<MetricsSeries | null>>,
  setCursor: (c: string | null) => void,
  setEvents: (e: GraphEvent[]) => void,
) {
  try {
    const payload = await fetchMetrics({
      window: windowSec,
      since: cursor ?? undefined,
      services: [service],
    });
    setEvents(payload.events ?? []);
    const delta = payload.series.find((s) => s.id === service);
    if (delta && delta.points.length) {
      setSeries((prev) => mergePoints(prev, delta));
    }
    if (payload.cursor) setCursor(payload.cursor);
  } catch {
    /* keep last good chart */
  }
}

function mergePoints(
  prev: MetricsSeries | null,
  delta: MetricsSeries,
): MetricsSeries {
  if (!prev) return delta;
  const seen = new Set(prev.points.map((p) => p.t));
  const points = [...prev.points];
  for (const p of delta.points) {
    if (!seen.has(p.t)) points.push(p);
  }
  return { ...prev, points };
}
