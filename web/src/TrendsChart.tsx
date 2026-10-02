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

type ChartRow = { t: string; label: string; [id: string]: string | number | null };

export function TrendsChart(props: {
  series: MetricsSeries[];
  metric: MetricKind;
  aggregate: boolean;
}) {
  const rows = props.aggregate
    ? buildAggregateRows(props.series, props.metric)
    : buildPerServiceRows(props.series, props.metric);
  const keys = props.aggregate
    ? ["aggregate"]
    : props.series.map((s) => s.id);
  const labels = props.aggregate
    ? { aggregate: "Average" }
    : Object.fromEntries(props.series.map((s) => [s.id, s.label]));

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
            tick={{ fill: "var(--muted)", fontSize: 11 }}
            unit="%"
            width={48}
            domain={[0, "auto"]}
          />
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
          {keys.map((key, i) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={COLORS[i % COLORS.length]}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function pointValue(point: MetricsSeries["points"][0], metric: MetricKind): number | null {
  const raw = metric === "cpu" ? point.cpu_percent : point.memory_used_percent;
  return typeof raw === "number" && Number.isFinite(raw) ? raw : null;
}

function buildPerServiceRows(series: MetricsSeries[], metric: MetricKind): ChartRow[] {
  const byTime = new Map<string, ChartRow>();
  for (const s of series) {
    for (const p of s.points) {
      const row = byTime.get(p.t) ?? { t: p.t, label: shortTime(p.t) };
      row[s.id] = pointValue(p, metric);
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
