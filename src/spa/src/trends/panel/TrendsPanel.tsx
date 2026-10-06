import { useEffect, useMemo, useState } from "react";
import {
  fetchMetrics,
  METRICS_POLL_MS,
  type GraphEvent,
  type MetricsAvailable,
  type MetricsBounds,
  type MetricsSeries,
} from "../../shared/api";
import { DownloadMenu } from "../../export/DownloadMenu";
import { metricsDownloadUrl } from "../../export/urls";
import { peekMetrics, putMetrics } from "../../shared/dashboardCache";
import { chartEndMs } from "../chart/chartTimeScale";
import { useLiveNow } from "../chart/useLiveNow";
import { TrendsBody } from "./TrendsBody";
import { TrendsFilters } from "./TrendsFilters";
import {
  RUNTIME_METRICS,
  type RuntimeMetricId,
} from "../runtimeMetrics";
import {
  applyFull,
  applyPayloadMeta,
  pollIncremental,
  toggleId,
} from "./trendsPoll";
import {
  defaultRangeState,
  isLiveQuery,
  isRollingWindow,
  metricsCacheKey,
  toQuery,
  type TrendsRangeState,
} from "../trendsRange";
import {
  groupOptions,
  resolveVisibleSeries,
  usesGroupPicker,
  type SeriesViewMode,
} from "./trendsView";

const INITIAL = defaultRangeState();
const INITIAL_KEY = metricsCacheKey(toQuery(INITIAL));

/** Historical resource trends from /api/metrics (HTTP poll + since cursor). */
export function TrendsPanel() {
  const [range, setRange] = useState<TrendsRangeState>(INITIAL);
  const query = useMemo(() => toQuery(range), [range]);
  const rolling = isRollingWindow(query);
  const nowMs = useLiveNow(rolling);
  const cacheKey = metricsCacheKey(query);
  const [metricId, setMetricId] = useState<RuntimeMetricId>("cpu_percent");
  const [viewMode, setViewMode] = useState<SeriesViewMode>("per_service");
  const [selected, setSelected] = useState<string[] | null>(null);
  const seed = peekMetrics(INITIAL_KEY);
  const [series, setSeries] = useState<MetricsSeries[]>(seed?.series ?? []);
  const [available, setAvailable] = useState<MetricsAvailable[]>(
    seed?.available ?? [],
  );
  const [cursor, setCursor] = useState<string | null>(seed?.cursor ?? null);
  const [events, setEvents] = useState<GraphEvent[]>(seed?.events ?? []);
  const [bounds, setBounds] = useState<MetricsBounds | null>(
    seed?.bounds ?? null,
  );
  const [clampMessage, setClampMessage] = useState<string | null>(null);
  const [rangeTo, setRangeTo] = useState<string | null>(seed?.to ?? null);
  const [windowSec, setWindowSec] = useState(query.window);
  const [busy, setBusy] = useState(seed === null);
  const [error, setError] = useState<string | null>(null);
  const metric =
    RUNTIME_METRICS.find((m) => m.id === metricId) ?? RUNTIME_METRICS[0];
  const groupMode = usesGroupPicker(viewMode);

  useEffect(() => {
    let cancelled = false;
    const cached = peekMetrics(cacheKey);
    if (cached) {
      applyFull(cached, setSeries, setAvailable, setCursor, setEvents);
      applyPayloadMeta(
        cached, setBounds, setClampMessage, setRangeTo, setWindowSec,
      );
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
        const payload = await fetchMetrics(query);
        if (cancelled) return;
        putMetrics(cacheKey, payload);
        applyFull(payload, setSeries, setAvailable, setCursor, setEvents);
        applyPayloadMeta(
          payload, setBounds, setClampMessage, setRangeTo, setWindowSec,
        );
      } catch {
        if (!cancelled && !cached) setError("Failed to load metrics history.");
      } finally {
        if (!cancelled) setBusy(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [cacheKey, query]);

  useEffect(() => {
    if (busy || !isLiveQuery(query)) return;
    const id = window.setInterval(() => {
      void pollIncremental(
        query, cursor, setSeries, setAvailable, setCursor, setEvents,
      );
    }, METRICS_POLL_MS);
    return () => window.clearInterval(id);
  }, [query, cursor, busy]);

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
        series, viewMode, selected, activeIds, metricId: metric.id,
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
        <DownloadMenu
          kind="metrics"
          hrefFor={(formatId) =>
            metricsDownloadUrl({
              formatId,
              window: windowSec,
              services: showingAll ? undefined : activeIds,
            })
          }
          disabled={showColdLoad || (!showingAll && activeIds.length === 0)}
        />
      </div>
      <div className="trends-layout">
        <TrendsFilters
          range={range}
          bounds={bounds}
          clampMessage={clampMessage}
          metric={metric}
          viewMode={viewMode}
          groupMode={groupMode}
          catalog={available}
          groups={groups}
          activeIds={activeIds}
          showingAll={showingAll}
          busy={busy}
          onRange={setRange}
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
              rangeEndMs={chartEndMs({ rolling, nowMs, rangeEndIso: rangeTo })}
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
