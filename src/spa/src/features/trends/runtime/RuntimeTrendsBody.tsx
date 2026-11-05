import type { GraphEvent, MetricsSeries } from "../../../shared/api";
import { ChartLoadingOverlay } from "../chart/ChartLoadingOverlay";
import type { RuntimeMetricDef } from "../runtimeMetrics";
import { ServiceRuntimeChart } from "./ServiceRuntimeChart";
import type { ChartRow } from "./runtimeTrendsPoll";

export function RuntimeTrendsBody(props: {
  error: string | null;
  busy: boolean;
  series: MetricsSeries | null;
  rows: ChartRow[];
  metric: RuntimeMetricDef;
  windowSec: number;
  rangeEndMs?: number;
  events: GraphEvent[];
}) {
  if (props.error) {
    return (
      <p className="error" role="alert">
        {props.error}
      </p>
    );
  }
  const hasData = Boolean(props.series && props.series.points.length > 0);
  return (
    <ChartLoadingOverlay
      busy={props.busy}
      hasData={hasData}
      label={hasData ? "Updating metrics" : "Loading metrics"}
    >
      <RuntimeChartContent {...props} />
    </ChartLoadingOverlay>
  );
}

function RuntimeChartContent(props: {
  series: MetricsSeries | null;
  rows: ChartRow[];
  metric: RuntimeMetricDef;
  windowSec: number;
  rangeEndMs?: number;
  events: GraphEvent[];
}) {
  if (!props.series || props.series.points.length === 0) {
    return (
      <p className="muted">No data for the selected time period.</p>
    );
  }
  if (props.rows.every((r) => r.value === null)) {
    return (
      <p className="muted">
        No data for {props.metric.label} in this window.
      </p>
    );
  }
  return (
    <ServiceRuntimeChart
      rows={props.rows}
      metric={props.metric}
      windowSec={props.windowSec}
      rangeEndMs={props.rangeEndMs}
      events={props.events}
    />
  );
}
