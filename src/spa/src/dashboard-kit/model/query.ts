import {
  planesForGraphs,
  type DashboardData,
  type GraphView,
  graphView,
} from "../../trends/dashboard/model/fanout.ts";
import type {
  TrendsGraphDraft,
} from "../../trends/dashboard/model/types.ts";
import type { SeriesViewMode } from "../../trends/panel/trendsView.ts";
import type { MetricPlane, RuntimeMetricId } from "../../trends/runtimeMetrics.ts";
import type { MetricsPanelQuery, PanelKind } from "./types.ts";

/** Lift a Trends graph draft into the kit query model. */
export function panelQueryFromGraph(
  graph: Pick<TrendsGraphDraft, "metricIds" | "viewMode" | "selected">,
): MetricsPanelQuery {
  return {
    metricIds: [...graph.metricIds],
    viewMode: graph.viewMode,
    selected: graph.selected === null ? null : [...graph.selected],
  };
}

/** Apply a kit query back onto a graph draft (timeseries only). */
export function graphFromPanelQuery(
  query: MetricsPanelQuery,
  base: TrendsGraphDraft,
): TrendsGraphDraft {
  return {
    ...base,
    metricIds: query.metricIds as RuntimeMetricId[],
    viewMode: query.viewMode as SeriesViewMode,
    selected: query.selected === null ? null : [...query.selected],
  };
}

/**
 * Union of metric planes needed by the queries — one fetch per plane for the
 * shared dashboard range (same rule as #238 fan-out).
 */
export function planesForQueries(
  queries: MetricsPanelQuery[],
): MetricPlane[] {
  const graphs = queries.map((q) => ({
    title: "",
    metricIds: q.metricIds as RuntimeMetricId[],
    viewMode: (q.viewMode || "per_service") as SeriesViewMode,
    selected: q.selected,
    size: "half" as const,
  }));
  return planesForGraphs(graphs);
}

/** Resolve one panel query against the shared plane payload. */
export function resolvePanelView(
  query: MetricsPanelQuery,
  data: DashboardData,
): GraphView {
  return graphView(
    {
      title: "",
      metricIds: query.metricIds as RuntimeMetricId[],
      viewMode: query.viewMode as SeriesViewMode,
      selected: query.selected,
      size: "half",
    },
    data,
  );
}

/** v1 only ships timeseries; other kinds are reserved extension points. */
export function isRenderableKind(kind: PanelKind | undefined): boolean {
  return kind === undefined || kind === "timeseries";
}

export function defaultPanelKind(): PanelKind {
  return "timeseries";
}
