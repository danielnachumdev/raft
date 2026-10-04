import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  YAxis,
} from "recharts";
import type { GraphEvent } from "../shared/api";
import {
  formatTooltipTime,
} from "../trends/chartTimeScale";
import { graphEventMarkers } from "../trends/GraphEventMarkers";
import {
  formatRuntimeValue,
  type RuntimeMetricDef,
  yAxisUnit,
} from "../trends/runtimeMetrics";
import { timeScaleXAxis } from "../trends/TimeScaleXAxis";
import type { ChartRow } from "./runtimeTrendsPoll";

export function ServiceRuntimeChart(props: {
  rows: ChartRow[];
  metric: RuntimeMetricDef;
  windowSec: number;
  events: GraphEvent[];
}) {
  const unit = yAxisUnit(props.metric.unit);
  return (
    <div
      className="trends-chart"
      role="img"
      aria-label={`${props.metric.label} trend chart`}
    >
      <ResponsiveContainer width="100%" height={260}>
        <LineChart
          data={props.rows}
          margin={{ top: 8, right: 12, left: 0, bottom: 0 }}
        >
          <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" />
          {timeScaleXAxis(props.windowSec)}
          <YAxis
            tick={{ fill: "var(--muted)", fontSize: 11 }}
            unit={unit || undefined}
            width={56}
            domain={[0, "auto"]}
            tickFormatter={(v: number) =>
              props.metric.unit === "bytes"
                ? formatRuntimeValue(v, "bytes")
                : String(v)
            }
          />
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
            formatter={(value: number | string) => [
              formatRuntimeValue(Number(value), props.metric.unit),
              props.metric.label,
            ]}
          />
          <Line
            type="monotone"
            dataKey="value"
            name={props.metric.label}
            stroke="#0f6b5c"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
            connectNulls={false}
          />
          {graphEventMarkers(props.events)}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
