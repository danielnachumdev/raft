/** Typed client for serve ``GET /api/events`` (ops timeline). */

import { detailFromBody, readJsonBody } from "../shared/api/http.ts";

export type OpsEventRow = {
  id?: string;
  kind: string;
  ts: string;
  summary: string;
  service?: string;
  metadata?: Record<string, unknown>;
};

export type OpsEventsPayload = {
  from: string;
  to: string;
  hours: number;
  count: number;
  events: OpsEventRow[];
};

export type OpsEventsQuery = {
  hours?: number;
  service?: string;
  kind?: string;
  limit?: number;
};

async function jsonRequest<T>(url: string): Promise<T> {
  const res = await fetch(url);
  const body = await readJsonBody(res);
  if (!res.ok) {
    const detail = detailFromBody(body) || res.statusText || "request failed";
    throw new Error(detail);
  }
  return body as T;
}

export async function fetchOpsEvents(
  query: OpsEventsQuery = {},
): Promise<OpsEventsPayload> {
  const params = new URLSearchParams();
  if (query.hours != null) params.set("hours", String(query.hours));
  if (query.service) params.set("service", query.service);
  if (query.kind) params.set("kind", query.kind);
  if (query.limit != null) params.set("limit", String(query.limit));
  const qs = params.toString();
  const url = qs ? `/api/events?${qs}` : "/api/events";
  return jsonRequest<OpsEventsPayload>(url);
}
