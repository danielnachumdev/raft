import { useMemo } from "react";
import {
  CartesianGrid,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  YAxis,
} from "recharts";
import type { GraphEvent, MetricsSeries } from "../../../shared/api";
import { formatTooltipTime } from "./chartTimeScale";
import { graphEventMarkers } from "./GraphEventMarkers";
import { eventsForSeries, seriesForEventFilter } from "./graphEvents";
import {
  formatMetricTick,
  formatMetricValue,
  yAxisSuffix,
  type MetricTypeId,
} from "../metricTypes";
import type { RuntimeMetricDef } from "../runtimeMetrics";
import { timeScaleXAxis } from "./TimeScaleXAxis";
import { tooltipItemSortKey } from "./tooltipItemSort";
import { trendsLegend } from "./TrendsLegend";
import { trendPlotLines } from "./trendPlotLines";
import { useChartHover } from "./useChartHover";
import {
  LEFT_AXIS,
  needsSplitAxes,
  RIGHT_AXIS,
  typeIdsForMetrics,
  type ChartRow,
  type PlotSeries,
} from "./trendsChartRows";
import { useTrendsChartRows } from "./useTrendsChartRows";
import "./TrendsChart.css";

export { tooltipItemSortKey } from "./tooltipItemSort";
export {
  buildPerServiceRows,
  pointValue,
} from "./trendsChartRows";

export function TrendsChart(props: {
  series: MetricsSeries[];
  metrics: RuntimeMetricDef[];
  windowSeconds: number;
  rangeEndMs?: number;
  aggregate: boolean;
  events?: GraphEvent[];
  /** Full window series — used to map group charts back to deploy services. */
  allSeries?: MetricsSeries[];
  height?: number;
  /** Series id → color slot; keeps a service's color across dashboard graphs. */
  palette?: Map<string, number>;
}) {
  const hover = useChartHover();
  const metrics = props.metrics;
  const endMs = props.rangeEndMs ?? Date.now();
  const { plots, rows, labels, types } = useTrendsChartRows({
    series: props.series,
    metrics,
    aggregate: props.aggregate,
    windowSeconds: props.windowSeconds,
    endMs,
  });
  const markers = useMemo(
    () =>
      eventsForSeries(
        props.events,
        seriesForEventFilter(props.allSeries ?? props.series, props.series),
      ),
    [props.events, props.allSeries, props.series],
  );
  const linePlots = useMemo(
    () =>
      plots.map((p) => ({
        chartKey: p.chartKey,
        label: p.label,
        axis: p.axis,
        ...paletteStyle(p, metrics, props.palette),
      })),
    [plots, metrics, props.palette],
  );
  if (!metrics.length) return null;
  const axisTypes = typeIdsForMetrics(metrics);
  // Same-type → one axis; cross-type → dual axes (also in avg views).
  const splitAxes = needsSplitAxes(props.series, metrics);
  const leftType = axisTypes[0];
  const rightType = axisTypes[1] ?? leftType;

  if (!rows.length) return null;
  const height = props.height ?? 280;

  return (
    <div
      className="trends-chart"
      role="img"
      aria-label="Resource trend chart"
      onMouseLeave={hover.clearHover}
      style={{ minHeight: height }}
    >
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" />
          {timeScaleXAxis(props.windowSeconds, endMs)}
          <YAxis
            yAxisId={LEFT_AXIS}
            tick={{ fill: "var(--muted)", fontSize: 11 }}
            unit={yAxisSuffix(leftType) || undefined}
            width={axisWidth(leftType)}
            domain={[0, "auto"]}
            tickFormatter={(v: number) => formatMetricTick(v, leftType)}
          />
          {splitAxes ? (
            <YAxis
              yAxisId={RIGHT_AXIS}
              orientation="right"
              tick={{ fill: "var(--muted)", fontSize: 11 }}
              unit={yAxisSuffix(rightType) || undefined}
              width={axisWidth(rightType)}
              domain={[0, "auto"]}
              tickFormatter={(v: number) => formatMetricTick(v, rightType)}
            />
          ) : null}
          <Tooltip
            contentStyle={{
              background: "var(--panel)",
              border: "1px solid var(--line)",
              borderRadius: "0.4rem",
            }}
            labelFormatter={(_, payload) => {
              const row = payload?.[0]?.payload as ChartRow | undefined;
              return row?.t ? formatTooltipTime(row.t) : "";
            }}
            formatter={(value, name) => [
              formatMetricValue(
                Number(value),
                (types[String(name)] ?? leftType) as MetricTypeId,
              ),
              labels[String(name)] ?? String(name ?? ""),
            ]}
            itemSorter={tooltipItemSortKey}
          />
          {trendsLegend({
            labels,
            highlight: hover.highlight,
            onHoverSeries: hover.hoverSeries,
          })}
          {trendPlotLines({
            aggregate: false,
            avgLabel: "",
            plots: linePlots,
            rows,
            splitAxes,
            serviceAxis: LEFT_AXIS,
            highlight: hover.highlight,
            onHoverSeries: hover.hoverSeries,
          })}
          {graphEventMarkers(markers, {
            yAxisId: LEFT_AXIS,
            highlight: hover.highlight,
            onHoverKind: hover.hoverEventKind,
          })}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Byte / uptime ticks carry their own unit text ("762.9 MiB"). */
function axisWidth(typeId: MetricTypeId): number {
  return typeId === "bytes" || typeId === "uptime" ? 80 : 56;
}

function paletteStyle(
  plot: PlotSeries,
  metrics: RuntimeMetricDef[],
  palette: Map<string, number> | undefined,
): { colorIndex?: number; dashed?: boolean } {
  if (!palette) return {};
  return {
    colorIndex: palette.get(plot.seriesId),
    dashed: metrics.length > 1 && plot.metricId === metrics[1].id,
  };
}
