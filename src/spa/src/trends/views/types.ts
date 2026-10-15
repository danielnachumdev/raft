import type { RuntimeMetricId } from "../runtimeMetrics.ts";
import type { TrendsRangeState } from "../range/types.ts";
import type { SeriesViewMode } from "../panel/trendsView.ts";

/** #202 single-chart named view (legacy; migrated into dashboards). */
export type TrendsViewConfig = {
  metricIds: RuntimeMetricId[];
  viewMode: SeriesViewMode;
  /** null = all; [] = none; string[] = explicit service or group ids. */
  selected: string[] | null;
  range: TrendsRangeState;
};

export type NamedTrendsView = {
  id: string;
  name: string;
  updatedAt: string;
  config: TrendsViewConfig;
};

export type TrendsViewsStore = {
  version: 1;
  activeId: string | null;
  views: NamedTrendsView[];
};

export const TRENDS_VIEWS_STORAGE_KEY = "raft-serve-trends-views";

export const EMPTY_VIEWS_STORE: TrendsViewsStore = {
  version: 1,
  activeId: null,
  views: [],
};
