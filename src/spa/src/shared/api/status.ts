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

/** Installed raft package version from serve ``GET /api/status``. */
export type RaftVersion = {
  /** Packaging semver (e.g. ``0.11.0``). */
  package: string;
  /** Operator line matching ``raft --version`` (e.g. ``raft 0.11.0 (editable …)``). */
  line: string;
  /** Short chrome label: semver for wheels, ``rev@sha`` for git installs. */
  label?: string;
};

/** Top-bar version text (prefer server ``label``, else packaging semver). */
export function versionChromeText(version: RaftVersion): string {
  const label = version.label?.trim();
  if (label) {
    return label;
  }
  return version.package;
}

export type StatusPayload = {
  host: { hostname?: string; [key: string]: unknown };
  containers: unknown[];
  control_plane: StatusRow[];
  apps: StatusRow[];
  /** Applied manifests under services/ that failed to parse (others still load). */
  registry_issues?: RegistryIssue[];
  /** Running raft install; omit only on stale cached payloads. */
  version?: RaftVersion;
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
