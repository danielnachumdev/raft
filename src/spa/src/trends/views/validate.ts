import { RUNTIME_METRICS, type RuntimeMetricId } from "../runtimeMetrics.ts";

const METRIC_IDS = new Set<string>(RUNTIME_METRICS.map((m) => m.id));

export function isRuntimeMetricId(v: unknown): v is RuntimeMetricId {
  return typeof v === "string" && METRIC_IDS.has(v);
}
