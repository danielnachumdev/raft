/** Home-page Trends stay off the status-table critical path. */

export type TrendsDeferPhase = "blocked" | "scheduled" | "ready";

/**
 * After the first actionable status payload, Trends may schedule; it mounts
 * only once the idle/macrotask deferral has fired.
 */
export function trendsDeferPhase(
  hasStatusData: boolean,
  idleElapsed: boolean,
): TrendsDeferPhase {
  if (!hasStatusData) return "blocked";
  if (!idleElapsed) return "scheduled";
  return "ready";
}

/** Delay (ms) before mounting Trends once status has painted; null while blocked. */
export function trendsDeferDelayMs(hasStatusData: boolean): number | null {
  return hasStatusData ? 0 : null;
}
