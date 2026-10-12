import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, YAxis } from "recharts";
import type { GraphEvent } from "../../shared/api";
import {
  clipRowsToDomain,
  formatTooltipTime,
  windowDomain,
} from "../chart/chartTimeScale";
import { graphEventMarkers } from "../chart/GraphEventMarkers";
import {
  formatMetricTick,
  formatMetricValue,
  yAxisSuffix,
} from "../metricTypes";
import type { RuntimeMetricDef } from "../runtimeMetrics";
import { timeScaleXAxis } from "../chart/TimeScaleXAxis";
import { useChartHover } from "../chart/useChartHover";
import type { ChartRow } from "./runtimeTrendsPoll";
import "../chart/TrendsChart.css";
const SERIES_ID = "value";

export function ServiceRuntimeChart(props: {
  rows: ChartRow[];
  metric: RuntimeMetricDef;
  windowSec: number;
  rangeEndMs?: number;
  events: GraphEvent[];
}) {
  const hover = useChartHover();
  const suffix = yAxisSuffix(props.metric.typeId);
  const endMs = props.rangeEndMs ?? Date.now();
  const rows = clipRowsToDomain(
    props.rows,
    windowDomain(props.windowSec, endMs),
  );
  return (
    <div
      className="trends-chart"
      role="img"
      aria-label={`${props.metric.label} trend chart`}
      onMouseLeave={hover.clearHover}
    >
      <ResponsiveContainer width="100%" height={260}>
        <LineChart
          data={rows}
          margin={{ top: 8, right: 12, left: 0, bottom: 0 }}
        >
          <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" />
          {timeScaleXAxis(props.windowSec, endMs)}
          <YAxis
            tick={{ fill: "var(--muted)", fontSize: 11 }}
            unit={suffix || undefined}
            width={56}
            domain={[0, "auto"]}
            tickFormatter={(v: number) =>
              formatMetricTick(v, props.metric.typeId)
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
              formatMetricValue(Number(value), props.metric.typeId),
              props.metric.label,
            ]}
          />
          <Line
            type="monotone"
            dataKey={SERIES_ID}
            name={props.metric.label}
            stroke="#0f6b5c"
            strokeWidth={hover.highlight.lineStrokeWidth(SERIES_ID)}
            strokeOpacity={hover.highlight.lineOpacity(SERIES_ID)}
            dot={false}
            activeDot={false}
            isAnimationActive={false}
            connectNulls={false}
            onMouseEnter={() => hover.hoverSeries(SERIES_ID)}
          />
          {graphEventMarkers(props.events, {
            highlight: hover.highlight,
            onHoverKind: hover.hoverEventKind,
          })}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
