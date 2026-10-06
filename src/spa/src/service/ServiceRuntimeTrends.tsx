import { useEffect, useMemo, useState } from "react";
import { DownloadMenu } from "../export/DownloadMenu";
import { metricsDownloadUrl } from "../export/urls";
import {
  fetchMetrics,
  METRICS_POLL_MS,
  type GraphEvent,
  type MetricsSeries,
} from "../shared/api";
import { eventsForSeries } from "../trends/graphEvents";
import {
  DEFAULT_RUNTIME_WINDOW,
  RUNTIME_METRICS,
  RUNTIME_WINDOWS,
  type RuntimeMetricId,
} from "../trends/runtimeMetrics";
import { RuntimeTrendsBody } from "./RuntimeTrendsBody";
import {
  buildRows,
  pollServiceMetrics,
} from "./runtimeTrendsPoll";

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
