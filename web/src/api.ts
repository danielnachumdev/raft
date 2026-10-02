export type StatusRow = {
  service: string;
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

export type ContainerDetail = {
  service: string;
  role: string;
  app: string | null;
  group: string | null;
  status: string;
  uptime_seconds: number | null;
  cpu_percent: number | null;
  memory: {
    used_bytes: number | null;
    limit_bytes: number | null;
    used_percent: number | null;
  };
  allocated: {
    cpus_limit: string;
    memory_limit: string;
    cpus_reservation: string;
    memory_reservation: string;
  };
  network: { rx_bytes: number | null; tx_bytes: number | null };
  block_io: { read_bytes: number | null; write_bytes: number | null };
  pids: number | null;
};

export type ServiceDetailPayload = {
  host: { hostname?: string; [key: string]: unknown };
  container: ContainerDetail;
  presentation: StatusRow;
};

const FALLBACK_TITLE = "raft serve";

export function documentTitleForHost(hostname: unknown): string {
  if (typeof hostname === "string" && hostname.trim()) {
    return `raft - ${hostname.trim()}`;
  }
  return FALLBACK_TITLE;
}

export function servicePath(service: string): string {
  return `/service/${encodeURIComponent(service)}`;
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

export async function fetchService(name: string): Promise<ServiceDetailPayload> {
  const res = await fetch(`/api/service/${encodeURIComponent(name)}`);
  if (res.status === 404) {
    throw new Error("not found");
  }
  if (!res.ok) {
    throw new Error(`service ${res.status}`);
  }
  return (await res.json()) as ServiceDetailPayload;
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
