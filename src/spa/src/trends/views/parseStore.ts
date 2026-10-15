import {
  isRuntimeMetricId,
  isSelected,
  isViewMode,
  parseRange,
} from "./validate.ts";
import {
  EMPTY_VIEWS_STORE,
  type NamedTrendsView,
  type TrendsViewConfig,
  type TrendsViewsStore,
} from "./types.ts";

export function parseStore(raw: unknown): TrendsViewsStore {
  if (!raw || typeof raw !== "object") return { ...EMPTY_VIEWS_STORE };
  const obj = raw as Record<string, unknown>;
  if (obj.version !== 1 || !Array.isArray(obj.views)) {
    return { ...EMPTY_VIEWS_STORE };
  }
  const views = obj.views
    .map(parseView)
    .filter((v): v is NamedTrendsView => v !== null);
  const activeId =
    typeof obj.activeId === "string" && views.some((v) => v.id === obj.activeId)
      ? obj.activeId
      : null;
  return { version: 1, activeId, views };
}

function parseView(raw: unknown): NamedTrendsView | null {
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;
  if (typeof obj.id !== "string" || !obj.id.trim()) return null;
  if (typeof obj.name !== "string" || !obj.name.trim()) return null;
  if (typeof obj.updatedAt !== "string") return null;
  const config = parseConfig(obj.config);
  if (!config) return null;
  return {
    id: obj.id,
    name: obj.name.trim(),
    updatedAt: obj.updatedAt,
    config,
  };
}

function parseConfig(raw: unknown): TrendsViewConfig | null {
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;
  if (!Array.isArray(obj.metricIds)) return null;
  const metricIds = obj.metricIds.filter(isRuntimeMetricId);
  if (!isViewMode(obj.viewMode)) return null;
  if (!isSelected(obj.selected)) return null;
  const range = parseRange(obj.range);
  if (!range) return null;
  return { metricIds, viewMode: obj.viewMode, selected: obj.selected, range };
}
