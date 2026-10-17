/** Typed client for serve `/api/firewall/*` (ordered edge rules). */

import {
  appResourceCache,
  CachedResourceProxy,
  resourceId,
} from "../shared/cache/index.ts";

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

const documentProxy = new CachedResourceProxy(
  appResourceCache,
  resourceId("firewall", "document"),
  { read: () => jsonRequest<FirewallDocument>("/api/firewall", undefined, "firewall") },
);

const servicesProxy = new CachedResourceProxy(
  appResourceCache,
  resourceId("firewall", "services"),
  {
    read: async () => {
      const body = await jsonRequest<{ services: FirewallServiceOption[] }>(
        "/api/firewall/services",
        undefined,
        "firewall services",
      );
      return body.services;
    },
  },
);

const recommendationsProxy = new CachedResourceProxy(
  appResourceCache,
  resourceId("firewall", "recommendations"),
  {
    read: async () => {
      const body = await jsonRequest<{ recommendations: FirewallRecommendation[] }>(
        "/api/firewall/recommendations",
        undefined,
        "firewall recommendations",
      );
      return body.recommendations;
    },
  },
);

export async function fetchFirewall(): Promise<FirewallDocument> {
  return documentProxy.read();
}

export async function putFirewall(
  body: Pick<FirewallDocument, "version" | "rules">,
): Promise<FirewallDocument> {
  const next = await documentProxy.write(() =>
    jsonRequest<FirewallDocument>(
      "/api/firewall",
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ version: body.version, rules: body.rules }),
      },
      "save firewall",
    ),
  );
  recommendationsProxy.invalidate();
  return next;
}

export async function exportFirewall(): Promise<FirewallDocument> {
  return jsonRequest("/api/firewall/export", undefined, "export firewall");
}

export async function importFirewall(
  body: unknown,
): Promise<FirewallDocument> {
  const next = await documentProxy.write(() =>
    jsonRequest<FirewallDocument>(
      "/api/firewall/import",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
      "import firewall",
    ),
  );
  recommendationsProxy.invalidate();
  return next;
}

export async function fetchFirewallServices(): Promise<FirewallServiceOption[]> {
  return servicesProxy.read();
}

export async function fetchFirewallRecommendations(): Promise<
  FirewallRecommendation[]
> {
  return recommendationsProxy.read();
}

export async function dismissFirewallRecommendation(
  id: string,
): Promise<FirewallRecommendation[]> {
  return recommendationsProxy.write(async () => {
    const body = await jsonRequest<{ recommendations: FirewallRecommendation[] }>(
      `/api/firewall/recommendations/${encodeURIComponent(id)}/dismiss`,
      { method: "POST" },
      "dismiss recommendation",
    );
    return body.recommendations;
  });
}

export type InspectionFirewallDraft = {
  cidr: string;
  rule: FirewallRule;
  matches: FirewallRule[];
  insert: "prepend";
};

export async function fetchInspectionFirewallDraft(opts: {
  clientIp: string;
  service?: string;
  action?: FirewallAction;
}): Promise<InspectionFirewallDraft> {
  const params = new URLSearchParams({ client_ip: opts.clientIp });
  if (opts.service) params.set("service", opts.service);
  if (opts.action) params.set("action", opts.action);
  return jsonRequest(
    `/api/firewall/from-inspection?${params}`,
    undefined,
    "firewall inspection draft",
  );
}

export async function applyInspectionFirewallRule(
  rule: FirewallRule,
): Promise<FirewallDocument> {
  const next = await documentProxy.write(() =>
    jsonRequest<FirewallDocument>(
      "/api/firewall/from-inspection",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rule }),
      },
      "apply inspection firewall rule",
    ),
  );
  recommendationsProxy.invalidate();
  return next;
}

export async function removeInspectionFirewallRule(opts: {
  clientIp: string;
  ruleId?: string;
}): Promise<FirewallDocument> {
  const next = await documentProxy.write(() =>
    jsonRequest<FirewallDocument>(
      "/api/firewall/from-inspection/remove",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_ip: opts.clientIp,
          rule_id: opts.ruleId ?? "",
        }),
      },
      "remove inspection firewall rule",
    ),
  );
  recommendationsProxy.invalidate();
  return next;
}

export function formatFirewallPort(port: FirewallPort): string {
  return port === "any" || port === 0 ? "any" : String(port);
}
