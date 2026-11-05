/** Pure helpers for alert rule drafts, durations, and condition trees. */

export type AlertConditionLeaf = {
  signal: string;
  select: Record<string, unknown>;
  kind: string;
  params: Record<string, unknown>;
};

export type AlertConditionGroup = {
  all?: AlertCondition[];
  any?: AlertCondition[];
};

export type AlertCondition = AlertConditionLeaf | AlertConditionGroup;

export type AlertCatalogField = {
  key: string;
  label: string;
  kind: string;
  required?: boolean;
  options?: { value: string; label: string }[];
  default?: unknown;
};

export type AlertCatalogSource = {
  type_id: string;
  label: string;
  value_type: string;
  select_fields: AlertCatalogField[];
  metrics: { key: string; label: string; unit: string; scopes: string[] }[];
};

export type AlertCatalogKind = {
  kind_id: string;
  label: string;
  value_types: string[];
  fields: AlertCatalogField[];
};

export type AlertCatalogPayload = {
  sources: AlertCatalogSource[];
  kinds: AlertCatalogKind[];
  severities: string[];
  noData: string[];
  limits: { maxRules: number; maxLeaves: number; maxDepth: number };
};

export type AlertRule = {
  id: string;
  name: string;
  enabled: boolean;
  severity: string;
  description: string;
  for: string;
  cooldown: string;
  repeatEvery: string;
  notifyOnRecovery: boolean;
  noData: string;
  channelIds: string[];
  condition: AlertCondition;
};

const DURATION_RE = /^(\d+)(s|m|h|d)$/;
const UNITS: Record<string, number> = { s: 1, m: 60, h: 3600, d: 86400 };

export function parseAlertDuration(text: string): number | null {
  const trimmed = text.trim();
  if (/^\d+$/.test(trimmed)) return Number(trimmed);
  const match = DURATION_RE.exec(trimmed);
  if (!match) return null;
  return Number(match[1]) * UNITS[match[2]];
}

export function formatAlertDuration(seconds: number): string {
  if (seconds % 86400 === 0 && seconds >= 86400) return `${seconds / 86400}d`;
  if (seconds % 3600 === 0 && seconds >= 3600) return `${seconds / 3600}h`;
  if (seconds % 60 === 0 && seconds >= 60) return `${seconds / 60}m`;
  return `${seconds}s`;
}

export function isGroup(node: AlertCondition): node is AlertConditionGroup {
  return "all" in node || "any" in node;
}

export function groupOp(node: AlertConditionGroup): "all" | "any" {
  return "all" in node && node.all ? "all" : "any";
}

export function groupChildren(node: AlertConditionGroup): AlertCondition[] {
  return (node.all ?? node.any ?? []) as AlertCondition[];
}

export function countLeaves(tree: AlertCondition): number {
  if (!isGroup(tree)) return 1;
  return groupChildren(tree).reduce((n, child) => n + countLeaves(child), 0);
}

export function depth(tree: AlertCondition): number {
  if (!isGroup(tree)) return 0;
  const kids = groupChildren(tree);
  return 1 + Math.max(0, ...kids.map(depth));
}

export function defaultLeaf(catalog: AlertCatalogPayload): AlertConditionLeaf {
  const source =
    catalog.sources.find((s) => s.value_type === "numeric") ?? catalog.sources[0];
  const kind =
    catalog.kinds.find((k) => k.value_types.includes(source?.value_type ?? "numeric")) ??
    catalog.kinds[0];
  const select: Record<string, unknown> = {};
  for (const field of source?.select_fields ?? []) {
    select[field.key] = field.default ?? field.options?.[0]?.value ?? "";
  }
  const params: Record<string, unknown> = {};
  for (const field of kind?.fields ?? []) {
    params[field.key] = field.default ?? "";
  }
  return {
    signal: source?.type_id ?? "metrics.http",
    select,
    kind: kind?.kind_id ?? "threshold",
    params,
  };
}

export function summarizeCondition(
  tree: AlertCondition,
  _catalog?: AlertCatalogPayload,
): string {
  if (isGroup(tree)) {
    const op = groupOp(tree).toUpperCase();
    return `${op}(${groupChildren(tree).map((c) => summarizeCondition(c)).join(", ")})`;
  }
  const metric = String(tree.select.metric ?? tree.select.target ?? "");
  return `${tree.signal} ${metric} ${tree.kind}`;
}

export function emptyRuleDraft(catalog: AlertCatalogPayload): AlertRule {
  return {
    id: "",
    name: "",
    enabled: true,
    severity: catalog.severities[1] ?? "warning",
    description: "",
    for: "0s",
    cooldown: "15m",
    repeatEvery: "0s",
    notifyOnRecovery: true,
    noData: "ok",
    channelIds: [],
    condition: defaultLeaf(catalog),
  };
}

export function draftFromRule(rule: AlertRule): AlertRule {
  return { ...rule, channelIds: [...rule.channelIds], condition: rule.condition };
}

export function ruleFromDraft(draft: AlertRule): AlertRule {
  return draft;
}

export function validateDraft(draft: AlertRule): string[] {
  const errors: string[] = [];
  if (!/^[a-z0-9][a-z0-9-]{0,62}$/.test(draft.id)) {
    errors.push("id must match ^[a-z0-9][a-z0-9-]{0,62}$");
  }
  if (!draft.name.trim()) errors.push("name is required");
  for (const key of ["for", "cooldown", "repeatEvery"] as const) {
    if (parseAlertDuration(draft[key]) === null) {
      errors.push(`${key} is not a valid duration`);
    }
  }
  return errors;
}

export function ruleStateFor(
  status: { rules?: Record<string, { state?: string }> } | null,
  ruleId: string,
  enabled: boolean,
): string {
  if (!enabled) return "disabled";
  return status?.rules?.[ruleId]?.state ?? "unknown";
}

export function routingLabel(
  channelIds: string[],
  channels: { id: string }[],
): string {
  if (!channelIds.length) return "All enabled channels";
  const known = new Set(channels.map((c) => c.id));
  return channelIds
    .map((id) => (known.has(id) ? id : `${id} (missing)`))
    .join(", ");
}

export function kindsForSource(
  catalog: AlertCatalogPayload,
  signal: string,
): AlertCatalogKind[] {
  const source = catalog.sources.find((s) => s.type_id === signal);
  if (!source) return catalog.kinds;
  return catalog.kinds.filter((k) => k.value_types.includes(source.value_type));
}

export function wrapInGroup(
  tree: AlertCondition,
  _path: number[],
  op: "all" | "any",
): AlertCondition {
  return op === "all" ? { all: [tree] } : { any: [tree] };
}

export function addLeaf(
  tree: AlertCondition,
  _path: number[],
  leaf: AlertConditionLeaf,
): AlertCondition {
  if (!isGroup(tree)) return { all: [tree, leaf] };
  const op = groupOp(tree);
  const children = [...groupChildren(tree), leaf];
  return op === "all" ? { all: children } : { any: children };
}

/** Chip class for a rule's evaluation state (firing / pending / ok / disabled). */
export function ruleStateChip(state: string): string {
  if (state === "firing") return "chip chip-bad";
  if (state === "pending" || state === "suppressed") return "chip chip-warn";
  if (state === "ok") return "chip chip-ok";
  return "chip";
}

/** Chip class for a rule severity (critical/error → bad, warning → warn, info → idle). */
export function severityChip(severity: string): string {
  const s = severity.toLowerCase();
  if (s === "critical" || s === "error") return "chip chip-bad";
  if (s === "warning" || s === "warn") return "chip chip-warn";
  if (s === "info") return "chip chip-idle";
  return "chip";
}
