/** Resource + HTTP edge metrics types and `/api/metrics*` clients. */

import { detailFromBody, readJsonBody } from "./http.ts";

export type MetricsPoint = {
  t: string;
  cpu_percent?: number | null;
  memory_used_percent?: number | null;
  memory_used_bytes?: number | null;
  memory_limit_bytes?: number | null;
  uptime_seconds?: number | null;
  pids?: number | null;
  network_rx_bytes?: number | null;
  network_tx_bytes?: number | null;
  block_read_bytes?: number | null;
  block_write_bytes?: number | null;
  rps?: number | null;
  in_flight?: number | null;
  active_connections?: number | null;
  requests?: number | null;
  duration_avg_ms?: number | null;
  duration_p50_ms?: number | null;
  duration_p95_ms?: number | null;
  duration_p99_ms?: number | null;
  status_2xx?: number | null;
  status_3xx?: number | null;
  status_4xx?: number | null;
  status_5xx?: number | null;
};

export type MetricsSeries = {
  id: string;
  label: string;
  kind: string;
  role: string;
  group?: string | null;
  points: MetricsPoint[];
};

export type MetricsAvailable = {
  id: string;
  label: string;
  kind: string;
  role: string;
  group?: string | null;
};

/** Chart annotation from ``host/events/graph.jsonl`` (lifecycle markers). */
export type GraphEvent = {
  kind: string;
  ts: string;
  service?: string | null;
  label?: string | null;
  metadata?: Record<string, unknown>;
  id?: string | null;
};

export type MetricsBounds = {
  retention_max_age_days: number;
  retention_max_bytes: number;
  available_from: string;
  earliest_ts: string | null;
  max_window_seconds: number;
};

export type MetricsPayload = {
  window_seconds: number;
  from: string;
  to: string;
  cursor: string | null;
  available: MetricsAvailable[];
  series: MetricsSeries[];
  /** Optional for older servers; treat missing as []. */
  events?: GraphEvent[];
  bounds?: MetricsBounds;
  clamped?: boolean;
  clamp_message?: string;
};

/** Poll /api/metrics every N ms with ``since`` cursor (no WebSocket). */
export const METRICS_POLL_MS = 5000;

export type MetricsQuery = {
  window: number;
  since?: string | null;
  start?: string;
  end?: string;
  services?: string[];
};

export async function fetchMetrics(opts: MetricsQuery): Promise<MetricsPayload> {
  return fetchMetricsPath("/api/metrics", opts);
}

/** HTTP edge request series (sibling of resource ``/api/metrics``). */
export async function fetchHttpMetrics(
  opts: MetricsQuery,
): Promise<MetricsPayload> {
  return fetchMetricsPath("/api/metrics/http", opts);
}

async function fetchMetricsPath(
  path: string,
  opts: MetricsQuery,
): Promise<MetricsPayload> {
  const params = new URLSearchParams();
  params.set("window", String(opts.window));
  if (opts.since) params.set("since", opts.since);
  if (opts.start) params.set("start", opts.start);
  if (opts.end) params.set("end", opts.end);
  if (opts.services && opts.services.length > 0) {
    params.set("services", opts.services.join(","));
  }
  const res = await fetch(`${path}?${params.toString()}`);
  const body = await readJsonBody(res);
  if (!res.ok) {
    throw new Error(detailFromBody(body) || `metrics ${res.status}`);
  }
  return body as MetricsPayload;
}
