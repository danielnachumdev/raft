import { useMemo, useState } from "react";
import type { MetricsAvailable } from "../shared/api";
import {
  RUNTIME_METRICS,
  RUNTIME_WINDOWS,
  type RuntimeMetricDef,
  type RuntimeMetricId,
} from "./runtimeMetrics";
import type { GroupOption, SeriesViewMode } from "./trendsView";

export function TrendsFilters(props: {
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
