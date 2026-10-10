import { useEffect, useMemo, useState } from "react";
import {
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
import type { RuntimeMetricId } from "../runtimeMetrics";
import {
  DEFAULT_METRIC_IDS,
  metricsFromIds,
  planesForMetrics,
  toggleMetricId,
} from "./metricSelection";
import {
  applyFull,
  applyPayloadMeta,
  fetchPlanes,
  planesCacheKey,
  pollPlanes,
  toggleId,
  type PlaneCursors,
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
import "./TrendsPanel.css";

const INITIAL = defaultRangeState();
const INITIAL_KEY = metricsCacheKey(toQuery(INITIAL));

/** Historical resource trends from /api/metrics (HTTP poll + since cursor). */
export function TrendsPanel() {
  const [range, setRange] = useState<TrendsRangeState>(INITIAL);
  const query = useMemo(() => toQuery(range), [range]);
  const rolling = isRollingWindow(query);
  const nowMs = useLiveNow(rolling);
  const cacheKey = metricsCacheKey(query);
  const [metricIds, setMetricIds] =
    useState<RuntimeMetricId[]>(DEFAULT_METRIC_IDS);
  const [viewMode, setViewMode] = useState<SeriesViewMode>("per_service");
  const [selected, setSelected] = useState<string[] | null>(null);
  const seed = peekMetrics(INITIAL_KEY);
  const [series, setSeries] = useState<MetricsSeries[]>(seed?.series ?? []);
  const [available, setAvailable] = useState<MetricsAvailable[]>(
    seed?.available ?? [],
  );
  const [cursors, setCursors] = useState<PlaneCursors>({});
  const [events, setEvents] = useState<GraphEvent[]>(seed?.events ?? []);
  const [bounds, setBounds] = useState<MetricsBounds | null>(
    seed?.bounds ?? null,
  );
  const [clampMessage, setClampMessage] = useState<string | null>(null);
  const [rangeTo, setRangeTo] = useState<string | null>(seed?.to ?? null);
  const [windowSec, setWindowSec] = useState(query.window);
  const [busy, setBusy] = useState(seed === null);
  const [error, setError] = useState<string | null>(null);
  const metrics = useMemo(() => metricsFromIds(metricIds), [metricIds]);
  const planes = useMemo(() => {
    const selectedPlanes = planesForMetrics(metrics);
    return selectedPlanes.length ? selectedPlanes : (["resources"] as const);
  }, [metrics]);
  const planeCacheKey = planesCacheKey([...planes], cacheKey);
  const groupMode = usesGroupPicker(viewMode);

  useEffect(() => {
    let cancelled = false;
    const cached = peekMetrics(planeCacheKey);
    if (cached) {
      applyFull(cached, setSeries, setAvailable, setEvents);
      applyPayloadMeta(
        cached, setBounds, setClampMessage, setRangeTo, setWindowSec,
      );
    } else {
      setSeries([]);
      setAvailable([]);
      setEvents([]);
    }
    setCursors({});
    setBusy(true);
    setError(null);
    void (async () => {
      try {
        const { payload, cursors: next } = await fetchPlanes([...planes], query);
        if (cancelled) return;
        putMetrics(planeCacheKey, payload);
        applyFull(payload, setSeries, setAvailable, setEvents);
        applyPayloadMeta(
          payload, setBounds, setClampMessage, setRangeTo, setWindowSec,
        );
        setCursors(next);
      } catch {
        if (!cancelled && !cached) setError("Failed to load metrics history.");
      } finally {
        if (!cancelled) setBusy(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [planeCacheKey, planes, query]);

  useEffect(() => {
    if (busy || !isLiveQuery(query)) return;
    const id = window.setInterval(() => {
      void pollPlanes(
        query,
        [...planes],
        cursors,
        setSeries,
        setAvailable,
        setCursors,
        setEvents,
      );
    }, METRICS_POLL_MS);
    return () => window.clearInterval(id);
  }, [query, cursors, busy, planes]);

  const groups = useMemo(() => groupOptions(available), [available]);
  const pickerIds = groupMode
    ? groups.map((g) => g.id)
    : available.map((a) => a.id);
  const activeIds = selected ?? pickerIds;
  const showingAll =
    selected === null ||
    (pickerIds.length > 0 && activeIds.length === pickerIds.length);
  const visible = useMemo(
    () => resolveVisibleSeries({ series, viewMode, selected, activeIds }),
    [series, viewMode, selected, activeIds],
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
          metricIds={metricIds}
          viewMode={viewMode}
          groupMode={groupMode}
          catalog={available}
          groups={groups}
          activeIds={activeIds}
          showingAll={showingAll}
          busy={busy}
          onRange={setRange}
          onToggleMetric={(id) => setMetricIds((cur) => toggleMetricId(cur, id))}
          onClearMetrics={() => setMetricIds([])}
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
              metrics={metrics}
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
