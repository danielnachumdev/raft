import type { ParsedLogLine } from "./logParse";

/** String-contains operators over raw log line text. */
export type LogFilterOp =
  | "contains_all"
  | "contains_any"
  | "not_contains_all"
  | "not_contains_any";

export type LogFilter = {
  op: LogFilterOp;
  values: string[];
};

export const LOG_FILTER_OPS: readonly LogFilterOp[] = [
  "contains_all",
  "contains_any",
  "not_contains_all",
  "not_contains_any",
];

const OP_LABELS: Record<LogFilterOp, string> = {
  contains_all: "contains all",
  contains_any: "contains any",
  not_contains_all: "not contains all",
  not_contains_any: "not contains any",
};

/** Default filter: contains-any with one empty value box. */
export function defaultLogFilter(): LogFilter {
  return { op: "contains_any", values: [""] };
}

export function logFilterOpLabel(op: LogFilterOp): string {
  return OP_LABELS[op];
}

/** Non-empty trimmed needles used for match + highlight. */
export function trimFilterValues(values: string[]): string[] {
  return values.map((v) => v.trim()).filter((v) => v.length > 0);
}

export function activeFilterValues(filter: LogFilter): string[] {
  return trimFilterValues(filter.values);
}

export function isLogFilterActive(filter: LogFilter): boolean {
  return activeFilterValues(filter).length > 0;
}

/** Case-insensitive string contains filter over the original line text. */
export function filterLogLines(
  lines: ParsedLogLine[],
  filter: LogFilter,
): ParsedLogLine[] {
  const needles = activeFilterValues(filter).map((v) => v.toLowerCase());
  if (needles.length === 0) return lines;
  return lines.filter((line) =>
    matchRawLine(line.raw.toLowerCase(), filter.op, needles),
  );
}

function matchRawLine(
  haystack: string,
  op: LogFilterOp,
  needles: string[],
): boolean {
  const hits = needles.map((n) => haystack.includes(n));
  switch (op) {
    case "contains_all":
      return hits.every(Boolean);
    case "contains_any":
      return hits.some(Boolean);
    case "not_contains_all":
      return !hits.every(Boolean);
    case "not_contains_any":
      return !hits.some(Boolean);
  }
}
