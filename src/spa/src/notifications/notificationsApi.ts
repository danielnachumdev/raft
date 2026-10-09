/** Typed client for serve `/api/notifications/*` (channel CRUD + strategy catalog). */

export const SECRET_MASK = "***" as const;

export type NotificationStrategyInfo = {
  type_id: string;
};

export type NotificationStrategiesPayload = {
  strategies: NotificationStrategyInfo[];
};

export type NotificationChannelSettings = Record<string, unknown>;

export type NotificationChannel = {
  id: string;
  type: string;
  enabled: boolean;
  settings: NotificationChannelSettings;
};

export type NotificationChannelsPayload = {
  enabled: boolean;
  channels: NotificationChannel[];
};

export type NotificationChannelCreateBody = {
  id: string;
  type: string;
  enabled?: boolean;
  settings?: NotificationChannelSettings;
};

export type NotificationChannelUpdateBody = {
  type?: string;
  enabled?: boolean;
  settings?: NotificationChannelSettings;
  id?: string;
};

export type NotificationChannelDeleteResult = {
  ok: true;
  deleted: string;
};

/** Server has no send-test route yet; keep UI disabled until one lands. */
export const SEND_TEST_API_AVAILABLE = false;

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

export async function fetchNotificationStrategies(): Promise<NotificationStrategiesPayload> {
  return jsonRequest(
    "/api/notifications/strategies",
    undefined,
    "strategies",
  );
}

export async function fetchNotificationChannels(): Promise<NotificationChannelsPayload> {
  return jsonRequest("/api/notifications/channels", undefined, "channels");
}

export async function createNotificationChannel(
  body: NotificationChannelCreateBody,
): Promise<NotificationChannel> {
  return jsonRequest(
    "/api/notifications/channels",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    "create channel",
  );
}

export async function updateNotificationChannel(
  id: string,
  body: NotificationChannelUpdateBody,
): Promise<NotificationChannel> {
  return jsonRequest(
    `/api/notifications/channels/${encodeURIComponent(id)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    "update channel",
  );
}

export async function deleteNotificationChannel(
  id: string,
): Promise<NotificationChannelDeleteResult> {
  return jsonRequest(
    `/api/notifications/channels/${encodeURIComponent(id)}`,
    { method: "DELETE" },
    "delete channel",
  );
}
