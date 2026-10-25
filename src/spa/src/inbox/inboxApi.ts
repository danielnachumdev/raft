/** Typed client for serve `/api/inbox/*` (in-app notices, not outbound channels). */

import { detailFromBody, readJsonBody } from "../shared/api/http.ts";

export type InboxItem = {
  id: string;
  source: string;
  sourceItemId: string;
  title: string;
  summary: string;
  severity: string;
  href: string;
  dismissible: boolean;
  unread: boolean;
};

export type InboxPayload = {
  items: InboxItem[];
  unreadCount: number;
  badge: string | null;
  badgeSemantics: string;
};

export type InboxSummary = {
  unreadCount: number;
  badge: string | null;
  badgeSemantics: string;
  totalCount: number;
};

async function jsonRequest<T>(
  url: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(url, init);
  const body = await readJsonBody(res);
  if (!res.ok) {
    const detail = detailFromBody(body) || res.statusText || "request failed";
    throw new Error(detail);
  }
  return body as T;
}

export async function fetchInbox(): Promise<InboxPayload> {
  return jsonRequest<InboxPayload>("/api/inbox");
}

export async function fetchInboxSummary(): Promise<InboxSummary> {
  return jsonRequest<InboxSummary>("/api/inbox/summary");
}

export async function markInboxItemRead(itemId: string): Promise<InboxPayload> {
  return jsonRequest<InboxPayload>(
    `/api/inbox/items/${encodeURIComponent(itemId)}/read`,
    { method: "POST" },
  );
}

export async function markInboxItemUnread(
  itemId: string,
): Promise<InboxPayload> {
  return jsonRequest<InboxPayload>(
    `/api/inbox/items/${encodeURIComponent(itemId)}/unread`,
    { method: "POST" },
  );
}

export async function markAllInboxRead(): Promise<InboxPayload> {
  return jsonRequest<InboxPayload>("/api/inbox/mark-all-read", {
    method: "POST",
  });
}

export async function dismissInboxItem(itemId: string): Promise<InboxPayload> {
  return jsonRequest<InboxPayload>(
    `/api/inbox/items/${encodeURIComponent(itemId)}/dismiss`,
    { method: "POST" },
  );
}
