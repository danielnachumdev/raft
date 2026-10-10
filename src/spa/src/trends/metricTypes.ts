/**
 * Open-closed metric type registry for Trends charts.
 * Concretes live under ``strategies/metricTypes`` — add there + assign ``typeId``.
 */

import { METRIC_TYPES } from "./strategies/metricTypes.ts";

export type MetricTypeId =
  | "percent"
  | "count"
  | "duration"
  | "bytes"
  | "rate"
  | "uptime";

export type MetricTypeDef = {
  id: MetricTypeId;
  label: string;
  /** Y-axis unit suffix (Recharts ``unit``); empty when ticks are self-describing. */
  axisSuffix: string;
  formatValue: (value: number) => string;
  formatTick: (value: number) => string;
};

export { METRIC_TYPES };

const BY_ID = new Map(METRIC_TYPES.map((t) => [t.id, t]));

export function metricType(id: MetricTypeId): MetricTypeDef {
  const found = BY_ID.get(id);
  if (!found) {
    throw new Error(`unknown metric type: ${id}`);
  }
  return found;
}

/** Selected types in registry order (stable; not checkbox order). */
export function uniqueTypeIds(
  typeIds: Iterable<MetricTypeId>,
): MetricTypeId[] {
  const present = new Set(typeIds);
  return METRIC_TYPES.map((t) => t.id).filter((id) => present.has(id));
}

export function formatMetricValue(
  value: number,
  typeId: MetricTypeId,
): string {
  return metricType(typeId).formatValue(value);
}

export function formatMetricTick(
  value: number,
  typeId: MetricTypeId,
): string {
  return metricType(typeId).formatTick(value);
}

export function yAxisSuffix(typeId: MetricTypeId): string {
  return metricType(typeId).axisSuffix;
}
