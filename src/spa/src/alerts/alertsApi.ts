/** Typed client for serve `/api/alerts/*`. */

import {
  appResourceCache,
  CachedResourceProxy,
  resourceId,
} from "../shared/cache/index.ts";
import type { AlertCatalogPayload, AlertRule } from "./alertsHelpers.ts";

export type AlertRulesPayload = { version: number; rules: AlertRule[] };

export type AlertStatusPayload = {
  enabled: boolean;
  intervalSeconds: number;
  notificationsEnabled: boolean;
  stale: boolean;
  lastEvaluation: Record<string, unknown> | null;
  documentError: string | null;
  rules: Record<
    string,
    {
      state: string;
      firingCount: number;
      pendingCount: number;
      suppressedCount: number;
      error: string | null;
    }
  >;
  instances: Array<{
    fingerprint: string;
    ruleId: string;
    ruleName: string;
    severity: string;
    subject: string;
    state: string;
    suppressed: boolean;
    since: string | null;
    lastValues: unknown[];
  }>;
};

export type AlertDryRunReport = {
  ruleId: string;
  evaluatedAt: string;
  error: string | null;
  subjects: Array<{
    subject: string;
    matched: boolean | null;
    currentState: string;
    wouldState: string;
    wouldNotify: string | null;
    leaves: Array<Record<string, unknown>>;
  }>;
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
): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  const body = await readJson(res);
  if (!res.ok) {
    throw new Error(detailOf(body) || `alerts ${res.status}`);
  }
  return body as T;
}

export const rulesProxy = new CachedResourceProxy<AlertRulesPayload>(
  appResourceCache,
  resourceId("alerts", "rules"),
  {
    read: () => jsonRequest<AlertRulesPayload>("/api/alerts/rules"),
  },
);

export const catalogProxy = new CachedResourceProxy<AlertCatalogPayload>(
  appResourceCache,
  resourceId("alerts", "catalog"),
  {
    read: () => jsonRequest<AlertCatalogPayload>("/api/alerts/catalog"),
  },
);

export async function fetchAlertRules(): Promise<AlertRulesPayload> {
  return rulesProxy.read();
}

export async function fetchAlertCatalog(): Promise<AlertCatalogPayload> {
  return catalogProxy.read();
}

export async function fetchAlertStatus(): Promise<AlertStatusPayload> {
  return jsonRequest<AlertStatusPayload>("/api/alerts/status");
}

export async function createAlertRule(rule: AlertRule): Promise<AlertRule> {
  return rulesProxy.mutateAndInvalidate(() =>
    jsonRequest<AlertRule>("/api/alerts/rules", {
      method: "POST",
      body: JSON.stringify(rule),
    }),
  );
}

export async function replaceAlertRule(
  ruleId: string,
  rule: AlertRule,
): Promise<AlertRule> {
  return rulesProxy.mutateAndInvalidate(() =>
    jsonRequest<AlertRule>(`/api/alerts/rules/${encodeURIComponent(ruleId)}`, {
      method: "PUT",
      body: JSON.stringify(rule),
    }),
  );
}

export async function setAlertRuleEnabled(
  ruleId: string,
  enabled: boolean,
): Promise<AlertRule> {
  return rulesProxy.mutateAndInvalidate(() =>
    jsonRequest<AlertRule>(
      `/api/alerts/rules/${encodeURIComponent(ruleId)}/enabled`,
      { method: "POST", body: JSON.stringify({ enabled }) },
    ),
  );
}

export async function deleteAlertRule(ruleId: string): Promise<void> {
  await rulesProxy.mutateAndInvalidate(() =>
    jsonRequest(`/api/alerts/rules/${encodeURIComponent(ruleId)}`, {
      method: "DELETE",
    }),
  );
}

export async function dryRunAlertRule(
  body: { rule: AlertRule } | { ruleId: string },
): Promise<AlertDryRunReport> {
  return jsonRequest<AlertDryRunReport>("/api/alerts/dry-run", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function testAlertRule(
  ruleId: string,
): Promise<{ ok: boolean; message: string }> {
  return jsonRequest(`/api/alerts/rules/${encodeURIComponent(ruleId)}/test`, {
    method: "POST",
  });
}

export async function exportAlertRules(): Promise<AlertRulesPayload> {
  return jsonRequest<AlertRulesPayload>("/api/alerts/export");
}

export async function importAlertRules(
  document: AlertRulesPayload,
  prune: boolean,
): Promise<unknown> {
  return rulesProxy.mutateAndInvalidate(() =>
    jsonRequest("/api/alerts/import", {
      method: "POST",
      body: JSON.stringify({ document, prune }),
    }),
  );
}
