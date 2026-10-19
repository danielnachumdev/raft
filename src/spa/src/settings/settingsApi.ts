/** Typed client for serve ``/api/settings`` (full operator document). */

export const SECRET_MASK = "***" as const;

export type SettingsNote = {
  code: string;
  severity: "info" | "warn" | string;
  message: string;
};

export type EdgeStream = {
  name: string;
  port: number;
  protocol: string;
};

export type NotificationChannel = {
  id: string;
  type: string;
  enabled: boolean;
  settings: Record<string, unknown>;
};

/** CamelCase settings.yaml shape returned by GET/PUT ``/api/settings``. */
export type SettingsDocument = {
  logging: {
    dir: string;
    file: string;
    level: string;
    retentionMaxAgeDays: number;
    retentionMaxBytes: number;
  };
  edge: {
    http: number | null;
    https: number | null;
    streams: EdgeStream[];
  };
  healing: {
    enabled: boolean;
    intervalSeconds: number;
    timeoutSeconds: number;
    failThreshold: number;
    cooldownSeconds: number;
    maxRestarts: number;
    escalateAfterRestarts: number;
  };
  metrics: {
    intervalSeconds: number;
    timeoutSeconds: number;
    batchSize: number;
    flushSeconds: number;
    retentionMaxAgeDays: number;
    retentionMaxBytes: number;
  };
  serviceLogs: {
    enabled: boolean;
    intervalSeconds: number;
    timeoutSeconds: number;
    retentionMaxAgeDays: number;
    retentionMaxBytes: number;
    includeEdge: boolean;
  };
  acme: {
    email: string | null;
    directory: string;
    renewDaysBeforeExpiry: number;
    challenge: string;
  };
  github: {
    mock: boolean;
    clientId: string | null;
    clientSecret: string | null;
    sessionTtlSeconds: number;
  };
  notifications: {
    enabled: boolean;
    channels: NotificationChannel[];
  };
  /** Legacy ``acl.gate`` — API round-trip only; not editable in Settings UI. */
  acl: {
    gate: {
      mode: string;
      entries: Array<{ id: string; cidr: string; comment?: string }>;
    };
  };
  alerts: {
    enabled: boolean;
    intervalSeconds: number;
    timeoutSeconds: number;
  };
};

export type SettingsPayload = {
  path: string;
  document: SettingsDocument;
  notes: SettingsNote[];
};

async function readJson(res: Response): Promise<unknown> {
  try {
    return await res.json();
  } catch {
    return null;
  }
}

function detailOf(body: unknown): string | null {
  if (!body || typeof body !== "object") return null;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string" && detail.trim()) return detail.trim();
  return null;
}

async function jsonRequest<T>(
  url: string,
  init?: RequestInit,
  label = "request",
): Promise<T> {
  const res = await fetch(url, init);
  const body = await readJson(res);
  if (!res.ok) {
    throw new Error(detailOf(body) || `${label} ${res.status}`);
  }
  return body as T;
}

export async function fetchSettings(): Promise<SettingsPayload> {
  return jsonRequest<SettingsPayload>("/api/settings", undefined, "settings");
}

export async function putSettings(
  document: SettingsDocument,
): Promise<SettingsPayload> {
  return jsonRequest<SettingsPayload>(
    "/api/settings",
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document }),
    },
    "save settings",
  );
}
