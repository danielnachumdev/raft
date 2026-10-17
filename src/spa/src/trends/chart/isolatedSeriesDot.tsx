import type { ReactElement } from "react";
import { isIsolatedSeriesPoint } from "./isolatedSeriesPoint";

const DOT_R = 3.5;

export type SeriesDotProps = {
  cx?: number;
  cy?: number;
  index?: number;
  stroke?: string;
};

/** Recharts ``dot`` renderer: circle only for points with no line siblings. */
export function isolatedSeriesDot(
  rows: ReadonlyArray<Record<string, unknown>>,
  dataKey: string,
  opts: { opacity?: number; onHover?: () => void } = {},
): (props: SeriesDotProps) => ReactElement<SVGElement> {
  const opacity = opts.opacity ?? 1;
  return (props) => {
    const { cx, cy, index = -1, stroke } = props;
    if (
      cx == null ||
      cy == null ||
      !isIsolatedSeriesPoint(rows, dataKey, index)
    ) {
      return <g />;
    }
    return (
      <circle
        cx={cx}
        cy={cy}
        r={DOT_R}
        fill={stroke}
        stroke={stroke}
        fillOpacity={opacity}
        strokeOpacity={opacity}
        style={{ cursor: "pointer" }}
        onMouseEnter={opts.onHover}
      />
    );
  };
}
