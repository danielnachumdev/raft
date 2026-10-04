import type { GraphEvent, MetricsSeries } from "../shared/api";
import { TrendsChart } from "./TrendsChart";
import type { RuntimeMetricDef } from "./runtimeMetrics";
import { isSingleLineAvg, type SeriesViewMode } from "./trendsView";

export function TrendsBody(props: {
  error: string | null;
  series: MetricsSeries[];
  visible: MetricsSeries[];
  metric: RuntimeMetricDef;
  windowSec: number;
  viewMode: SeriesViewMode;
  groupMode: boolean;
  events: GraphEvent[];
}) {
  if (props.error) {
    return (
      <p className="error" role="alert">
        {props.error}
      </p>
    );
  }
  if (props.series.length === 0) {
    return (
      <p className="muted">
        No metrics samples yet. The controller writes{" "}
        <code>state/metrics/resources.jsonl</code> on its metrics interval.
      </p>
    );
  }
  if (props.visible.length === 0) {
    return (
      <p className="muted">
        {props.groupMode
          ? "Select at least one group to plot."
          : "Select at least one service to plot."}
      </p>
    );
  }
  return (
    <TrendsChart
      series={props.visible}
      metric={props.metric.id}
      unit={props.metric.unit}
      windowSeconds={props.windowSec}
      aggregate={isSingleLineAvg(props.viewMode)}
      aggregateLabel="Average"
      events={props.events}
      allSeries={props.series}
    />
  );
}
