import type { RuntimeMetricId } from "../../runtimeMetrics.ts";
import type { TrendsRangeState } from "../../range/types.ts";
import type { SeriesViewMode } from "../../panel/trendsView.ts";

export type GraphSize = "half" | "full";

/** One graph on a Trends dashboard; range is shared by the dashboard. */
export type TrendsGraphConfig = {
  id: string;
  /** Empty → derived from the metric labels at render time. */
  title: string;
  metricIds: RuntimeMetricId[];
  viewMode: SeriesViewMode;
  /** null = all; [] = none; string[] = explicit service or group ids. */
  selected: string[] | null;
  size: GraphSize;
};

/** Graph fields the editor owns (id is assigned by the store). */
export type TrendsGraphDraft = Omit<TrendsGraphConfig, "id">;

export type TrendsDashboard = {
  id: string;
  name: string;
  updatedAt: string;
  range: TrendsRangeState;
  panels: TrendsGraphConfig[];
};

export type TrendsDashboardStore = {
  version: 2;
  activeId: string;
  dashboards: TrendsDashboard[];
};

export const TRENDS_DASHBOARDS_STORAGE_KEY = "raft-serve-trends-dashboards";

export const DEFAULT_DASHBOARD_ID = "overview";
