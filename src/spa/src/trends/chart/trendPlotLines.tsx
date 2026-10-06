import type { ReactElement } from "react";
import { Line } from "recharts";
import type { ChartHoverHighlight } from "./chartHover";

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

export type TrendPlot = {
  chartKey: string;
  label: string;
  axis: string;
};

/** Direct ``Line`` children for LineChart (wrapper components are skipped). */
export function trendPlotLines(args: {
  aggregate: boolean;
  avgLabel: string;
  plots: TrendPlot[];
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
      i,
      args,
    ),
  );
}

function hoverLine(
  id: string,
  name: string,
  yAxisId: string,
  colorIndex: number,
  args: {
    highlight: ChartHoverHighlight;
    onHoverSeries: (id: string) => void;
  },
): ReactElement {
  return (
    <Line
      key={id}
      type="monotone"
      dataKey={id}
      name={name}
      yAxisId={yAxisId}
      stroke={COLORS[colorIndex % COLORS.length]}
      strokeWidth={args.highlight.lineStrokeWidth(id)}
      strokeOpacity={args.highlight.lineOpacity(id)}
      dot={false}
      activeDot={false}
      isAnimationActive={false}
      connectNulls={false}
      onMouseEnter={() => args.onHoverSeries(id)}
    />
  );
}
