import type { MetricsSeries } from "../../../shared/api/index.ts";
import type { MetricTypeId } from "../../metricTypes.ts";
import {
  runtimePointValue,
  type RuntimeMetricDef,
} from "../../runtimeMetrics.ts";

export type HeadlineHow = "max" | "total" | "avg";

export type Headline = {
  value: number;
  typeId: MetricTypeId;
  how: HeadlineHow;
  /** Metrics folded into the number (for the tooltip). */
  metrics: RuntimeMetricDef[];
};

const SUMMED: ReadonlySet<MetricTypeId> = new Set(["rate", "count", "bytes"]);
const EDGE_ROLE = "edge";

/**
 * Latest sample per plotted line, rolled into one glanceable number for
 * the graph header: averaged for "avg" views, summed for additive types
 * (rate / count / bytes), otherwise the worst (max) line. Same-type metric
 * pairs (4xx + 5xx, RX + TX) fold together; mixed types use the first.
 */
export function headlineStat(
  visible: MetricsSeries[],
  metrics: RuntimeMetricDef[],
  averaged: boolean,
): Headline | null {
  const first = metrics[0];
  if (!first) return null;
  const how = headlineHow(first.typeId, averaged);
  const folded = averaged || metrics.some((m) => m.typeId !== first.typeId)
    ? [first]
    : metrics;
  const latest = rollUpSeries(visible, how).flatMap((s) =>
    folded
      .map((m) => latestValue(s, m))
      .filter((v): v is number => v !== null),
  );
  if (latest.length === 0) return null;
  return { value: rollUp(latest, how), typeId: first.typeId, how, metrics: folded };
}

export function headlineHow(typeId: MetricTypeId, averaged: boolean): HeadlineHow {
  if (averaged) return "avg";
  return SUMMED.has(typeId) ? "total" : "max";
}

/** The HTTP edge series already sums every service — never add it twice. */
function rollUpSeries(visible: MetricsSeries[], how: HeadlineHow): MetricsSeries[] {
  if (how === "max") return visible;
  const services = visible.filter((s) => s.role !== EDGE_ROLE);
  return services.length ? services : visible;
}

function rollUp(values: number[], how: HeadlineHow): number {
  if (how === "max") return Math.max(...values);
  const sum = values.reduce((a, b) => a + b, 0);
  return how === "total" ? sum : sum / values.length;
}

function latestValue(s: MetricsSeries, metric: RuntimeMetricDef): number | null {
  let bestT = "";
  let best: number | null = null;
  for (const p of s.points) {
    const v = runtimePointValue(p, metric.id);
    if (v === null || p.t < bestT) continue;
    bestT = p.t;
    best = v;
  }
  return best;
}
