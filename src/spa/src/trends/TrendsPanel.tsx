import { useEffect, useMemo, useState } from "react";
import {
  fetchMetrics,
  METRICS_POLL_MS,
  type GraphEvent,
  type MetricsAvailable,
  type MetricsSeries,
} from "../shared/api";
import { peekMetrics, putMetrics } from "../shared/dashboardCache";
import { TrendsBody } from "./TrendsBody";
import { TrendsFilters } from "./TrendsFilters";
import {
  DEFAULT_RUNTIME_WINDOW,
  RUNTIME_METRICS,
  type RuntimeMetricId,
} from "./runtimeMetrics";
import {
  applyFull,
  pollIncremental,
  toggleId,
} from "./trendsPoll";
import {
  groupOptions,
  resolveVisibleSeries,
  usesGroupPicker,
  type SeriesViewMode,
} from "./trendsView";

/** Historical resource trends from /api/metrics (HTTP poll + since cursor). */
export function TrendsPanel() {
  const [windowSec, setWindowSec] = useState(DEFAULT_RUNTIME_WINDOW);
  const [metricId, setMetricId] = useState<RuntimeMetricId>("cpu_percent");
  const [viewMode, setViewMode] = useState<SeriesViewMode>("per_service");
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
  const [events, setEvents] = useState<GraphEvent[]>(() => {
    return peekMetrics(DEFAULT_RUNTIME_WINDOW)?.events ?? [];
  });
  const [busy, setBusy] = useState(
    () => peekMetrics(DEFAULT_RUNTIME_WINDOW) === null,
  );
  const metric =
    RUNTIME_METRICS.find((m) => m.id === metricId) ?? RUNTIME_METRICS[0];
  const [error, setError] = useState<string | null>(null);
  const groupMode = usesGroupPicker(viewMode);

  useEffect(() => {
    let cancelled = false;
    const cached = peekMetrics(windowSec);
    if (cached) {
      setSeries(cached.series);
      setAvailable(cached.available);
      setCursor(cached.cursor);
      setEvents(cached.events ?? []);
    } else {
      setSeries([]);
      setAvailable([]);
      setCursor(null);
      setEvents([]);
    }
    setBusy(true);
    setError(null);
    void (async () => {
      try {
        const payload = await fetchMetrics({ window: windowSec });
        if (cancelled) return;
        putMetrics(windowSec, payload);
        applyFull(
          payload,
          setSeries,
          setAvailable,
          setCursor,
          setEvents,
        );
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
      void pollIncremental(
        windowSec,
        cursor,
        setSeries,
        setAvailable,
        setCursor,
        setEvents,
      );
    }, METRICS_POLL_MS);
    return () => window.clearInterval(id);
  }, [windowSec, cursor, busy]);

  const groups = useMemo(() => groupOptions(available), [available]);
  const pickerIds = groupMode
    ? groups.map((g) => g.id)
    : available.map((a) => a.id);
  const activeIds = selected ?? pickerIds;
  const showingAll =
    selected === null ||
    (pickerIds.length > 0 && activeIds.length === pickerIds.length);

  const visible = useMemo(
    () =>
      resolveVisibleSeries({
        series,
        viewMode,
        selected,
        activeIds,
        metricId: metric.id,
      }),
    [series, viewMode, selected, activeIds, metric.id],
  );

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
          viewMode={viewMode}
          groupMode={groupMode}
          catalog={available}
          groups={groups}
          activeIds={activeIds}
          showingAll={showingAll}
          busy={busy}
          onWindow={setWindowSec}
          onMetric={setMetricId}
          onViewMode={(next) => {
            setViewMode(next);
            setSelected(null);
          }}
          onToggle={(id) => setSelected(toggleId(activeIds, id, pickerIds))}
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
              windowSec={windowSec}
              viewMode={viewMode}
              groupMode={groupMode}
              events={events}
            />
          )}
        </div>
      </div>
    </section>
  );
}
