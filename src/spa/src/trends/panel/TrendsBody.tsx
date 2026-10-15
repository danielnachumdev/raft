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
    const hasHttp = props.metrics.some((m) => m.plane === "http");
    const hasRes = props.metrics.some((m) => m.plane === "resources");
    const files = [
      hasRes ? "state/metrics/resources.jsonl" : null,
      hasHttp ? "state/metrics/http.jsonl" : null,
    ].filter(Boolean);
    return (
      <p className="muted">
        No metrics samples yet. The controller writes{" "}
        <code>{files.join(" / ")}</code> on its metrics interval.
      </p>
    );
  }
  if (props.visible.length === 0) {
    return (
      <p className="muted">
        {props.groupMode
          ? "No samples for the selected groups in this range."
          : "No samples for the selected services in this range."}
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
