import { toggleMetricId } from "../../panel/metricSelection.ts";
import type { SeriesViewMode } from "../../panel/trendsView.ts";
import { parseRange } from "../../range/validate.ts";
import {
  RUNTIME_METRICS,
  type RuntimeMetricId,
} from "../../runtimeMetrics.ts";
import type {
  TrendsDashboard,
  TrendsDashboardStore,
  TrendsGraphConfig,
} from "./types.ts";

const METRIC_IDS = new Set<string>(RUNTIME_METRICS.map((m) => m.id));

function isRuntimeMetricId(v: unknown): v is RuntimeMetricId {
  return typeof v === "string" && METRIC_IDS.has(v);
}

function isViewMode(v: unknown): v is SeriesViewMode {
  return (
    v === "per_service" ||
    v === "per_group" ||
    v === "avg_all" ||
    v === "avg_group"
  );
}

function isSelected(v: unknown): v is string[] | null {
  if (v === null) return true;
  return Array.isArray(v) && v.every((x) => typeof x === "string");
}

/** Validate a stored v2 payload; null when it is not a usable store. */
export function parseDashboardStore(raw: unknown): TrendsDashboardStore | null {
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;
  if (obj.version !== 2 || !Array.isArray(obj.dashboards)) return null;
  const dashboards = uniqueById(
    obj.dashboards
      .map(parseDashboard)
      .filter((d): d is TrendsDashboard => d !== null),
  );
  if (dashboards.length === 0) return null;
  const activeId =
    typeof obj.activeId === "string" &&
    dashboards.some((d) => d.id === obj.activeId)
      ? obj.activeId
      : dashboards[0].id;
  return { version: 2, activeId, dashboards };
}

function parseDashboard(raw: unknown): TrendsDashboard | null {
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;
  if (!nonEmpty(obj.id) || !nonEmpty(obj.name)) return null;
  if (typeof obj.updatedAt !== "string" || !Array.isArray(obj.panels)) {
    return null;
  }
  const range = parseRange(obj.range);
  if (!range) return null;
  const panels = uniqueById(
    obj.panels
      .map(parseGraph)
      .filter((p): p is TrendsGraphConfig => p !== null),
  );
  return { id: obj.id, name: obj.name.trim(), updatedAt: obj.updatedAt, range, panels };
}

export function parseGraph(raw: unknown): TrendsGraphConfig | null {
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;
  if (!nonEmpty(obj.id) || typeof obj.title !== "string") return null;
  if (!Array.isArray(obj.metricIds)) return null;
  if (!isViewMode(obj.viewMode) || !isSelected(obj.selected)) return null;
  if (obj.size !== "half" && obj.size !== "full") return null;
  return {
    id: obj.id,
    title: obj.title.trim(),
    metricIds: capMetricTypes(obj.metricIds.filter(isRuntimeMetricId)),
    viewMode: obj.viewMode,
    selected: obj.selected,
    size: obj.size,
  };
}

/** Re-apply the dual-axis rule so hand-edited storage cannot plot 3 types. */
export function capMetricTypes(ids: RuntimeMetricId[]): RuntimeMetricId[] {
  return ids.reduce<RuntimeMetricId[]>(
    (acc, id) => (acc.includes(id) ? acc : toggleMetricId(acc, id)),
    [],
  );
}

function nonEmpty(v: unknown): v is string {
  return typeof v === "string" && v.trim().length > 0;
}

function uniqueById<T extends { id: string }>(items: T[]): T[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    if (seen.has(item.id)) return false;
    seen.add(item.id);
    return true;
  });
}
