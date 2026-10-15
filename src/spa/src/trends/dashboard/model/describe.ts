import type { SeriesViewMode } from "../../panel/trendsView.ts";
import type { HeadlineHow } from "./headline.ts";
import type { TrendsGraphDraft } from "./types.ts";

export const VIEW_MODE_LABELS: Record<SeriesViewMode, string> = {
  per_service: "Per service",
  per_group: "Per group",
  avg_all: "Average of all",
  avg_group: "Average per group",
};

export const HEADLINE_LABELS: Record<HeadlineHow, string> = {
  max: "peak now",
  total: "total now",
  avg: "avg now",
};

/** Muted line under a graph title, e.g. "Per service · 2 of 5 services". */
export function graphSubtitle(
  graph: Pick<TrendsGraphDraft, "viewMode" | "selected">,
  activeCount: number,
  pickerCount: number,
  groupMode: boolean,
): string {
  const noun = groupMode ? "group" : "service";
  const mode = VIEW_MODE_LABELS[graph.viewMode];
  if (graph.selected === null) return `${mode} · all ${noun}s`;
  const plural = pickerCount === 1 ? noun : `${noun}s`;
  return `${mode} · ${activeCount} of ${pickerCount} ${plural}`;
}
