/** How a chart should present an in-flight metrics fetch. */
export type ChartLoadState = "idle" | "cold" | "refresh";

/**
 * Map fetch busy + whether any prior samples are on screen to a load mode.
 * ``refresh`` keeps the last chart visible under an overlay spinner.
 */
export function chartLoadState(busy: boolean, hasData: boolean): ChartLoadState {
  if (!busy) return "idle";
  return hasData ? "refresh" : "cold";
}
