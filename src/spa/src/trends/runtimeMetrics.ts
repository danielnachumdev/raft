import type { MetricsPoint } from "../shared/api.ts";

/** Graphable Runtime fields from the service detail page / metrics series. */
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
  | "block_write_bytes";

export type RuntimeUnit = "percent" | "bytes" | "seconds" | "count";

export type RuntimeMetricDef = {
  id: RuntimeMetricId;
  label: string;
  unit: RuntimeUnit;
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

export const RUNTIME_METRICS: RuntimeMetricDef[] = [
  { id: "cpu_percent", label: "CPU %", unit: "percent" },
  { id: "memory_used_percent", label: "Memory used %", unit: "percent" },
  { id: "memory_used_bytes", label: "Memory used bytes", unit: "bytes" },
  { id: "memory_limit_bytes", label: "Memory limit bytes", unit: "bytes" },
  { id: "uptime_seconds", label: "Uptime seconds", unit: "seconds" },
  { id: "pids", label: "PIDs", unit: "count" },
  { id: "network_rx_bytes", label: "Network RX", unit: "bytes" },
  { id: "network_tx_bytes", label: "Network TX", unit: "bytes" },
  { id: "block_read_bytes", label: "Block read", unit: "bytes" },
  { id: "block_write_bytes", label: "Block write", unit: "bytes" },
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
  return String(Math.round(value));
}

export function yAxisUnit(unit: RuntimeUnit): string {
  if (unit === "percent") return "%";
  if (unit === "bytes") return "";
  if (unit === "seconds") return "s";
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
