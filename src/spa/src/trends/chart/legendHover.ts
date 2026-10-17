import type { ChartHoverHighlight } from "./chartHover";

/** Legend payload fields we read for series hover / label dimming. */
export type LegendHoverEntry = {
  dataKey?: unknown;
  value?: unknown;
};

/** Resolve the plot ``dataKey`` from a Recharts legend payload item. */
export function legendSeriesId(entry: LegendHoverEntry): string | null {
  return typeof entry.dataKey === "string" ? entry.dataKey : null;
}

/** Display label for a legend item (chartKey → human label). */
export function legendItemLabel(
  value: unknown,
  entry: LegendHoverEntry,
  labels: Record<string, string>,
): string {
  const id = legendSeriesId(entry);
  if (id && labels[id]) return labels[id];
  if (typeof value === "string" && labels[value]) return labels[value];
  if (typeof value === "string") return value;
  if (typeof entry.value === "string") return entry.value;
  return id ?? "";
}

/** Match trendline dimming when a series (or event) is hovered. */
export function legendItemOpacity(
  entry: LegendHoverEntry,
  highlight: ChartHoverHighlight,
): number {
  const id = legendSeriesId(entry);
  if (id === null) return 1;
  return highlight.lineOpacity(id);
}
