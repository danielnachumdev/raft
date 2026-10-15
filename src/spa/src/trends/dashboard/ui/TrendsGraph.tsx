import { useMemo, type ReactNode } from "react";
import { FlashValue } from "../../../chrome/FlashValue";
import { formatMetricValue } from "../../metricTypes";
import { isSingleLineAvg } from "../../panel/trendsView";
import { TrendsBody } from "../../panel/TrendsBody";
import {
  graphSubtitle,
  graphView,
  HEADLINE_LABELS,
  headlineStat,
  type GraphView,
  type TrendsGraphDraft,
} from "../model/index.ts";
import type { DashboardMetrics } from "./useDashboardMetrics";
import "./TrendsGraph.css";

export const GRAPH_HEIGHT = 240;

/**
 * Reusable dashboard graph: config in, shared dashboard data in, card out.
 * Header chrome (menu, drag handle) is injected so previews stay bare.
 */
export function TrendsGraph(props: {
  config: TrendsGraphDraft;
  data: DashboardMetrics;
  palette: Map<string, number>;
  height?: number;
  leading?: ReactNode;
  actions?: ReactNode;
  onOpen?: () => void;
  className?: string;
}) {
  const { series, available } = props.data;
  const view = useMemo(
    () => graphView(props.config, { series, available }),
    [props.config, series, available],
  );
  const height = props.height ?? GRAPH_HEIGHT;
  return (
    <article
      className={`trends-graph ${props.className ?? ""}`}
      aria-label={view.title}
    >
      <header className="trends-graph-head">
        {props.leading}
        <GraphTitle config={props.config} view={view} onOpen={props.onOpen} />
        <GraphHeadline config={props.config} view={view} />
        {props.actions}
      </header>
      {view.staleMessage ? (
        <p className="muted trends-graph-stale" role="status">
          {view.staleMessage}
        </p>
      ) : null}
      <div className="trends-graph-body" style={{ minHeight: height }}>
        <GraphBody {...props} view={view} height={height} />
      </div>
    </article>
  );
}

function GraphTitle(props: {
  config: TrendsGraphDraft;
  view: GraphView;
  onOpen?: () => void;
}) {
  const { view } = props;
  const sub = graphSubtitle(
    props.config,
    view.activeIds.length,
    view.pickerIds.length,
    view.groupMode,
  );
  return (
    <div className="trends-graph-titles">
      {props.onOpen ? (
        <button
          type="button"
          className="trends-graph-title is-link"
          onClick={props.onOpen}
          title="Expand graph"
        >
          {view.title}
        </button>
      ) : (
        <h3 className="trends-graph-title">{view.title}</h3>
      )}
      <p className="muted trends-graph-sub">{sub}</p>
    </div>
  );
}

function GraphHeadline(props: { config: TrendsGraphDraft; view: GraphView }) {
  const stat = headlineStat(
    props.view.visible,
    props.view.metrics,
    isSingleLineAvg(props.config.viewMode),
  );
  if (!stat) return null;
  const text = formatMetricValue(stat.value, stat.typeId);
  const tip = `${stat.metrics.map((m) => m.label).join(" + ")} · latest sample`;
  return (
    <div className="trends-graph-stat" title={tip}>
      <FlashValue value={text}>
        <span className="trends-graph-stat-value">{text}</span>
      </FlashValue>
      <span className="trends-graph-stat-how">{HEADLINE_LABELS[stat.how]}</span>
    </div>
  );
}

function GraphBody(props: {
  config: TrendsGraphDraft;
  data: DashboardMetrics;
  palette: Map<string, number>;
  view: GraphView;
  height: number;
}) {
  const { data, view } = props;
  if (data.busy && data.series.length === 0) {
    return <div className="trends-graph-skeleton" role="status" aria-label="Loading graph" />;
  }
  return (
    <TrendsBody
      error={data.error}
      series={data.series}
      visible={view.visible}
      metrics={view.metrics}
      windowSec={data.windowSec}
      rangeEndMs={data.rangeEndMs}
      viewMode={props.config.viewMode}
      groupMode={view.groupMode}
      events={data.events}
      height={props.height}
      palette={props.palette}
    />
  );
}
