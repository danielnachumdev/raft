export type StatusRow = {
  service: string;
  name: string;
  role: string;
  group: string;
  status: string;
  cpu: string;
  memory: string;
  started: string;
  uptime: string;
  external_urls: string[];
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

export function serviceLogsPath(service: string): string {
  return `${servicePath(service)}#logs`;
}

export type MetricsPoint = {
  t: string;
  cpu_percent: number | null;
  memory_used_percent: number | null;
  memory_used_bytes: number | null;
  memory_limit_bytes?: number | null;
  uptime_seconds?: number | null;
  pids?: number | null;
  network_rx_bytes?: number | null;
  network_tx_bytes?: number | null;
  block_read_bytes?: number | null;
  block_write_bytes?: number | null;
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

/** Chart annotation from ``state/events/graph.jsonl`` (lifecycle markers). */
export type GraphEvent = {
  kind: string;
  ts: string;
  service?: string | null;
  label?: string | null;
  metadata?: Record<string, unknown>;
  id?: string | null;
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
};

/** Poll /api/metrics every N ms with ``since`` cursor (no WebSocket). */
export const METRICS_POLL_MS = 5000;

/** Poll /api/status while the dashboard is mounted (pause when tab hidden). */
export const STATUS_POLL_MS = 30_000;

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

export type ServiceLogsPayload = {
  service: string;
  tail: number;
  text: string;
};

export const DEFAULT_LOG_TAIL = 100;

export function serviceLogsFollowUrl(
  name: string,
  tail: number = DEFAULT_LOG_TAIL,
): string {
  const params = new URLSearchParams();
  params.set("tail", String(tail));
  return `/api/service/${encodeURIComponent(name)}/logs/follow?${params.toString()}`;
}

export async function fetchServiceLogs(
  name: string,
  tail: number = DEFAULT_LOG_TAIL,
): Promise<ServiceLogsPayload> {
  const params = new URLSearchParams();
  params.set("tail", String(tail));
  const res = await fetch(
    `/api/service/${encodeURIComponent(name)}/logs?${params.toString()}`,
  );
  const body = await readJsonBody(res);
  if (!res.ok) {
    throw new Error(detailFromBody(body) || `logs failed (${res.status})`);
  }
  return body as ServiceLogsPayload;
}

/** Open SSE follow stream; resolves once the response is ready. */
export async function openServiceLogsFollow(
  name: string,
  tail: number,
  signal: AbortSignal,
): Promise<AsyncGenerator<string, void, void>> {
  const res = await fetch(serviceLogsFollowUrl(name, tail), { signal });
  if (!res.ok) {
    const body = await readJsonBody(res);
    throw new Error(detailFromBody(body) || `logs follow failed (${res.status})`);
  }
  if (!res.body) {
    throw new Error("logs follow failed (empty body)");
  }
  return readSseDataLines(res.body, signal);
}

async function* readSseDataLines(
  body: ReadableStream<Uint8Array>,
  signal: AbortSignal,
): AsyncGenerator<string, void, void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (!signal.aborted) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";
      for (const chunk of parts) {
        const line = sseDataPayload(chunk);
        if (line !== null) yield line;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

function sseDataPayload(chunk: string): string | null {
  const lines = chunk.split("\n");
  const data: string[] = [];
  for (const line of lines) {
    if (line.startsWith("data:")) {
      data.push(line.slice(5).replace(/^ /, ""));
    }
  }
  if (data.length === 0) return null;
  return data.join("\n");
}

export type ServiceAction = "start" | "stop" | "redeploy";

export type ServiceActionResult = {
  ok: boolean;
  action: ServiceAction;
  service: string;
};

export async function postServiceAction(
  name: string,
  action: ServiceAction,
): Promise<ServiceActionResult> {
  const res = await fetch(
    `/api/service/${encodeURIComponent(name)}/${action}`,
    { method: "POST" },
  );
  const body = await readJsonBody(res);
  if (!res.ok) {
    throw new Error(detailFromBody(body) || `${action} failed (${res.status})`);
  }
  return body as ServiceActionResult;
}

async function readJsonBody(res: Response): Promise<unknown> {
  try {
    return await res.json();
  } catch {
    return null;
  }
}

function detailFromBody(body: unknown): string | null {
  if (!body || typeof body !== "object") return null;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string" && detail.trim()) return detail.trim();
  return null;
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
