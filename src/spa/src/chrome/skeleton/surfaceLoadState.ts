/** How a known-layout surface should present an in-flight fetch. */
export type SurfaceLoadState = "idle" | "cold" | "refresh";

/**
 * Map fetch busy + whether prior data is on screen to a load mode.
 * ``refresh`` keeps the last good UI (no skeleton flash); ``cold`` is first
 * paint / empty→loading where a skeleton belongs.
 */
export function surfaceLoadState(
  busy: boolean,
  hasData: boolean,
): SurfaceLoadState {
  if (!busy) return "idle";
  return hasData ? "refresh" : "cold";
}

/** True only when a skeleton should replace the body (first paint / no data). */
export function showSkeleton(busy: boolean, hasData: boolean): boolean {
  return surfaceLoadState(busy, hasData) === "cold";
}
