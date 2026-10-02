export type StatusRow = {
  name: string;
  role: string;
  group: string;
  status: string;
  cpu: string;
  memory: string;
  uptime: string;
};

export type StatusPayload = {
  host: { hostname?: string; [key: string]: unknown };
  containers: unknown[];
  control_plane: StatusRow[];
  apps: StatusRow[];
};

const FALLBACK_TITLE = "raft serve";

export function documentTitleForHost(hostname: unknown): string {
  if (typeof hostname === "string" && hostname.trim()) {
    return `raft - ${hostname.trim()}`;
  }
  return FALLBACK_TITLE;
}

export type MetricsPoint = {
  t: string;
  cpu_percent: number | null;
  memory_used_percent: number | null;
  memory_used_bytes: number | null;
};

export type MetricsSeries = {
  id: string;
  label: string;
  kind: string;
  role: string;
  points: MetricsPoint[];
};

export type MetricsAvailable = {
  id: string;
  label: string;
  kind: string;
  role: string;
};

export type MetricsPayload = {
  window_seconds: number;
  from: string;
  to: string;
  cursor: string | null;
  available: MetricsAvailable[];
  series: MetricsSeries[];
};

/** Poll /api/metrics every N ms with ``since`` cursor (no WebSocket). */
export const METRICS_POLL_MS = 5000;

export async function fetchStatus(): Promise<StatusPayload> {
  const res = await fetch("/api/status");
  if (!res.ok) {
    throw new Error(`status ${res.status}`);
  }
  return (await res.json()) as StatusPayload;
}

export async function fetchMetrics(opts: {
  window: number;
  since?: string | null;
  services?: string[];
}): Promise<MetricsPayload> {
  const params = new URLSearchParams();
  params.set("window", String(opts.window));
  if (opts.since) {
    params.set("since", opts.since);
  }
  if (opts.services && opts.services.length > 0) {
    params.set("services", opts.services.join(","));
  }
  const res = await fetch(`/api/metrics?${params.toString()}`);
  if (!res.ok) {
    throw new Error(`metrics ${res.status}`);
  }
  return (await res.json()) as MetricsPayload;
}
