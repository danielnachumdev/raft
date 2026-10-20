/** Typed client for serve ``/api/settings`` (full operator document). */

export const SECRET_MASK = "***" as const;

export type SettingsNote = {
  code: string;
  severity: "info" | "warn" | string;
  message: string;
};

export type SectionKind = "always" | "flag" | "derived";

export type SettingsSection = {
  key: string;
  title: string;
  kind: SectionKind;
  enabled: boolean;
  source: string;
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
    clientId: string | null;
    clientSecret: string | null;
    sessionTtlSeconds: number;
  };
  notifications: {
    enabled: boolean;
    channels: NotificationChannel[];
  };
  alerts: {
    enabled: boolean;
    intervalSeconds: number;
    timeoutSeconds: number;
  };
  dashboard: {
    enabled: boolean;
    port: number;
    publicHost: string | null;
    tls: string;
    auth: {
      mode: string;
      passwordHash: string | null;
      verifyUrl: string | null;
      signInUrl: string | null;
      identityHeader: string;
      oauth: {
        provider: string;
        redirectPath: string;
        allowlistFile: string;
        issuerUrl: string | null;
      };
    };
  };
};

export type SettingsPayload = {
  path: string;
  document: SettingsDocument;
  sections: SettingsSection[];
  notes: SettingsNote[];
  yaml?: string;
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

export async function fetchSettingsYaml(): Promise<SettingsPayload> {
  return jsonRequest<SettingsPayload>(
    "/api/settings/yaml",
    undefined,
    "settings yaml",
  );
}

export async function putSettingsYaml(yaml: string): Promise<SettingsPayload> {
  return jsonRequest<SettingsPayload>(
    "/api/settings/yaml",
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ yaml }),
    },
    "save settings yaml",
  );
}

export async function encodeSettingsYaml(
  document: SettingsDocument,
): Promise<{ yaml: string; document: SettingsDocument; sections: SettingsSection[] }> {
  return jsonRequest(
    "/api/settings/yaml/encode",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document }),
    },
    "encode settings yaml",
  );
}

export async function decodeSettingsYaml(
  yaml: string,
): Promise<{ document: SettingsDocument; sections: SettingsSection[] }> {
  return jsonRequest(
    "/api/settings/yaml/decode",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ yaml }),
    },
    "decode settings yaml",
  );
}
