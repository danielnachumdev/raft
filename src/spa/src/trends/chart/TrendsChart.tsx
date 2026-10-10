import {
  CartesianGrid,
  Legend,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  YAxis,
} from "recharts";
import type { GraphEvent, MetricsSeries } from "../../shared/api";
import {
  clipRowsToDomain,
  formatTooltipTime,
  windowDomain,
} from "./chartTimeScale";
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
import { trendPlotLines } from "./trendPlotLines";
import { useChartHover } from "./useChartHover";
import {
  aggregatePlots,
  buildAggregateRows,
  buildPerServiceRows,
  LEFT_AXIS,
  needsSplitAxes,
  RIGHT_AXIS,
  toPlotSeries,
  typeIdsForMetrics,
  type ChartRow,
} from "./trendsChartRows";
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
}) {
  const hover = useChartHover();
  const metrics = props.metrics;
  if (!metrics.length) return null;
  const eventSeries = seriesForEventFilter(
    props.allSeries ?? props.series,
    props.series,
  );
  const markers = eventsForSeries(props.events, eventSeries);
  const plots = props.aggregate
    ? aggregatePlots(metrics)
    : toPlotSeries(props.series, metrics);
  const endMs = props.rangeEndMs ?? Date.now();
  const domain = windowDomain(props.windowSeconds, endMs);
  const rows = clipRowsToDomain(
    props.aggregate
      ? buildAggregateRows(props.series, plots)
      : buildPerServiceRows(props.series, plots),
    domain,
  );
  const labels = Object.fromEntries(plots.map((p) => [p.chartKey, p.label]));
  const types = Object.fromEntries(plots.map((p) => [p.chartKey, p.typeId]));
  const axisTypes = typeIdsForMetrics(metrics);
  // Same-type → one axis; cross-type → dual axes (also in avg views).
  const splitAxes = needsSplitAxes(props.series, metrics);
  const leftType = axisTypes[0];
  const rightType = axisTypes[1] ?? leftType;

  if (!rows.length) return null;

  return (
    <div
      className="trends-chart"
      role="img"
      aria-label="Resource trend chart"
      onMouseLeave={hover.clearHover}
    >
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" />
          {timeScaleXAxis(props.windowSeconds, endMs)}
          <YAxis
            yAxisId={LEFT_AXIS}
            tick={{ fill: "var(--muted)", fontSize: 11 }}
            unit={yAxisSuffix(leftType) || undefined}
            width={56}
            domain={[0, "auto"]}
            tickFormatter={(v: number) => formatMetricTick(v, leftType)}
          />
          {splitAxes ? (
            <YAxis
              yAxisId={RIGHT_AXIS}
              orientation="right"
              tick={{ fill: "var(--muted)", fontSize: 11 }}
              unit={yAxisSuffix(rightType) || undefined}
              width={56}
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
            formatter={(value: number | string, name: string) => [
              formatMetricValue(
                Number(value),
                (types[name] ?? leftType) as MetricTypeId,
              ),
              labels[name] ?? name,
            ]}
            itemSorter={tooltipItemSortKey}
          />
          <Legend
            formatter={(value) => labels[value] ?? value}
            onMouseEnter={(item) => {
              if (typeof item.dataKey === "string") {
                hover.hoverSeries(item.dataKey);
              }
            }}
          />
          {trendPlotLines({
            aggregate: false,
            avgLabel: "",
            plots: plots.map((p) => ({
              chartKey: p.chartKey,
              label: p.label,
              axis: p.axis,
            })),
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
