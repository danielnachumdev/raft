import { useMemo, useState } from "react";
import {
  ChartHoverHighlight,
  eventKindHover,
  seriesHover,
  type HoverGroup,
} from "./chartHover";

/** Chart-local hover: enter a mark to group-highlight; leave the chart to clear. */
export function useChartHover(): {
  highlight: ChartHoverHighlight;
  hoverSeries: (id: string) => void;
  hoverEventKind: (kind: string) => void;
  clearHover: () => void;
} {
  const [hover, setHover] = useState<HoverGroup | null>(null);
  const highlight = useMemo(() => new ChartHoverHighlight(hover), [hover]);
  return {
    highlight,
    hoverSeries: (id: string) => setHover(seriesHover(id)),
    hoverEventKind: (kind: string) => setHover(eventKindHover(kind)),
    clearHover: () => setHover(null),
  };
}
