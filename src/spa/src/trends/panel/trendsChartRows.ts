import type { MetricsSeries } from "../../shared/api.ts";
import {
  mergeTimedRows,
  toEpochMs,
  type TimedValue,
} from "../chart/chartTimeScale.ts";
import {
  uniqueTypeIds,
  type MetricTypeId,
} from "../metricTypes.ts";
import {
  runtimePointValue,
  type RuntimeMetricDef,
  type RuntimeMetricId,
} from "../runtimeMetrics.ts";

export const LEFT_AXIS = "left";
export const RIGHT_AXIS = "right";

export type ChartRow = {
  ts: number;
  t: string;
  label: string;
  [key: string]: string | number | null;
};

export type PlotSeries = {
  chartKey: string;
  seriesId: string;
  metricId: RuntimeMetricId;
  label: string;
  typeId: MetricTypeId;
  axis: typeof LEFT_AXIS | typeof RIGHT_AXIS;
};

/** Build plot descriptors for each visible series × selected metric. */
export function toPlotSeries(
  series: MetricsSeries[],
  metrics: RuntimeMetricDef[],
): PlotSeries[] {
  const types = typeIdsForMetrics(metrics);
  const multi = metrics.length > 1;
  const sorted = [...series].sort(
    (a, b) => a.label.localeCompare(b.label) || a.id.localeCompare(b.id),
  );
  const plots: PlotSeries[] = [];
  let i = 0;
  for (const s of sorted) {
    for (const m of metrics) {
      plots.push({
        chartKey: `v${i++}`,
        seriesId: s.id,
        metricId: m.id,
        label: multi ? `${s.label} · ${m.label}` : s.label,
        typeId: m.typeId,
        axis: axisForType(m.typeId, types),
      });
    }
  }
  return plots;
}

export function aggregatePlots(metrics: RuntimeMetricDef[]): PlotSeries[] {
  const types = typeIdsForMetrics(metrics);
  const multi = metrics.length > 1;
  return metrics.map((m, i) => ({
    chartKey: `agg${i}`,
    seriesId: "aggregate",
    metricId: m.id,
    label: multi ? `Average · ${m.label}` : "Average",
    typeId: m.typeId,
    axis: axisForType(m.typeId, types),
  }));
}

export function buildPerServiceRows(
  series: MetricsSeries[],
  plots: PlotSeries[],
): ChartRow[] {
  const keyed = plots.map((p) => ({
    key: p.chartKey,
    points: timedPointsForSeries(
      series.find((s) => s.id === p.seriesId),
      p.metricId,
    ),
  }));
  return mergeTimedRows(keyed) as ChartRow[];
}

export function buildAggregateRows(
  series: MetricsSeries[],
  plots: PlotSeries[],
): ChartRow[] {
  const keyed = plots.map((p) => ({
    key: p.chartKey,
    points: aggregateTimedPoints(series, p.metricId),
  }));
  return mergeTimedRows(keyed) as ChartRow[];
}

/** Coerce JSON numbers so stringy samples still plot. */
export function pointValue(
  point: MetricsSeries["points"][0],
  metric: RuntimeMetricId,
): number | null {
  return runtimePointValue(point, metric);
}

/** Axis type ids for selected metrics (registry order; max two axes). */
export function typeIdsForMetrics(
  metrics: RuntimeMetricDef[],
): MetricTypeId[] {
  return uniqueTypeIds(metrics.map((m) => m.typeId));
}

/**
 * Assign left/right by metric type (stable registry order).
 * Same-type → shared left axis. Two types → type[0] left, type[1] right.
 * Selection UI caps at two types (see ``MAX_METRIC_TYPES``).
 */
export function axisForType(
  typeId: MetricTypeId,
  types: MetricTypeId[],
): typeof LEFT_AXIS | typeof RIGHT_AXIS {
  return types.indexOf(typeId) === 1 ? RIGHT_AXIS : LEFT_AXIS;
}

export function needsSplitAxes(
  _series: MetricsSeries[],
  metrics: RuntimeMetricDef[],
): boolean {
  return typeIdsForMetrics(metrics).length > 1;
}

function aggregateTimedPoints(
  series: MetricsSeries[],
  metric: RuntimeMetricId,
): TimedValue[] {
  const byTime = new Map<string, number[]>();
  for (const s of series) {
    for (const p of s.points) {
      const v = pointValue(p, metric);
      if (v === null) continue;
      const list = byTime.get(p.t) ?? [];
      list.push(v);
      byTime.set(p.t, list);
    }
  }
  return [...byTime.entries()].map(([t, vals]) => ({
    ts: toEpochMs(t) ?? 0,
    t,
    value: vals.reduce((a, b) => a + b, 0) / vals.length,
  }));
}

function timedPointsForSeries(
  series: MetricsSeries | undefined,
  metric: RuntimeMetricId,
): TimedValue[] {
  if (!series) return [];
  const out: TimedValue[] = [];
  for (const p of series.points) {
    const ts = toEpochMs(p.t);
    if (ts === null) continue;
    out.push({ ts, t: p.t, value: pointValue(p, metric) });
  }
  return out;
}
