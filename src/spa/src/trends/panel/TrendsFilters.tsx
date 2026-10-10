import { useMemo, useState } from "react";
import type { MetricsAvailable, MetricsBounds } from "../../shared/api";
import type { RuntimeMetricId } from "../runtimeMetrics";
import { TrendsRangeControls } from "../TrendsRangeControls";
import type { TrendsRangeState } from "../trendsRange";
import {
  isMetricTypeBlocked,
  metricFilterSections,
  THIRD_TYPE_BLOCK_REASON,
} from "./metricSelection";
import type { GroupOption, SeriesViewMode } from "./trendsView";
import "./TrendsFilters.css";

export function TrendsFilters(props: {
  range: TrendsRangeState;
  bounds: MetricsBounds | null;
  clampMessage: string | null;
  metricIds: RuntimeMetricId[];
  viewMode: SeriesViewMode;
  groupMode: boolean;
  catalog: MetricsAvailable[];
  groups: GroupOption[];
  activeIds: string[];
  showingAll: boolean;
  busy: boolean;
  onRange: (next: TrendsRangeState) => void;
  onToggleMetric: (id: RuntimeMetricId) => void;
  onClearMetrics: () => void;
  onViewMode: (m: SeriesViewMode) => void;
  onToggle: (id: string) => void;
  onShowAll: () => void;
  onClearAll: () => void;
}) {
  return (
    <aside className="trends-sidebar" aria-label="Trend filters">
      <TrendsRangeControls
        range={props.range}
        bounds={props.bounds}
        clampMessage={props.clampMessage}
        busy={props.busy}
        onChange={props.onRange}
      />
      <MetricFilter
        activeIds={props.metricIds}
        busy={props.busy}
        onToggle={props.onToggleMetric}
        onClearAll={props.onClearMetrics}
      />
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

function MetricFilter(props: {
  activeIds: RuntimeMetricId[];
  busy: boolean;
  onToggle: (id: RuntimeMetricId) => void;
  onClearAll: () => void;
}) {
  const noneSelected = props.activeIds.length === 0;
  return (
    <div className="trends-services-block trends-metrics-block">
      <div className="trends-services-head">
        <span className="trends-services-title">Metrics</span>
        <div className="trends-services-actions">
          <button
            type="button"
            className="trends-clear-all"
            onClick={props.onClearAll}
            disabled={props.busy || noneSelected}
          >
            Clear all
          </button>
        </div>
      </div>
      <div
        className="trends-services-list"
        role="group"
        aria-label="Metrics"
      >
        {metricFilterSections().map((section) => (
          <div key={section.plane} className="trends-metric-plane-block">
            <p className="trends-metric-plane">{section.planeLabel}</p>
            {section.types.map(({ type, metrics }) => (
              <div key={type.id} className="trends-metric-type-block">
                <p className="trends-metric-type">{type.label}</p>
                {metrics.map((m) => {
                  const typeBlocked = isMetricTypeBlocked(
                    props.activeIds,
                    m.id,
                  );
                  return (
                    <MetricChip
                      key={m.id}
                      id={m.id}
                      label={m.label}
                      checked={props.activeIds.includes(m.id)}
                      busy={props.busy}
                      typeBlocked={typeBlocked}
                      onToggle={props.onToggle}
                    />
                  );
                })}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

function MetricChip(props: {
  id: RuntimeMetricId;
  label: string;
  checked: boolean;
  busy: boolean;
  typeBlocked: boolean;
  onToggle: (id: RuntimeMetricId) => void;
}) {
  const blocked = props.typeBlocked && !props.checked;
  const disabled = props.busy || blocked;
  const reason = blocked ? THIRD_TYPE_BLOCK_REASON : undefined;
  return (
    <label
      className={
        blocked ? "trends-chip trends-chip-type-blocked" : "trends-chip"
      }
      title={reason}
    >
      <input
        type="checkbox"
        checked={props.checked}
        onChange={() => props.onToggle(props.id)}
        disabled={disabled}
        aria-disabled={disabled || undefined}
        aria-description={reason}
      />
      <span className="trends-chip-label">{props.label}</span>
    </label>
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
