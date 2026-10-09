import type { MetricsPoint } from "../shared/api.ts";

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

export type RuntimeUnit = "percent" | "bytes" | "seconds" | "count" | "ms" | "rps";

export type MetricPlane = "resources" | "http";

export type RuntimeMetricDef = {
  id: RuntimeMetricId;
  label: string;
  unit: RuntimeUnit;
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
  { id: "cpu_percent", label: "CPU %", unit: "percent", plane: "resources" },
  {
    id: "memory_used_percent",
    label: "Memory used %",
    unit: "percent",
    plane: "resources",
  },
  {
    id: "memory_used_bytes",
    label: "Memory used bytes",
    unit: "bytes",
    plane: "resources",
  },
  {
    id: "memory_limit_bytes",
    label: "Memory limit bytes",
    unit: "bytes",
    plane: "resources",
  },
  {
    id: "uptime_seconds",
    label: "Uptime seconds",
    unit: "seconds",
    plane: "resources",
  },
  { id: "pids", label: "PIDs", unit: "count", plane: "resources" },
  {
    id: "network_rx_bytes",
    label: "Network RX",
    unit: "bytes",
    plane: "resources",
  },
  {
    id: "network_tx_bytes",
    label: "Network TX",
    unit: "bytes",
    plane: "resources",
  },
  {
    id: "block_read_bytes",
    label: "Block read",
    unit: "bytes",
    plane: "resources",
  },
  {
    id: "block_write_bytes",
    label: "Block write",
    unit: "bytes",
    plane: "resources",
  },
];

export const HTTP_METRICS: RuntimeMetricDef[] = [
  { id: "rps", label: "Requests / sec", unit: "rps", plane: "http" },
  {
    id: "in_flight",
    label: "In-flight (Writing)",
    unit: "count",
    plane: "http",
  },
  {
    id: "duration_avg_ms",
    label: "Latency avg (ms)",
    unit: "ms",
    plane: "http",
  },
  {
    id: "duration_p50_ms",
    label: "Latency p50 (ms)",
    unit: "ms",
    plane: "http",
  },
  {
    id: "duration_p95_ms",
    label: "Latency p95 (ms)",
    unit: "ms",
    plane: "http",
  },
  {
    id: "duration_p99_ms",
    label: "Latency p99 (ms)",
    unit: "ms",
    plane: "http",
  },
  { id: "status_2xx", label: "2xx count", unit: "count", plane: "http" },
  { id: "status_3xx", label: "3xx count", unit: "count", plane: "http" },
  { id: "status_4xx", label: "4xx count", unit: "count", plane: "http" },
  { id: "status_5xx", label: "5xx count", unit: "count", plane: "http" },
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

export function formatRuntimeValue(value: number, unit: RuntimeUnit): string {
  if (unit === "percent") return `${value.toFixed(1)}%`;
  if (unit === "bytes") return formatBytes(value);
  if (unit === "seconds") return formatSeconds(value);
  if (unit === "ms") return `${value.toFixed(1)} ms`;
  if (unit === "rps") return `${value.toFixed(2)}/s`;
  return String(Math.round(value));
}

export function yAxisUnit(unit: RuntimeUnit): string {
  if (unit === "percent") return "%";
  if (unit === "bytes") return "";
  if (unit === "seconds") return "s";
  if (unit === "ms") return "ms";
  if (unit === "rps") return "/s";
  return "";
}

function formatBytes(n: number): string {
  const abs = Math.abs(n);
  if (abs < 1024) return `${Math.round(n)} B`;
  if (abs < 1024 ** 2) return `${(n / 1024).toFixed(1)} KiB`;
  if (abs < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MiB`;
  return `${(n / 1024 ** 3).toFixed(2)} GiB`;
}

function formatSeconds(n: number): string {
  if (n < 60) return `${n.toFixed(0)}s`;
  if (n < 3600) return `${(n / 60).toFixed(1)}m`;
  return `${(n / 3600).toFixed(1)}h`;
}
