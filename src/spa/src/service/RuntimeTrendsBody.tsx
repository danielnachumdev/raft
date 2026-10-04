import type { GraphEvent, MetricsSeries } from "../shared/api";
import type { RuntimeMetricDef } from "../trends/runtimeMetrics";
import { ServiceRuntimeChart } from "./ServiceRuntimeChart";
import type { ChartRow } from "./runtimeTrendsPoll";

export function RuntimeTrendsBody(props: {
  error: string | null;
  showCold: boolean;
  series: MetricsSeries | null;
  rows: ChartRow[];
  metric: RuntimeMetricDef;
  windowSec: number;
  events: GraphEvent[];
}) {
  if (props.error) {
    return (
      <p className="error" role="alert">
        {props.error}
      </p>
    );
  }
  if (props.showCold) {
    return (
      <div className="trends-loading" role="status" aria-busy="true">
        <span className="spinner" aria-hidden="true" />
        <p>Loading metrics…</p>
      </div>
    );
  }
  if (!props.series || props.series.points.length === 0) {
    return (
      <p className="muted">
        No metrics samples yet for this service. The controller writes{" "}
        <code>state/metrics/resources.jsonl</code> on its metrics interval.
      </p>
    );
  }
  if (props.rows.every((r) => r.value === null)) {
    return (
      <p className="muted">
        No samples for {props.metric.label} in this window (older JSONL may
        omit newer Runtime fields).
      </p>
    );
  }
  return (
    <ServiceRuntimeChart
      rows={props.rows}
      metric={props.metric}
      windowSec={props.windowSec}
      events={props.events}
    />
  );
}
