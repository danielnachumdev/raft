import { useMemo } from "react";
import type { MetricsSeries } from "../../../shared/api";
import type { RuntimeMetricDef } from "../runtimeMetrics";
import {
  aggregatePlots,
  buildAggregateRows,
  buildPerServiceRows,
  toPlotSeries,
} from "./trendsChartRows";
import { useStableClip } from "./useStableClip";

/**
 * Plots + merged rows rebuild only when samples or the selection change;
 * the rolling clock just re-clips (identity kept when nothing scrolled out).
 */
export function useTrendsChartRows(args: {
  series: MetricsSeries[];
  metrics: RuntimeMetricDef[];
  aggregate: boolean;
  windowSeconds: number;
  endMs: number;
}) {
  const { series, metrics, aggregate } = args;
  const plots = useMemo(
    () => (aggregate ? aggregatePlots(metrics) : toPlotSeries(series, metrics)),
    [aggregate, series, metrics],
  );
  const merged = useMemo(
    () => (aggregate ? buildAggregateRows(series, plots) : buildPerServiceRows(series, plots)),
    [aggregate, series, plots],
  );
  const rows = useStableClip(merged, args.windowSeconds, args.endMs);
  const lookups = useMemo(
    () => ({
      labels: Object.fromEntries(plots.map((p) => [p.chartKey, p.label])),
      types: Object.fromEntries(plots.map((p) => [p.chartKey, p.typeId])),
    }),
    [plots],
  );
  return { plots, rows, ...lookups };
}
