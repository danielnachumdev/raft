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
} from "../chart/chartTimeScale";
import { graphEventMarkers } from "../chart/GraphEventMarkers";
import { eventsForSeries, seriesForEventFilter } from "../chart/graphEvents";
import {
  formatRuntimeValue,
  yAxisUnit,
  type RuntimeMetricDef,
  type RuntimeUnit,
} from "../runtimeMetrics";
import { timeScaleXAxis } from "../chart/TimeScaleXAxis";
import { tooltipItemSortKey } from "../chart/tooltipItemSort";
import { trendPlotLines } from "../chart/trendPlotLines";
import { useChartHover } from "../chart/useChartHover";
import {
  aggregatePlots,
  buildAggregateRows,
  buildPerServiceRows,
  LEFT_AXIS,
  needsSplitAxes,
  RIGHT_AXIS,
  toPlotSeries,
  type ChartRow,
} from "./trendsChartRows";
import "./TrendsChart.css";

export { tooltipItemSortKey } from "../chart/tooltipItemSort";
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
  const units = Object.fromEntries(plots.map((p) => [p.chartKey, p.unit]));
  const splitAxes = !props.aggregate && needsSplitAxes(props.series, metrics);
  const leftUnit = metrics[0].unit;
  const rightUnit =
    metrics.find((m) => m.unit !== leftUnit)?.unit ?? leftUnit;

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
            unit={yAxisUnit(leftUnit) || undefined}
            width={56}
            domain={[0, "auto"]}
            tickFormatter={(v: number) => formatAxisTick(v, leftUnit)}
          />
          {splitAxes ? (
            <YAxis
              yAxisId={RIGHT_AXIS}
              orientation="right"
              tick={{ fill: "var(--muted)", fontSize: 11 }}
              unit={yAxisUnit(rightUnit) || undefined}
              width={56}
              domain={[0, "auto"]}
              tickFormatter={(v: number) => formatAxisTick(v, rightUnit)}
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
              formatRuntimeValue(
                Number(value),
                units[name] ?? leftUnit,
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

function formatAxisTick(value: number, unit: RuntimeUnit): string {
  if (unit === "bytes") return formatRuntimeValue(value, "bytes");
  if (unit === "seconds") return formatRuntimeValue(value, "seconds");
  return String(value);
}
