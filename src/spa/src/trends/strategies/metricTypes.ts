/**
 * Concrete metric type strategies for Trends charts.
 * Add a type here + assign ``typeId`` on metrics — no chart switch explosion.
 */

import type { MetricTypeDef } from "../metricTypes.ts";

export const METRIC_TYPES: MetricTypeDef[] = [
  {
    id: "percent",
    label: "Percent",
    axisSuffix: "%",
    formatValue: (v) => `${v.toFixed(1)}%`,
    formatTick: (v) => String(v),
  },
  {
    id: "count",
    label: "Count",
    axisSuffix: "",
    formatValue: (v) => String(Math.round(v)),
    formatTick: (v) => String(v),
  },
  {
    id: "duration",
    label: "Duration",
    axisSuffix: "ms",
    formatValue: (v) => `${v.toFixed(1)} ms`,
    formatTick: (v) => String(v),
  },
  {
    id: "bytes",
    label: "Bytes",
    axisSuffix: "",
    formatValue: formatBytes,
    formatTick: formatBytes,
  },
  {
    id: "rate",
    label: "Rate",
    axisSuffix: "/s",
    formatValue: (v) => `${v.toFixed(2)}/s`,
    formatTick: (v) => String(v),
  },
  {
    id: "uptime",
    label: "Uptime",
    axisSuffix: "",
    formatValue: formatUptime,
    formatTick: formatUptime,
  },
];

function formatBytes(n: number): string {
  const abs = Math.abs(n);
  if (abs < 1024) return `${Math.round(n)} B`;
  if (abs < 1024 ** 2) return `${(n / 1024).toFixed(1)} KiB`;
  if (abs < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MiB`;
  return `${(n / 1024 ** 3).toFixed(2)} GiB`;
}

function formatUptime(n: number): string {
  if (n < 60) return `${n.toFixed(0)}s`;
  if (n < 3600) return `${(n / 60).toFixed(1)}m`;
  return `${(n / 3600).toFixed(1)}h`;
}
