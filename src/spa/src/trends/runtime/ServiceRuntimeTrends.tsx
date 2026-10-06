import { useEffect, useMemo, useState } from "react";
import { DownloadMenu } from "../../export/DownloadMenu";
import { metricsDownloadUrl } from "../../export/urls";
import {
  fetchMetrics,
  METRICS_POLL_MS,
  type GraphEvent,
  type MetricsBounds,
  type MetricsSeries,
} from "../../shared/api";
import { eventsForSeries } from "../chart/graphEvents";
import { chartEndMs } from "../chart/chartTimeScale";
import { useLiveNow } from "../chart/useLiveNow";
import {
  RUNTIME_METRICS,
  type RuntimeMetricId,
} from "../runtimeMetrics";
import { TrendsRangeControls } from "../TrendsRangeControls";
import {
  defaultRangeState,
  isLiveQuery,
  isRollingWindow,
  toQuery,
  type TrendsRangeState,
} from "../trendsRange";
import { RuntimeTrendsBody } from "./RuntimeTrendsBody";
import {
  buildRows,
  pollServiceMetrics,
} from "./runtimeTrendsPoll";

/** Per-service Runtime history charts (same /api/metrics as Trends). */
export function ServiceRuntimeTrends(props: { service: string }) {
  const [range, setRange] = useState<TrendsRangeState>(defaultRangeState);
  const query = useMemo(() => toQuery(range), [range]);
  const rolling = isRollingWindow(query);
  const nowMs = useLiveNow(rolling);
  const [metricId, setMetricId] = useState<RuntimeMetricId>("cpu_percent");
  const [series, setSeries] = useState<MetricsSeries | null>(null);
  const [events, setEvents] = useState<GraphEvent[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [bounds, setBounds] = useState<MetricsBounds | null>(null);
  const [clampMessage, setClampMessage] = useState<string | null>(null);
  const [windowSec, setWindowSec] = useState(query.window);
  const [rangeTo, setRangeTo] = useState<string | null>(null);
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
          ...query,
          services: [props.service],
        });
        if (cancelled) return;
        setSeries(payload.series.find((s) => s.id === props.service) ?? null);
        setEvents(payload.events ?? []);
        setCursor(payload.cursor);
        setBounds(payload.bounds ?? null);
        setClampMessage(payload.clamped ? payload.clamp_message ?? null : null);
        setWindowSec(payload.window_seconds);
        setRangeTo(payload.to);
      } catch {
        if (!cancelled) setError("Failed to load runtime metrics.");
      } finally {
        if (!cancelled) setBusy(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [props.service, query]);

  useEffect(() => {
    if (busy || !isLiveQuery(query)) return;
    const id = window.setInterval(() => {
      void pollServiceMetrics(
        props.service, query, cursor, setSeries, setCursor, setEvents,
      );
    }, METRICS_POLL_MS);
    return () => window.clearInterval(id);
  }, [props.service, query, cursor, busy]);

  const markers = useMemo(
    () => eventsForSeries(events, series ? [series] : []),
    [events, series],
  );
  const rows = useMemo(
    () => buildRows(series, metric.id),
    [series, metric.id],
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
        <DownloadMenu
          kind="metrics"
          hrefFor={(formatId) =>
            metricsDownloadUrl({
              formatId,
              window: windowSec,
              services: [props.service],
            })
          }
          disabled={showCold || Boolean(error)}
        />
      </div>
      <div className="service-runtime-controls">
        <TrendsRangeControls
          range={range}
          bounds={bounds}
          clampMessage={clampMessage}
          busy={busy && series === null}
          onChange={setRange}
        />
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
        rangeEndMs={chartEndMs({ rolling, nowMs, rangeEndIso: rangeTo })}
        events={markers}
      />
    </section>
  );
}
