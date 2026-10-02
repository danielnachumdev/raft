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

export async function fetchStatus(): Promise<StatusPayload> {
  const res = await fetch("/api/status");
  if (!res.ok) {
    throw new Error(`status ${res.status}`);
  }
  return (await res.json()) as StatusPayload;
}
