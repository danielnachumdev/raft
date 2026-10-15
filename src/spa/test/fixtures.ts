/** Module-level SPA test fixtures (dummy data only — no live operator inventory). */

import type {
  MetricsAvailable,
  MetricsBounds,
  MetricsSeries,
} from "../src/shared/api/index.ts";

export function metricsPoint(
  t: string,
  cpu: number | null,
  mem: number | null = null,
) {
  return {
    t,
    cpu_percent: cpu,
    memory_used_percent: mem,
    memory_used_bytes: null,
  };
}

export function metricsSeries(
  id: string,
  group: string | null,
  points: { t: string; cpu: number | null; mem?: number | null }[],
): MetricsSeries {
  return {
    id,
    label: id,
    kind: "container",
    role: "app",
    group,
    points: points.map((p) => metricsPoint(p.t, p.cpu, p.mem ?? null)),
  };
}

export function metricsAvailable(
  id: string,
  group: string | null = null,
  kind = "container",
): MetricsAvailable {
  return { id, label: id, kind, role: kind === "host" ? "host" : "app", group };
}

export function metricsBounds(overrides: Partial<MetricsBounds> = {}): MetricsBounds {
  return {
    retention_max_age_days: 2,
    retention_max_bytes: 100,
    available_from: "2026-10-04T12:00:00.000Z",
    earliest_ts: "2026-10-04T12:00:00.000Z",
    max_window_seconds: 2 * 86400,
    ...overrides,
  };
}
