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
  mergeTimedRows,
  toEpochMs,
  windowDomain,
  type TimedValue,
} from "../chart/chartTimeScale";
import { graphEventMarkers } from "../chart/GraphEventMarkers";
import { eventsForSeries, seriesForEventFilter } from "../chart/graphEvents";
import {
  formatRuntimeValue,
  runtimePointValue,
  yAxisUnit,
  type RuntimeMetricId,
  type RuntimeUnit,
} from "../runtimeMetrics";
import { timeScaleXAxis } from "../chart/TimeScaleXAxis";
import { tooltipItemSortKey } from "../chart/tooltipItemSort";
import { trendPlotLines } from "../chart/trendPlotLines";
import { useChartHover } from "../chart/useChartHover";
import "./TrendsChart.css";

export { tooltipItemSortKey } from "../chart/tooltipItemSort";
const HOST_AXIS = "host";
const SERVICE_AXIS = "service";

type ChartRow = {
  ts: number;
  t: string;
  label: string;
  [key: string]: string | number | null;
};

type PlotSeries = {
  chartKey: string;
  id: string;
  label: string;
  axis: typeof HOST_AXIS | typeof SERVICE_AXIS;
};

export function TrendsChart(props: {
  series: MetricsSeries[];
  metric: RuntimeMetricId;
  unit: RuntimeUnit;
  windowSeconds: number;
  rangeEndMs?: number;
  aggregate: boolean;
  aggregateLabel?: string;
  events?: GraphEvent[];
  /** Full window series — used to map group charts back to deploy services. */
  allSeries?: MetricsSeries[];
}) {
  const hover = useChartHover();
  const avgLabel = props.aggregateLabel ?? "Average";
  const eventSeries = seriesForEventFilter(
    props.allSeries ?? props.series,
    props.series,
  );
  const markers = eventsForSeries(props.events, eventSeries);
  const plots = props.aggregate ? [] : toPlotSeries(props.series);
  const endMs = props.rangeEndMs ?? Date.now();
  const domain = windowDomain(props.windowSeconds, endMs);
  const rows = clipRowsToDomain(
    props.aggregate
      ? buildAggregateRows(props.series, props.metric)
      : buildPerServiceRows(props.series, plots, props.metric),
    domain,
  );
  const labels = props.aggregate
    ? { aggregate: avgLabel }
    : Object.fromEntries(plots.map((p) => [p.chartKey, p.label]));
  const splitAxes = !props.aggregate && needsSplitAxes(props.series);
  const axisUnit = yAxisUnit(props.unit);

  if (!rows.length) {
    return null;
  }

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
            yAxisId={SERVICE_AXIS}
            tick={{ fill: "var(--muted)", fontSize: 11 }}
            unit={axisUnit || undefined}
            width={56}
            domain={[0, "auto"]}
            tickFormatter={(v: number) => formatAxisTick(v, props.unit)}
          />
          {splitAxes ? (
            <YAxis
              yAxisId={HOST_AXIS}
              orientation="right"
              tick={{ fill: "var(--muted)", fontSize: 11 }}
              unit={axisUnit || undefined}
              width={56}
              domain={[0, "auto"]}
              tickFormatter={(v: number) => formatAxisTick(v, props.unit)}
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
              formatRuntimeValue(Number(value), props.unit),
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
            aggregate: props.aggregate,
            avgLabel,
            plots,
            splitAxes,
            serviceAxis: SERVICE_AXIS,
            highlight: hover.highlight,
            onHoverSeries: hover.hoverSeries,
          })}
          {/* Direct children — Recharts ignores wrapper components for ReferenceLine. */}
          {graphEventMarkers(markers, {
            yAxisId: SERVICE_AXIS,
            highlight: hover.highlight,
            onHoverKind: hover.hoverEventKind,
          })}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function toPlotSeries(series: MetricsSeries[]): PlotSeries[] {
  return [...series]
    .sort((a, b) => a.label.localeCompare(b.label) || a.id.localeCompare(b.id))
    .map((s, i) => ({
      chartKey: `v${i}`,
      id: s.id,
      label: s.label,
      axis: s.kind === "host" || s.id === "host" ? HOST_AXIS : SERVICE_AXIS,
    }));
}

function needsSplitAxes(series: MetricsSeries[]): boolean {
  const hasHost = series.some((s) => s.kind === "host" || s.id === "host");
  const hasService = series.some((s) => s.kind !== "host" && s.id !== "host");
  return hasHost && hasService;
}

/** Coerce JSON numbers so stringy samples still plot. */
export function pointValue(
  point: MetricsSeries["points"][0],
  metric: RuntimeMetricId,
): number | null {
  return runtimePointValue(point, metric);
}

export function buildPerServiceRows(
  series: MetricsSeries[],
  plots: PlotSeries[],
  metric: RuntimeMetricId,
): ChartRow[] {
  const keyed = plots.map((p) => ({
    key: p.chartKey,
    points: timedPointsForSeries(
      series.find((s) => s.id === p.id),
      metric,
    ),
  }));
  return mergeTimedRows(keyed) as ChartRow[];
}

function buildAggregateRows(
  series: MetricsSeries[],
  metric: RuntimeMetricId,
): ChartRow[] {
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
  const points: TimedValue[] = [...byTime.entries()].map(([t, vals]) => ({
    ts: toEpochMs(t) ?? 0,
    t,
    value: vals.reduce((a, b) => a + b, 0) / vals.length,
  }));
  return mergeTimedRows([{ key: "aggregate", points }]) as ChartRow[];
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

function formatAxisTick(value: number, unit: RuntimeUnit): string {
  if (unit === "bytes") return formatRuntimeValue(value, "bytes");
  if (unit === "seconds") return formatRuntimeValue(value, "seconds");
  return String(value);
}
