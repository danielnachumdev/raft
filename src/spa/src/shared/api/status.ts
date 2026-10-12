/** Status snapshot types + `/api/status` client. */

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
  /** Compose service ids from App ``spec.dependsOn`` (empty when none). */
  depends_on?: string[];
};

export type RegistryIssue = {
  file: string;
  error: string;
};

export type StatusPayload = {
  host: { hostname?: string; [key: string]: unknown };
  containers: unknown[];
  control_plane: StatusRow[];
  apps: StatusRow[];
  /** Applied manifests under state/apps that failed to parse (others still load). */
  registry_issues?: RegistryIssue[];
};

/** Dashboard status poll while the tab is visible (tight bound for out-of-band apply). */
export const STATUS_POLL_MS = 2000;

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

export async function fetchStatus(): Promise<StatusPayload> {
  const res = await fetch("/api/status");
  if (!res.ok) {
    throw new Error(`status ${res.status}`);
  }
  return (await res.json()) as StatusPayload;
}
