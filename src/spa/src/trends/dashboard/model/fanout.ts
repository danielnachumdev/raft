import type {
  MetricsAvailable,
  MetricsSeries,
} from "../../../shared/api/index.ts";
import {
  metricsFromIds,
  planesForMetrics,
} from "../../panel/metricSelection.ts";
import {
  groupOptions,
  resolveVisibleSeries,
  seriesWithData,
  usesGroupPicker,
} from "../../panel/trendsView.ts";
import type { MetricPlane, RuntimeMetricDef } from "../../runtimeMetrics.ts";
import { reconcileSelection, staleSelectionMessage } from "./reconcile.ts";
import type { TrendsGraphDraft } from "./types.ts";

/** Shared data every graph on a dashboard reads from (one fetch per plane). */
export type DashboardData = {
  series: MetricsSeries[];
  available: MetricsAvailable[];
};

export type GraphView = {
  title: string;
  metrics: RuntimeMetricDef[];
  groupMode: boolean;
  pickerIds: string[];
  activeIds: string[];
  visible: MetricsSeries[];
  staleMessage: string | null;
};

const PLANE_ORDER: MetricPlane[] = ["resources", "http"];

/** Union of planes the graphs need; resources alone keeps the catalog warm. */
export function planesForGraphs(graphs: TrendsGraphDraft[]): MetricPlane[] {
  const want = new Set<MetricPlane>();
  for (const g of graphs) {
    for (const plane of planesForMetrics(metricsFromIds(g.metricIds))) {
      want.add(plane);
    }
  }
  const planes = PLANE_ORDER.filter((p) => want.has(p));
  return planes.length ? planes : ["resources"];
}

/** Resolve one graph against the shared dashboard data (client-side filter). */
export function graphView(graph: TrendsGraphDraft, data: DashboardData): GraphView {
  const metrics = metricsFromIds(graph.metricIds);
  const groupMode = usesGroupPicker(graph.viewMode);
  const pickerIds = pickerIdsFor(groupMode, data.available);
  const { selected, missingIds } = reconcileSelection(graph.selected, pickerIds);
  const activeIds = selected ?? pickerIds;
  const visible = resolveVisibleSeries({
    series: data.series,
    viewMode: graph.viewMode,
    selected,
    activeIds,
  });
  return {
    title: graphTitle(graph),
    metrics,
    groupMode,
    pickerIds,
    activeIds,
    visible: seriesWithData(visible, metrics),
    staleMessage: staleSelectionMessage(missingIds, groupMode),
  };
}

export function pickerIdsFor(
  groupMode: boolean,
  available: MetricsAvailable[],
): string[] {
  return groupMode
    ? groupOptions(available).map((g) => g.id)
    : available.map((a) => a.id);
}

/** Saved title, else metric labels (e.g. "Network RX · Network TX"). */
export function graphTitle(graph: Pick<TrendsGraphDraft, "title" | "metricIds">): string {
  if (graph.title.trim()) return graph.title.trim();
  const labels = metricsFromIds(graph.metricIds).map((m) => m.label);
  return labels.length ? labels.join(" · ") : "Untitled graph";
}
/** Stable color slot per series id so one service looks the same on every graph. */
export function seriesPalette(available: MetricsAvailable[]): Map<string, number> {
  const ids = [...available]
    .sort((a, b) => a.label.localeCompare(b.label) || a.id.localeCompare(b.id))
    .map((a) => a.id);
  const palette = new Map(ids.map((id, i) => [id, i]));
  groupOptions(available).forEach((g, i) => palette.set(`group:${g.id}`, i));
  return palette;
}
