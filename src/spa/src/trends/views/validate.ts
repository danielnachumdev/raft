import { RUNTIME_METRICS, type RuntimeMetricId } from "../runtimeMetrics.ts";
import type { SeriesViewMode } from "../panel/trendsView.ts";
import type { TrendsRangeState } from "../range/types.ts";

const METRIC_IDS = new Set<string>(RUNTIME_METRICS.map((m) => m.id));

export function isRuntimeMetricId(v: unknown): v is RuntimeMetricId {
  return typeof v === "string" && METRIC_IDS.has(v);
}

export function isViewMode(v: unknown): v is SeriesViewMode {
  return (
    v === "per_service" ||
    v === "per_group" ||
    v === "avg_all" ||
    v === "avg_group"
  );
}

export function isSelected(v: unknown): v is string[] | null {
  if (v === null) return true;
  return Array.isArray(v) && v.every((x) => typeof x === "string");
}

export function parseRange(raw: unknown): TrendsRangeState | null {
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;
  if (obj.mode !== "preset" && obj.mode !== "custom" && obj.mode !== "absolute") {
    return null;
  }
  if (typeof obj.windowSec !== "number" || !Number.isFinite(obj.windowSec)) {
    return null;
  }
  if (typeof obj.customAmount !== "number") return null;
  if (
    obj.customUnit !== "minutes" &&
    obj.customUnit !== "hours" &&
    obj.customUnit !== "days"
  ) {
    return null;
  }
  if (typeof obj.startLocal !== "string" || typeof obj.endLocal !== "string") {
    return null;
  }
  return {
    mode: obj.mode,
    windowSec: obj.windowSec,
    customAmount: obj.customAmount,
    customUnit: obj.customUnit,
    startLocal: obj.startLocal,
    endLocal: obj.endLocal,
  };
}
