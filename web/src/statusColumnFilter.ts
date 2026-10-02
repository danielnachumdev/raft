import type { StatusRow } from "./api";
import { parseMemoryRatioPercent, parsePercent } from "./statusTone";

export type SortKey = Exclude<keyof StatusRow, "external_urls">;
export type ColumnValueKind = "string" | "numeric";

export const COLUMN_LABELS: Record<SortKey, string> = {
  name: "Name",
  role: "Role",
  group: "Group",
  status: "Status",
  cpu: "CPU",
  memory: "Memory",
  started: "Started",
  uptime: "Uptime",
  service: "Service",
};

export type StringFilterOp =
  | "contains"
  | "equals"
  | "not_equals"
  | "starts_with";
export type NumericFilterOp = "equals" | "not_equals" | "gt" | "lt";
export type FilterOp = StringFilterOp | NumericFilterOp;

export type ColumnFilter = {
  op: FilterOp;
  value: string;
};

export type ColumnFilters = Partial<Record<SortKey, ColumnFilter>>;

export const STRING_OPS: readonly StringFilterOp[] = [
  "contains",
  "equals",
  "not_equals",
  "starts_with",
];

export const NUMERIC_OPS: readonly NumericFilterOp[] = [
  "equals",
  "not_equals",
  "gt",
  "lt",
];

const NUMERIC_KEYS: ReadonlySet<string> = new Set(["cpu", "memory"]);

const OP_LABELS: Record<FilterOp, string> = {
  contains: "contains",
  equals: "equals",
  not_equals: "does not equal",
  starts_with: "starts with",
  gt: "greater than",
  lt: "less than",
};

const ALL_KEYS: ReadonlySet<string> = new Set(Object.keys(COLUMN_LABELS));

export function columnValueKind(key: SortKey): ColumnValueKind {
  return NUMERIC_KEYS.has(key) ? "numeric" : "string";
}

export function operatorsFor(key: SortKey): readonly FilterOp[] {
  return columnValueKind(key) === "numeric" ? NUMERIC_OPS : STRING_OPS;
}

export function defaultFilterOp(key: SortKey): FilterOp {
  return columnValueKind(key) === "numeric" ? "equals" : "contains";
}

export function filterOpLabel(op: FilterOp): string {
  return OP_LABELS[op];
}

export function isActiveColumnFilter(
  filter: ColumnFilter | undefined,
): boolean {
  return Boolean(filter && filter.value.trim());
}

export function activeColumnFilterEntries(
  filters: ColumnFilters,
): { key: SortKey; filter: ColumnFilter }[] {
  const entries: { key: SortKey; filter: ColumnFilter }[] = [];
  for (const key of Object.keys(filters) as SortKey[]) {
    const filter = filters[key];
    if (isActiveColumnFilter(filter)) {
      entries.push({ key, filter: filter! });
    }
  }
  return entries;
}

export function matchColumnFilter(
  row: StatusRow,
  key: SortKey,
  filter: ColumnFilter,
): boolean {
  const needle = filter.value.trim();
  if (!needle) {
    return true;
  }
  const cell = row[key];
  if (columnValueKind(key) === "numeric") {
    return matchNumeric(key, cell, filter.op, needle);
  }
  return matchString(cell, filter.op, needle);
}

export function normalizeColumnFilters(raw: unknown): ColumnFilters {
  if (!raw || typeof raw !== "object") {
    return {};
  }
  const out: ColumnFilters = {};
  for (const [key, val] of Object.entries(raw as Record<string, unknown>)) {
    const parsed = parseStoredFilter(key, val);
    if (parsed) {
      out[key as SortKey] = parsed;
    }
  }
  return out;
}

function parseStoredFilter(key: string, val: unknown): ColumnFilter | null {
  if (!ALL_KEYS.has(key)) {
    return null;
  }
  if (!val || typeof val !== "object") {
    return null;
  }
  const op = (val as { op?: unknown }).op;
  const value = (val as { value?: unknown }).value;
  if (typeof op !== "string" || typeof value !== "string") {
    return null;
  }
  if (!value.trim()) {
    return null;
  }
  const allowed = operatorsFor(key as SortKey);
  if (!allowed.includes(op as FilterOp)) {
    return null;
  }
  return { op: op as FilterOp, value };
}

function matchString(cell: string, op: FilterOp, needle: string): boolean {
  const hay = cell.toLowerCase();
  const n = needle.toLowerCase();
  switch (op) {
    case "equals":
      return hay === n;
    case "not_equals":
      return hay !== n;
    case "starts_with":
      return hay.startsWith(n);
    case "contains":
    default:
      return hay.includes(n);
  }
}

function matchNumeric(
  key: SortKey,
  cell: string,
  op: FilterOp,
  needle: string,
): boolean {
  const cellNum =
    key === "cpu" ? parsePercent(cell) : parseMemoryRatioPercent(cell);
  const filterNum = parseFilterNumber(needle);
  if (cellNum === null || filterNum === null) {
    return cell.toLowerCase().includes(needle.toLowerCase());
  }
  switch (op) {
    case "equals":
      return Math.abs(cellNum - filterNum) < 0.05;
    case "not_equals":
      return Math.abs(cellNum - filterNum) >= 0.05;
    case "gt":
      return cellNum > filterNum;
    case "lt":
      return cellNum < filterNum;
    default:
      return cell.toLowerCase().includes(needle.toLowerCase());
  }
}

function parseFilterNumber(text: string): number | null {
  const raw = text.trim().replace(/%$/, "");
  if (!raw) {
    return null;
  }
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}
