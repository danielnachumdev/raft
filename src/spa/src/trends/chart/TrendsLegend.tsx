import type { ReactElement } from "react";
import { Legend } from "recharts";
import type { ChartHoverHighlight } from "./chartHover";
import {
  legendItemLabel,
  legendItemOpacity,
  legendSeriesId,
} from "./legendHover";

/**
 * Direct ``Legend`` child for LineChart (wrapper components are skipped).
 * Hovering a label highlights the matching series via ``onHoverSeries``.
 */
export function trendsLegend(args: {
  labels: Record<string, string>;
  highlight: ChartHoverHighlight;
  onHoverSeries: (id: string) => void;
}): ReactElement {
  return (
    <Legend
      onMouseEnter={(item) => {
        const id = legendSeriesId(item);
        if (id) args.onHoverSeries(id);
      }}
      formatter={(value, entry) => (
        <span style={{ opacity: legendItemOpacity(entry, args.highlight) }}>
          {legendItemLabel(value, entry, args.labels)}
        </span>
      )}
    />
  );
}
