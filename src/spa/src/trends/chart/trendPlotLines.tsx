import type { ReactElement } from "react";
import { Line } from "recharts";
import type { ChartHoverHighlight } from "./chartHover";
import { isolatedSeriesDot } from "./isolatedSeriesDot";

// Distinct hues that stay legible on both the light and dark panel colors.
const COLORS = [
  "#0f8a74",
  "#d9622b",
  "#4c6fd6",
  "#b0408a",
  "#7a9a1f",
  "#c79a12",
  "#0e8fb0",
  "#8a5cc7",
];

export type TrendPlot = {
  chartKey: string;
  label: string;
  axis: string;
  /** Fixed palette slot (dashboard-wide); defaults to plot order. */
  colorIndex?: number;
  /** Second metric of a series on a two-metric graph. */
  dashed?: boolean;
};

/** Direct ``Line`` children for LineChart (wrapper components are skipped). */
export function trendPlotLines(args: {
  aggregate: boolean;
  avgLabel: string;
  plots: TrendPlot[];
  rows: ReadonlyArray<Record<string, unknown>>;
  splitAxes: boolean;
  serviceAxis: string;
  highlight: ChartHoverHighlight;
  onHoverSeries: (id: string) => void;
}): ReactElement[] {
  if (args.aggregate) {
    return [hoverLine("aggregate", args.avgLabel, args.serviceAxis, 0, args)];
  }
  return args.plots.map((plot, i) =>
    hoverLine(
      plot.chartKey,
      plot.label,
      args.splitAxes ? plot.axis : args.serviceAxis,
      plot.colorIndex ?? i,
      args,
      plot.dashed,
    ),
  );
}

function hoverLine(
  id: string,
  name: string,
  yAxisId: string,
  colorIndex: number,
  args: {
    rows: ReadonlyArray<Record<string, unknown>>;
    highlight: ChartHoverHighlight;
    onHoverSeries: (id: string) => void;
  },
  dashed?: boolean,
): ReactElement {
  const opacity = args.highlight.lineOpacity(id);
  const onHover = () => args.onHoverSeries(id);
  return (
    <Line
      key={id}
      type="monotone"
      dataKey={id}
      name={name}
      yAxisId={yAxisId}
      stroke={COLORS[colorIndex % COLORS.length]}
      strokeDasharray={dashed ? "5 3" : undefined}
      strokeWidth={args.highlight.lineStrokeWidth(id)}
      strokeOpacity={opacity}
      dot={isolatedSeriesDot(args.rows, id, { opacity, onHover })}
      activeDot={false}
      isAnimationActive={false}
      connectNulls={false}
      onMouseEnter={onHover}
    />
  );
}
