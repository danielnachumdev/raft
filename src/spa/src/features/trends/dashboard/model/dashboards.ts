import { defaultRangeState } from "../../range/index.ts";
import { defaultDashboard } from "./defaults.ts";
import type { TrendsDashboard, TrendsDashboardStore } from "./types.ts";

/** Pure store-level reducers (which dashboards exist + which is open). */

export function activeDashboard(store: TrendsDashboardStore): TrendsDashboard {
  return (
    store.dashboards.find((d) => d.id === store.activeId) ?? store.dashboards[0]
  );
}

export function updateActive(
  store: TrendsDashboardStore,
  fn: (d: TrendsDashboard) => TrendsDashboard,
): TrendsDashboardStore {
  const current = activeDashboard(store);
  return {
    ...store,
    activeId: current.id,
    dashboards: store.dashboards.map((d) => (d.id === current.id ? fn(d) : d)),
  };
}

export function setActiveDashboard(
  store: TrendsDashboardStore,
  id: string,
): TrendsDashboardStore {
  if (!store.dashboards.some((d) => d.id === id)) return store;
  return { ...store, activeId: id };
}

/** New empty dashboard (shares the active range) and open it. */
export function createDashboard(
  store: TrendsDashboardStore,
  name: string,
  id: string,
): TrendsDashboardStore {
  const trimmed = name.trim();
  if (!trimmed || store.dashboards.some((d) => d.id === id)) return store;
  const range = store.dashboards.length
    ? { ...activeDashboard(store).range }
    : defaultRangeState();
  const created: TrendsDashboard = {
    id,
    name: trimmed,
    updatedAt: new Date().toISOString(),
    range,
    panels: [],
  };
  return { ...store, activeId: id, dashboards: [...store.dashboards, created] };
}

export function renameDashboard(
  store: TrendsDashboardStore,
  id: string,
  name: string,
): TrendsDashboardStore {
  const trimmed = name.trim();
  if (!trimmed) return store;
  return {
    ...store,
    dashboards: store.dashboards.map((d) =>
      d.id === id
        ? { ...d, name: trimmed, updatedAt: new Date().toISOString() }
        : d,
    ),
  };
}

/** Delete; the last dashboard is replaced by a fresh Overview. */
export function deleteDashboard(
  store: TrendsDashboardStore,
  id: string,
): TrendsDashboardStore {
  const idx = store.dashboards.findIndex((d) => d.id === id);
  if (idx < 0) return store;
  const rest = store.dashboards.filter((d) => d.id !== id);
  if (rest.length === 0) {
    const overview = defaultDashboard();
    return { version: 2, activeId: overview.id, dashboards: [overview] };
  }
  const activeId =
    store.activeId === id ? rest[Math.max(0, idx - 1)].id : store.activeId;
  return { ...store, activeId, dashboards: rest };
}

export function suggestDashboardName(store: TrendsDashboardStore): string {
  const names = new Set(store.dashboards.map((d) => d.name));
  let n = store.dashboards.length + 1;
  while (names.has(`Dashboard ${n}`)) n += 1;
  return `Dashboard ${n}`;
}
