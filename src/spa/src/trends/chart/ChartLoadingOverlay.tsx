import type { ReactNode } from "react";
import { chartLoadState } from "./chartLoadState";
import "./ChartLoadingOverlay.css";

/** Centered spinner for cold load, or dimming overlay while refreshing. */
export function ChartLoadingOverlay(props: {
  busy: boolean;
  hasData: boolean;
  label?: string;
  children?: ReactNode;
}) {
  const mode = chartLoadState(props.busy, props.hasData);
  const label = props.label ?? (mode === "refresh" ? "Updating chart" : "Loading chart");
  if (mode === "cold") {
    return (
      <div
        className="chart-loading is-cold"
        role="status"
        aria-busy="true"
        aria-label={label}
      >
        <span className="spinner" aria-hidden="true" />
      </div>
    );
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
