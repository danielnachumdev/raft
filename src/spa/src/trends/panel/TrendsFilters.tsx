import type { MetricsAvailable, MetricsBounds } from "../../shared/api/index.ts";
import type { RuntimeMetricId } from "../runtimeMetrics";
import type { TrendsRangeState } from "../range/index.ts";
import { TrendsRangeControls } from "../TrendsRangeControls";
import {
  TrendsViewsBar,
  type TrendsNamedViewsApi,
} from "../views/index.ts";
import { IdFilter } from "./IdFilter";
import { MetricFilter } from "./MetricFilter";
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
  namedViews: TrendsNamedViewsApi;
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
      <TrendsViewsBar
        store={props.namedViews.store}
        staleMessage={props.namedViews.staleMessage}
        onSelect={props.namedViews.onSelect}
        onSave={props.namedViews.onSave}
        onUpdate={props.namedViews.onUpdate}
        onRename={props.namedViews.onRename}
        onDelete={props.namedViews.onDelete}
      />
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
