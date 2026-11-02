import type { GraphEvent, MetricsSeries } from "../../shared/api";
import { TrendsChart } from "../chart/TrendsChart";
import type { RuntimeMetricDef } from "../runtimeMetrics";
import {
  isSingleLineAvg,
  seriesWithData,
  type SeriesViewMode,
} from "./trendsView";

export function TrendsBody(props: {
  error: string | null;
  series: MetricsSeries[];
  visible: MetricsSeries[];
  metrics: RuntimeMetricDef[];
  windowSec: number;
  rangeEndMs?: number;
  viewMode: SeriesViewMode;
  groupMode: boolean;
  events: GraphEvent[];
  height?: number;
  palette?: Map<string, number>;
}) {
  if (props.error) {
    return (
      <p className="error" role="alert">
        {props.error}
      </p>
    );
  }
  if (props.metrics.length === 0) {
    return (
      <p className="muted">Select at least one metric to plot.</p>
    );
  }
  if (seriesWithData(props.series, props.metrics).length === 0) {
    return (
      <p className="muted">No data for the selected time period.</p>
    );
  }
  if (props.visible.length === 0) {
    return (
      <p className="muted">
        {props.groupMode
          ? "No data for the selected groups in this range."
          : "No data for the selected services in this range."}
      </p>
    );
  }
  return (
    <TrendsChart
      series={props.visible}
      metrics={props.metrics}
      windowSeconds={props.windowSec}
      rangeEndMs={props.rangeEndMs}
      aggregate={isSingleLineAvg(props.viewMode)}
      events={props.events}
      allSeries={props.series}
      height={props.height}
      palette={props.palette}
    />
  );
}
