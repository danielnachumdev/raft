import type { MetricsPoint } from "../shared/api.ts";
import {
  formatMetricValue,
  yAxisSuffix,
  type MetricTypeId,
} from "./metricTypes.ts";
import { HTTP_METRICS } from "./strategies/httpMetrics.ts";
import { RESOURCE_METRICS } from "./strategies/resourceMetrics.ts";

/** Graphable Runtime / HTTP fields from metrics series points. */
export type RuntimeMetricId =
  | "cpu_percent"
  | "memory_used_percent"
  | "memory_used_bytes"
  | "memory_limit_bytes"
  | "uptime_seconds"
  | "pids"
  | "network_rx_bytes"
  | "network_tx_bytes"
  | "block_read_bytes"
  | "block_write_bytes"
  | "rps"
  | "in_flight"
  | "duration_avg_ms"
  | "duration_p50_ms"
  | "duration_p95_ms"
  | "duration_p99_ms"
  | "status_2xx"
  | "status_3xx"
  | "status_4xx"
  | "status_5xx";

export type MetricPlane = "resources" | "http";

export type RuntimeMetricDef = {
  id: RuntimeMetricId;
  label: string;
  typeId: MetricTypeId;
  plane: MetricPlane;
};

/** Same window choices as the global Trends panel. */
export const RUNTIME_WINDOWS: { seconds: number; label: string }[] = [
  { seconds: 900, label: "15m" },
  { seconds: 3600, label: "1h" },
  { seconds: 21600, label: "6h" },
  { seconds: 86400, label: "24h" },
  { seconds: 604800, label: "7d" },
];

export const DEFAULT_RUNTIME_WINDOW = 3600;

export { RESOURCE_METRICS, HTTP_METRICS };

export const RUNTIME_METRICS: RuntimeMetricDef[] = [
  ...RESOURCE_METRICS,
  ...HTTP_METRICS,
];

export function runtimePointValue(
  point: MetricsPoint,
  id: RuntimeMetricId,
): number | null {
  const raw: unknown = point[id];
  if (typeof raw === "number" && Number.isFinite(raw)) return raw;
  if (typeof raw === "string" && raw.trim()) {
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

export function formatRuntimeValue(
  value: number,
  typeId: MetricTypeId,
): string {
  return formatMetricValue(value, typeId);
}

export function yAxisUnit(typeId: MetricTypeId): string {
  return yAxisSuffix(typeId);
}
