import { useEffect, useMemo, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import {
  fetchMetrics,
  METRICS_POLL_MS,
  type GraphEvent,
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
import {
  buildPerGroupSeries,
  groupOptions,
  isSingleLineAvg,
  seriesInGroups,
  usesGroupPicker,
  type GroupOption,
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
      resolveVisible({
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

function resolveVisible(args: {
  series: MetricsSeries[];
  viewMode: SeriesViewMode;
  selected: string[] | null;
  activeIds: string[];
  metricId: RuntimeMetricId;
}): MetricsSeries[] {
  if (args.viewMode === "per_group") {
    return buildPerGroupSeries(args.series, args.activeIds, args.metricId);
  }
  if (args.viewMode === "avg_group") {
    return seriesInGroups(args.series, args.activeIds);
  }
  if (args.selected === null) return args.series;
  return args.series.filter((s) => args.selected!.includes(s.id));
}

function TrendsBody(props: {
  error: string | null;
  series: MetricsSeries[];
  visible: MetricsSeries[];
  metric: RuntimeMetricDef;
  viewMode: SeriesViewMode;
  groupMode: boolean;
  events: GraphEvent[];
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
    return (
      <p className="muted">
        {props.groupMode
          ? "Select at least one group to plot."
          : "Select at least one service to plot."}
      </p>
    );
  }
  return (
    <TrendsChart
      series={props.visible}
      metric={props.metric.id}
      unit={props.metric.unit}
      aggregate={isSingleLineAvg(props.viewMode)}
      aggregateLabel={
        props.viewMode === "avg_group" ? "Group average" : "Average"
      }
      events={props.events}
      allSeries={props.series}
    />
  );
}

function TrendsFilters(props: {
  windowSec: number;
  metric: RuntimeMetricDef;
  viewMode: SeriesViewMode;
  groupMode: boolean;
  catalog: MetricsAvailable[];
  groups: GroupOption[];
  activeIds: string[];
  showingAll: boolean;
  busy: boolean;
  onWindow: (n: number) => void;
  onMetric: (m: RuntimeMetricId) => void;
  onViewMode: (m: SeriesViewMode) => void;
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
          value={props.viewMode}
          onChange={(e) =>
            props.onViewMode(e.target.value as SeriesViewMode)
          }
          aria-label="Series view"
          disabled={props.busy}
        >
          <option value="per_service">Per service</option>
          <option value="per_group">Per group</option>
          <option value="avg_all">Avg all</option>
          <option value="avg_group">Avg group</option>
        </select>
      </label>
      {props.groupMode ? (
        <IdFilter
          title="Groups"
          searchLabel="Search groups"
          searchPlaceholder="Search groups"
          emptyLabel="No matching groups"
          items={props.groups}
          activeIds={props.activeIds}
          showingAll={props.showingAll}
          busy={props.busy}
          onToggle={props.onToggle}
          onShowAll={props.onShowAll}
          onClearAll={props.onClearAll}
        />
      ) : (
        <IdFilter
          title="Services"
          searchLabel="Search services"
          searchPlaceholder="Search services"
          emptyLabel="No matching services"
          items={props.catalog.map((a) => ({ id: a.id, label: a.label }))}
          activeIds={props.activeIds}
          showingAll={props.showingAll}
          busy={props.busy}
          onToggle={props.onToggle}
          onShowAll={props.onShowAll}
          onClearAll={props.onClearAll}
        />
      )}
    </aside>
  );
}

function IdFilter(props: {
  title: string;
  searchLabel: string;
  searchPlaceholder: string;
  emptyLabel: string;
  items: { id: string; label: string }[];
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
    if (!q) return props.items;
    return props.items.filter(
      (a) =>
        a.label.toLowerCase().includes(q) || a.id.toLowerCase().includes(q),
    );
  }, [props.items, query]);
  const noneSelected = props.activeIds.length === 0;

  return (
    <div className="trends-services-block">
      <div className="trends-services-head">
        <span className="trends-services-title">{props.title}</span>
        <div className="trends-services-actions">
          <button
            type="button"
            className="trends-clear-all"
            onClick={props.onClearAll}
            disabled={props.busy || noneSelected || props.items.length === 0}
          >
            Clear all
          </button>
          <button
            type="button"
            className="trends-show-all"
            onClick={props.onShowAll}
            disabled={
              props.busy || props.showingAll || props.items.length === 0
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
        placeholder={props.searchPlaceholder}
        aria-label={props.searchLabel}
        disabled={props.busy}
      />
      <div
        className="trends-services-list"
        role="group"
        aria-label={props.title}
      >
        {filtered.length === 0 ? (
          <p className="muted trends-services-empty">{props.emptyLabel}</p>
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
  setEvents: (e: GraphEvent[]) => void,
) {
  setSeries(payload.series);
  setAvailable(payload.available);
  setCursor(payload.cursor);
  setEvents(payload.events ?? []);
}

async function pollIncremental(
  windowSec: number,
  cursor: string | null,
  setSeries: Dispatch<SetStateAction<MetricsSeries[]>>,
  setAvailable: (a: MetricsAvailable[]) => void,
  setCursor: (c: string | null) => void,
  setEvents: (e: GraphEvent[]) => void,
) {
  try {
    const payload = await fetchMetrics({
      window: windowSec,
      since: cursor ?? undefined,
    });
    if (payload.available.length) setAvailable(payload.available);
    setEvents(payload.events ?? []);
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

function toggleId(active: string[], id: string, order: string[]): string[] {
  if (active.includes(id)) {
    return active.filter((x) => x !== id);
  }
  const next = [...active, id];
  return order.filter((x) => next.includes(x));
}
