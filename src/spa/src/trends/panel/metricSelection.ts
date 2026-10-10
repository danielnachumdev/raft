import {
  RUNTIME_METRICS,
  type MetricPlane,
  type RuntimeMetricDef,
  type RuntimeMetricId,
} from "../runtimeMetrics.ts";

/** Default Trends metric selection: CPU % only. */
export const DEFAULT_METRIC_IDS: RuntimeMetricId[] = ["cpu_percent"];

export function metricsFromIds(ids: RuntimeMetricId[]): RuntimeMetricDef[] {
  const want = new Set(ids);
  return RUNTIME_METRICS.filter((m) => want.has(m.id));
}

/** Planes needed for the current metric checkboxes (stable order). */
export function planesForMetrics(metrics: RuntimeMetricDef[]): MetricPlane[] {
  const seen = new Set<MetricPlane>();
  const out: MetricPlane[] = [];
  for (const m of metrics) {
    if (seen.has(m.plane)) continue;
    seen.add(m.plane);
    out.push(m.plane);
  }
  return out;
}

/** Toggle a metric id; order follows ``RUNTIME_METRICS``. */
export function toggleMetricId(
  active: RuntimeMetricId[],
  id: RuntimeMetricId,
): RuntimeMetricId[] {
  const next = active.includes(id)
    ? active.filter((x) => x !== id)
    : [...active, id];
  const want = new Set(next);
  return RUNTIME_METRICS.map((m) => m.id).filter((x) => want.has(x));
}
