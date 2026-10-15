import type { NamedTrendsView, TrendsViewsStore } from "../../views/types.ts";
import { capMetricTypes } from "./parse.ts";
import { defaultDashboard } from "./defaults.ts";
import type { TrendsDashboard, TrendsDashboardStore } from "./types.ts";

/**
 * Build the first v2 store: Overview defaults, then one dashboard per #202
 * named view (its own range + a single full-width graph), so nothing saved
 * before dashboards is lost. The last active named view stays active.
 */
export function migrateLegacyViews(
  legacy: TrendsViewsStore,
  nowMs: number = Date.now(),
): TrendsDashboardStore {
  const overview = defaultDashboard(nowMs);
  const migrated = legacy.views
    .filter((v) => v.id !== overview.id)
    .map(viewToDashboard);
  const activeId = migrated.some((d) => d.id === legacy.activeId)
    ? (legacy.activeId as string)
    : overview.id;
  return { version: 2, activeId, dashboards: [overview, ...migrated] };
}

function viewToDashboard(view: NamedTrendsView): TrendsDashboard {
  const c = view.config;
  return {
    id: view.id,
    name: view.name,
    updatedAt: view.updatedAt,
    range: { ...c.range },
    panels: [
      {
        id: `${view.id}-graph`,
        title: "",
        metricIds: capMetricTypes(c.metricIds),
        viewMode: c.viewMode,
        selected: c.selected === null ? null : [...c.selected],
        size: "full",
      },
    ],
  };
}
