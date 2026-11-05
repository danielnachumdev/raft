import type { ReactNode } from "react";
import { ChartPlotSkeleton } from "../../../shared/chrome/skeleton";
import { chartLoadState } from "./chartLoadState";
import "./ChartLoadingOverlay.css";

/**
 * Cold load: plot skeleton (card header stays real). Refresh: keep chart +
 * dimming spinner overlay.
 */
export function ChartLoadingOverlay(props: {
  busy: boolean;
  hasData: boolean;
  label?: string;
  children?: ReactNode;
}) {
  const mode = chartLoadState(props.busy, props.hasData);
  const label = props.label ?? (mode === "refresh" ? "Updating chart" : "Loading chart");
  if (mode === "cold") {
    return <ChartPlotSkeleton label={label} />;
  }
  return (
    <div className="chart-loading-host">
      {props.children}
      {mode === "refresh" ? (
        <div
          className="chart-loading is-overlay"
          role="status"
          aria-busy="true"
          aria-label={label}
        >
          <span className="spinner" aria-hidden="true" />
        </div>
      ) : null}
    </div>
  );
}
