import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { GraphEvent, MetricsSeries } from "./api";
import { GraphEventMarkers } from "./GraphEventMarkers";
import {
  eventsForSeries,
  seriesForEventFilter,
  shortTime,
  withEventRows,
} from "./graphEvents";
import {
  formatRuntimeValue,
  runtimePointValue,
  yAxisUnit,
  type RuntimeMetricId,
  type RuntimeUnit,
} from "./runtimeMetrics";

const COLORS = [
  "#0f6b5c",
  "#b45309",
  "#0e7490",
  "#9a3412",
  "#166534",
  "#44403c",
  "#a16207",
  "#1e3a5f",
];

const HOST_AXIS = "host";
const SERVICE_AXIS = "service";

type ChartRow = { t: string; label: string; [key: string]: string | number | null };

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
  aggregate: boolean;
  aggregateLabel?: string;
  events?: GraphEvent[];
  /** Full window series — used to map group charts back to deploy services. */
  allSeries?: MetricsSeries[];
}) {
  const avgLabel = props.aggregateLabel ?? "Average";
  const eventSeries = seriesForEventFilter(
    props.allSeries ?? props.series,
    props.series,
  );
  const markers = eventsForSeries(props.events, eventSeries);
  const plots = props.aggregate ? [] : toPlotSeries(props.series);
  const baseRows = props.aggregate
    ? buildAggregateRows(props.series, props.metric)
    : buildPerServiceRows(props.series, plots, props.metric);
  const rows = withEventRows(baseRows, markers, (t, label) => ({ t, label }));
  const labels = props.aggregate
    ? { aggregate: avgLabel }
    : Object.fromEntries(plots.map((p) => [p.chartKey, p.label]));
  const splitAxes = !props.aggregate && needsSplitAxes(props.series);
  const axisUnit = yAxisUnit(props.unit);

  if (!rows.length) {
    return null;
  }

  return (
    <div className="trends-chart" role="img" aria-label="Resource trend chart">
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" />
          <XAxis
            dataKey="t"
            tick={{ fill: "var(--muted)", fontSize: 11 }}
            minTickGap={28}
            tickFormatter={shortTime}
          />
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
              return row?.t ? formatTime(row.t) : "";
            }}
            formatter={(value: number | string, name: string) => [
              formatRuntimeValue(Number(value), props.unit),
              labels[name] ?? name,
            ]}
            itemSorter={tooltipItemSortKey}
          />
          <Legend formatter={(value) => labels[value] ?? value} />
          <GraphEventMarkers events={markers} />
          {props.aggregate ? (
            <Line
              type="monotone"
              dataKey="aggregate"
              name={avgLabel}
              yAxisId={SERVICE_AXIS}
              stroke={COLORS[0]}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
              connectNulls
              xAxisId={0}
            />
          ) : (
            plots.map((plot, i) => (
              <Line
                key={plot.chartKey}
                type="monotone"
                dataKey={plot.chartKey}
                name={plot.label}
                yAxisId={splitAxes ? plot.axis : SERVICE_AXIS}
                stroke={COLORS[i % COLORS.length]}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
                connectNulls
                xAxisId={0}
              />
            ))
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Lodash sortBy key: abs(value) desc, then label asc. */
export function tooltipItemSortKey(item: {
  value?: number | string | Array<number | string>;
  name?: number | string;
}): string {
  const raw = Array.isArray(item.value) ? item.value[0] : item.value;
  const n = Math.abs(Number(raw));
  const mag = Number.isFinite(n) ? n : -1;
  const rank = String(1_000_000_000 - Math.round(mag * 1000)).padStart(12, "0");
  return `${rank}\0${String(item.name ?? "")}`;
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
  const byId = new Map(plots.map((p) => [p.id, p.chartKey]));
  const byTime = new Map<string, ChartRow>();
  for (const s of series) {
    const key = byId.get(s.id);
    if (!key) continue;
    for (const p of s.points) {
      const row = byTime.get(p.t) ?? { t: p.t, label: shortTime(p.t) };
      row[key] = pointValue(p, metric);
      byTime.set(p.t, row);
    }
  }
  return [...byTime.values()].sort((a, b) => a.t.localeCompare(b.t));
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
  return [...byTime.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([t, vals]) => ({
      t,
      label: shortTime(t),
      aggregate: vals.reduce((a, b) => a + b, 0) / vals.length,
    }));
}

function formatAxisTick(value: number, unit: RuntimeUnit): string {
  if (unit === "bytes") return formatRuntimeValue(value, "bytes");
  if (unit === "seconds") return formatRuntimeValue(value, "seconds");
  return String(value);
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}
