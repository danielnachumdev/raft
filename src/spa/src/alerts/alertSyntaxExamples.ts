/** Demo alert document for the in-UI syntax guide (PII-safe names only). */

import type { AlertRule } from "./alertsHelpers";

/** GitHub tree for checked-in samples + primer. */
export const ALERT_EXAMPLES_GITHUB_URL =
  "https://github.com/danielnachumdev/raft/tree/main/examples/alerts";

export const ALERT_RULES_EXAMPLE_GITHUB_URL =
  "https://github.com/danielnachumdev/raft/blob/main/examples/alerts/rules.yaml";

export type AlertRulesDocument = {
  version: number;
  rules: AlertRule[];
};

/** Same shape as ``examples/alerts/rules.yaml`` (keep in sync). */
export const ALERT_SYNTAX_EXAMPLE: AlertRulesDocument = {
  version: 1,
  rules: [
    {
      id: "demo-api-5xx-rate",
      name: "demo-api 5xx rate",
      description: "High 5xx share on demo-api over a short window.",
      enabled: true,
      severity: "error",
      for: "2m",
      cooldown: "15m",
      repeatEvery: "0s",
      notifyOnRecovery: true,
      noData: "keep",
      channelIds: [],
      condition: {
        signal: "metrics.http",
        select: { target: "demo-api", metric: "error_rate_5xx" },
        kind: "threshold",
        params: {
          aggregate: "avg",
          window: "5m",
          op: "gt",
          value: 0.05,
        },
      },
    },
    {
      id: "demo-api-container-down",
      name: "demo-api container down",
      description: "demo-api Compose service not running.",
      enabled: true,
      severity: "critical",
      for: "1m",
      cooldown: "30m",
      repeatEvery: "0s",
      notifyOnRecovery: true,
      noData: "keep",
      channelIds: [],
      condition: {
        signal: "control.container_status",
        select: { target: "demo-api" },
        kind: "state",
        params: { match: "notIn", values: ["running"] },
      },
    },
  ],
};

export const ALERT_SYNTAX_PRIMER: { term: string; meaning: string }[] = [
  {
    term: "signal",
    meaning:
      "Catalog source id (metrics.http, metrics.resources, control.container_status, …).",
  },
  {
    term: "select",
    meaning:
      "Which subject to watch — target is an App compose id, or * for every App.",
  },
  {
    term: "kind / params",
    meaning:
      "How to match: threshold (aggregate, window, op, value) or state (match, values).",
  },
  {
    term: "for",
    meaning: "Condition must stay true this long before the rule fires (e.g. 2m).",
  },
  {
    term: "cooldown",
    meaning: "Silence before re-notifying the same firing instance.",
  },
  {
    term: "channelIds",
    meaning:
      "Optional. [] / omit = every enabled channel when any exist; rules still evaluate with none.",
  },
];
