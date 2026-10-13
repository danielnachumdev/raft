/** Typed client for serve `/api/firewall/*` (ordered edge rules). */

export type FirewallAction = "deny" | "permit" | "drop";

export type FirewallPort = number | "any";

export type FirewallRule = {
  id: string;
  cidr: string;
  port: FirewallPort;
  protocol: string;
  service: string;
  action: FirewallAction;
};

export type FirewallDocument = {
  version: number;
  source?: string;
  rules: FirewallRule[];
  applied?: boolean;
};

export type FirewallServiceOption = {
  name: string;
  label?: string;
  publicHost?: string;
};

export type FirewallRecommendation = {
  id: string;
  kind: string;
  title: string;
  summary: string;
  rule: FirewallRule;
  append?: boolean;
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

export async function fetchFirewall(): Promise<FirewallDocument> {
  return jsonRequest("/api/firewall", undefined, "firewall");
}

export async function putFirewall(
  body: Pick<FirewallDocument, "version" | "rules">,
): Promise<FirewallDocument> {
  return jsonRequest(
    "/api/firewall",
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ version: body.version, rules: body.rules }),
    },
    "save firewall",
  );
}

export async function exportFirewall(): Promise<FirewallDocument> {
  return jsonRequest("/api/firewall/export", undefined, "export firewall");
}

export async function importFirewall(
  body: unknown,
): Promise<FirewallDocument> {
  return jsonRequest(
    "/api/firewall/import",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    "import firewall",
  );
}

export async function fetchFirewallServices(): Promise<FirewallServiceOption[]> {
  const body = await jsonRequest<{ services: FirewallServiceOption[] }>(
    "/api/firewall/services",
    undefined,
    "firewall services",
  );
  return body.services;
}

export async function fetchFirewallRecommendations(): Promise<
  FirewallRecommendation[]
> {
  const body = await jsonRequest<{ recommendations: FirewallRecommendation[] }>(
    "/api/firewall/recommendations",
    undefined,
    "firewall recommendations",
  );
  return body.recommendations;
}

export async function dismissFirewallRecommendation(
  id: string,
): Promise<FirewallRecommendation[]> {
  const body = await jsonRequest<{ recommendations: FirewallRecommendation[] }>(
    `/api/firewall/recommendations/${encodeURIComponent(id)}/dismiss`,
    { method: "POST" },
    "dismiss recommendation",
  );
  return body.recommendations;
}

export function formatFirewallPort(port: FirewallPort): string {
  return port === "any" || port === 0 ? "any" : String(port);
}
