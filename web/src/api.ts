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
  host: Record<string, unknown>;
  containers: unknown[];
  control_plane: StatusRow[];
  apps: StatusRow[];
};

export async function fetchStatus(): Promise<StatusPayload> {
  const res = await fetch("/api/status");
  if (!res.ok) {
    throw new Error(`status ${res.status}`);
  }
  return (await res.json()) as StatusPayload;
}
