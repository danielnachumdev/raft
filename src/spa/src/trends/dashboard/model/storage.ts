import { loadTrendsViewsStore } from "../../views/storage.ts";
import { defaultDashboard } from "./defaults.ts";
import { migrateLegacyViews } from "./migrate.ts";
import { parseDashboardStore } from "./parse.ts";
import {
  TRENDS_DASHBOARDS_STORAGE_KEY,
  type TrendsDashboardStore,
} from "./types.ts";

/** Fresh store holding only the default Overview dashboard. */
export function defaultDashboardStore(
  nowMs: number = Date.now(),
): TrendsDashboardStore {
  const overview = defaultDashboard(nowMs);
  return { version: 2, activeId: overview.id, dashboards: [overview] };
}

/**
 * Load dashboards from localStorage. A missing key migrates #202 named
 * views; a corrupt payload falls back to defaults (never throws).
 */
export function loadDashboardStore(): TrendsDashboardStore {
  try {
    if (typeof localStorage === "undefined") return defaultDashboardStore();
    const raw = localStorage.getItem(TRENDS_DASHBOARDS_STORAGE_KEY);
    if (raw === null) return migrateLegacyViews(loadTrendsViewsStore());
    return parseDashboardStore(JSON.parse(raw)) ?? defaultDashboardStore();
  } catch {
    return defaultDashboardStore();
  }
}

/** Persist store; ignores quota / private-mode failures. */
export function saveDashboardStore(store: TrendsDashboardStore): void {
  try {
    if (typeof localStorage === "undefined") return;
    localStorage.setItem(TRENDS_DASHBOARDS_STORAGE_KEY, JSON.stringify(store));
  } catch {
    /* ignore */
  }
}

export function newId(prefix: string, nowMs: number = Date.now()): string {
  const rand = Math.random().toString(36).slice(2, 8);
  return `${prefix}-${nowMs.toString(36)}-${rand}`;
}
