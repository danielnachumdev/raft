import type { MetricsPoint } from "../shared/api.ts";
import {
  formatMetricValue,
  yAxisSuffix,
  type MetricTypeId,
} from "./metricTypes.ts";

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

export const RESOURCE_METRICS: RuntimeMetricDef[] = [
  { id: "cpu_percent", label: "CPU %", typeId: "percent", plane: "resources" },
  {
    id: "memory_used_percent",
    label: "Memory used %",
    typeId: "percent",
    plane: "resources",
  },
  {
    id: "memory_used_bytes",
    label: "Memory used bytes",
    typeId: "bytes",
    plane: "resources",
  },
  {
    id: "memory_limit_bytes",
    label: "Memory limit bytes",
    typeId: "bytes",
    plane: "resources",
  },
  {
    id: "uptime_seconds",
    label: "Uptime seconds",
    typeId: "uptime",
    plane: "resources",
  },
  { id: "pids", label: "PIDs", typeId: "count", plane: "resources" },
  {
    id: "network_rx_bytes",
    label: "Network RX",
    typeId: "bytes",
    plane: "resources",
  },
  {
    id: "network_tx_bytes",
    label: "Network TX",
    typeId: "bytes",
    plane: "resources",
  },
  {
    id: "block_read_bytes",
    label: "Block read",
    typeId: "bytes",
    plane: "resources",
  },
  {
    id: "block_write_bytes",
    label: "Block write",
    typeId: "bytes",
    plane: "resources",
  },
];

export const HTTP_METRICS: RuntimeMetricDef[] = [
  { id: "rps", label: "Requests / sec", typeId: "rate", plane: "http" },
  {
    id: "in_flight",
    label: "In-flight (Writing)",
    typeId: "count",
    plane: "http",
  },
  {
    id: "duration_avg_ms",
    label: "Latency avg (ms)",
    typeId: "duration",
    plane: "http",
  },
  {
    id: "duration_p50_ms",
    label: "Latency p50 (ms)",
    typeId: "duration",
    plane: "http",
  },
  {
    id: "duration_p95_ms",
    label: "Latency p95 (ms)",
    typeId: "duration",
    plane: "http",
  },
  {
    id: "duration_p99_ms",
    label: "Latency p99 (ms)",
    typeId: "duration",
    plane: "http",
  },
  { id: "status_2xx", label: "2xx count", typeId: "count", plane: "http" },
  { id: "status_3xx", label: "3xx count", typeId: "count", plane: "http" },
  { id: "status_4xx", label: "4xx count", typeId: "count", plane: "http" },
  { id: "status_5xx", label: "5xx count", typeId: "count", plane: "http" },
];

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
