import type { RuntimeMetricDef } from "../runtimeMetrics.ts";

/** HTTP edge series for Trends (gate access_log / stub_status plane). */
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
