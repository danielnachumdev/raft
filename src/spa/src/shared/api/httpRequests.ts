/** Per-request HTTP inspection for Host-routed Apps. */

export const HTTP_REQUESTS_POLL_MS = 3000;
export const DEFAULT_HTTP_REQUESTS_LIMIT = 100;

export type HttpRequestRow = {
  ts: string | null;
  method: string | null;
  path: string | null;
  status: number;
  duration_ms: number;
  client_ip: string | null;
  host: string;
  user_agent: string | null;
  enriched: boolean;
};

export type HttpRequestsPayload = {
  service: string;
  eligible: boolean;
  reason: string | null;
  scaled_to_zero: boolean;
  limit: number;
  unknown?: boolean;
  privacy: {
    query_strings: string;
    cookies_authorization_bodies: string;
    path_max: number;
    user_agent_max: number;
  };
  requests: HttpRequestRow[];
};

export async function fetchServiceHttpRequests(
  name: string,
  limit: number = DEFAULT_HTTP_REQUESTS_LIMIT,
): Promise<HttpRequestsPayload> {
  const qs = new URLSearchParams({ limit: String(limit) });
  const res = await fetch(
    `/api/service/${encodeURIComponent(name)}/http-requests?${qs}`,
  );
  if (res.status === 404) {
    throw new Error("not found");
  }
  if (!res.ok) {
    throw new Error(`http-requests ${res.status}`);
  }
  return (await res.json()) as HttpRequestsPayload;
}
