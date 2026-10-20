/**
 * Client CSV dialect matching ``DelimitedMetricsExporter`` (dashboard Download /
 * ``raft metrics export_metrics``). Resource graphs share the same header;
 * HTTP metric ids used by a graph are appended so per-graph export stays useful.
 */
import type { MetricsPoint, MetricsSeries } from "../../shared/api/index.ts";

/** Same order as Python ``DelimitedMetricsExporter._POINT_KEYS``. */
export const RESOURCE_POINT_KEYS = [
  "cpu_percent",
  "memory_used_percent",
  "memory_used_bytes",
  "memory_limit_bytes",
  "uptime_seconds",
  "pids",
  "network_rx_bytes",
  "network_tx_bytes",
  "block_read_bytes",
  "block_write_bytes",
] as const;

export const METRICS_CSV_META = [
  "t",
  "series_id",
  "label",
  "kind",
  "role",
  "group",
] as const;

/** Exact server metrics CSV header (resource plane). */
export const SERVER_METRICS_CSV_COLUMNS = [
  ...METRICS_CSV_META,
  ...RESOURCE_POINT_KEYS,
] as const;

const RESOURCE_SET = new Set<string>(RESOURCE_POINT_KEYS);

export type MetricsCsvOptions = {
  /**
   * Extra point columns after the server resource keys (e.g. graph HTTP metrics).
   * Duplicates of resource keys are ignored.
   */
  extraPointKeys?: readonly string[];
};

/** Flatten series into CSV text (header always present). */
export function encodeMetricsCsv(
  series: MetricsSeries[],
  opts: MetricsCsvOptions = {},
): string {
  const columns = columnsForExport(opts.extraPointKeys);
  const pointKeys = columns.slice(METRICS_CSV_META.length);
  const lines = [columns.join(",")];
  for (const item of series) {
    for (const point of item.points) {
      lines.push(rowCsv(columns, item, point, pointKeys));
    }
  }
  return `${lines.join("\n")}\n`;
}

/** Server columns plus unique extras (stable order of ``extraPointKeys``). */
export function columnsForExport(extraPointKeys?: readonly string[]): string[] {
  const extras = (extraPointKeys ?? []).filter(
    (k) => k && !RESOURCE_SET.has(k) && k !== "t",
  );
  const seen = new Set<string>();
  const unique: string[] = [];
  for (const key of extras) {
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(key);
  }
  return [...SERVER_METRICS_CSV_COLUMNS, ...unique];
}

function rowCsv(
  columns: string[],
  series: MetricsSeries,
  point: MetricsPoint,
  pointKeys: readonly string[],
): string {
  const cells = new Map<string, string>([
    ["t", cell(point.t)],
    ["series_id", cell(series.id)],
    ["label", cell(series.label)],
    ["kind", cell(series.kind)],
    ["role", cell(series.role)],
    ["group", cell(series.group)],
  ]);
  for (const key of pointKeys) {
    cells.set(key, cell(pointValue(point, key)));
  }
  return columns.map((c) => escapeCsv(cells.get(c) ?? "")).join(",");
}

function pointValue(point: MetricsPoint, key: string): unknown {
  return (point as Record<string, unknown>)[key];
}

function cell(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value);
}

/** RFC-style escape: quote when comma/quote/newline present. */
export function escapeCsv(value: string): string {
  if (/[",\n\r]/.test(value)) return `"${value.replace(/"/g, '""')}"`;
  return value;
}
