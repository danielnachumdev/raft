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
import type { MetricsSeries } from "./api";

export type MetricKind = "cpu" | "memory";

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
  metric: MetricKind;
  aggregate: boolean;
}) {
  const plots = props.aggregate ? [] : toPlotSeries(props.series);
  const rows = props.aggregate
    ? buildAggregateRows(props.series, props.metric)
    : buildPerServiceRows(props.series, plots, props.metric);
  const labels = props.aggregate
    ? { aggregate: "Average" }
    : Object.fromEntries(plots.map((p) => [p.chartKey, p.label]));
  const splitAxes = !props.aggregate && needsSplitAxes(props.series);

  if (!rows.length) {
    return null;
  }

  return (
    <div className="trends-chart" role="img" aria-label="Resource trend chart">
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" />
          <XAxis
            dataKey="label"
            tick={{ fill: "var(--muted)", fontSize: 11 }}
            minTickGap={28}
          />
          <YAxis
            yAxisId={SERVICE_AXIS}
            tick={{ fill: "var(--muted)", fontSize: 11 }}
            unit="%"
            width={48}
            domain={[0, "auto"]}
          />
          {splitAxes ? (
            <YAxis
              yAxisId={HOST_AXIS}
              orientation="right"
              tick={{ fill: "var(--muted)", fontSize: 11 }}
              unit="%"
              width={48}
              domain={[0, "auto"]}
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
              `${Number(value).toFixed(1)}%`,
              labels[name] ?? name,
            ]}
          />
          <Legend formatter={(value) => labels[value] ?? value} />
          {props.aggregate ? (
            <Line
              type="monotone"
              dataKey="aggregate"
              name="Average"
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

function toPlotSeries(series: MetricsSeries[]): PlotSeries[] {
  return series.map((s, i) => ({
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
  metric: MetricKind,
): number | null {
  const raw: unknown =
    metric === "cpu" ? point.cpu_percent : point.memory_used_percent;
  if (typeof raw === "number" && Number.isFinite(raw)) return raw;
  if (typeof raw === "string" && raw.trim()) {
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

export function buildPerServiceRows(
  series: MetricsSeries[],
  plots: PlotSeries[],
  metric: MetricKind,
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

function buildAggregateRows(series: MetricsSeries[], metric: MetricKind): ChartRow[] {
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

function shortTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}
