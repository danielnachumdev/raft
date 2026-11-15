import type { ReactElement } from "react";
import { isolatedPointIndices } from "./isolatedSeriesPoint";

const DOT_R = 3.5;

export type SeriesDotProps = {
  cx?: number;
  cy?: number;
  index?: number;
  stroke?: string;
};

export type SeriesDot = false | ((props: SeriesDotProps) => ReactElement | null);

/**
 * Recharts ``dot`` for a line: circles only for points with no line siblings.
 * ``false`` when the series has none, so Recharts skips the dots layer; the
 * renderer returns ``null`` (no DOM) for every connected point.
 */
export function isolatedSeriesDot(
  rows: ReadonlyArray<Record<string, unknown>>,
  dataKey: string,
  opts: { opacity?: number; onHover?: () => void } = {},
): SeriesDot {
  const isolated = isolatedPointIndices(rows, dataKey);
  if (isolated.size === 0) return false;
  const opacity = opts.opacity ?? 1;
  return (props) => {
    const { cx, cy, index = -1, stroke } = props;
    if (cx == null || cy == null || !isolated.has(index)) return null;
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
