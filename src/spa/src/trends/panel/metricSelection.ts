import { METRIC_TYPES, type MetricTypeDef } from "../metricTypes.ts";
import {
  HTTP_METRICS,
  RESOURCE_METRICS,
  RUNTIME_METRICS,
  type MetricPlane,
  type RuntimeMetricDef,
  type RuntimeMetricId,
} from "../runtimeMetrics.ts";

/** Default Trends metric selection: CPU % only. */
export const DEFAULT_METRIC_IDS: RuntimeMetricId[] = ["cpu_percent"];

export type MetricFilterSection = {
  plane: MetricPlane;
  planeLabel: string;
  types: { type: MetricTypeDef; metrics: RuntimeMetricDef[] }[];
};

const PLANE_LABEL: Record<MetricPlane, string> = {
  resources: "Resources",
  http: "HTTP",
};

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

/** Sidebar sections: plane → type headings → metrics (registry order). */
export function metricFilterSections(): MetricFilterSection[] {
  return (["resources", "http"] as MetricPlane[]).map((plane) => ({
    plane,
    planeLabel: PLANE_LABEL[plane],
    types: typesForPlane(plane),
  }));
}

function typesForPlane(
  plane: MetricPlane,
): { type: MetricTypeDef; metrics: RuntimeMetricDef[] }[] {
  const pool = plane === "resources" ? RESOURCE_METRICS : HTTP_METRICS;
  const out: { type: MetricTypeDef; metrics: RuntimeMetricDef[] }[] = [];
  for (const type of METRIC_TYPES) {
    const metrics = pool.filter((m) => m.typeId === type.id);
    if (metrics.length) out.push({ type, metrics });
  }
  return out;
}
