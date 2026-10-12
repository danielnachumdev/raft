import { fromDatetimeLocal } from "./datetime.ts";
import type { MetricsQueryOpts, TrendsRangeState } from "./types.ts";

export function toQuery(
  state: TrendsRangeState,
  nowMs: number = Date.now(),
): MetricsQueryOpts {
  if (state.mode !== "absolute") return { window: state.windowSec };
  const endMs = fromDatetimeLocal(state.endLocal) ?? nowMs;
  const startMs =
    fromDatetimeLocal(state.startLocal) ?? endMs - state.windowSec * 1000;
  return {
    window: state.windowSec,
    start: new Date(startMs).toISOString(),
    end: new Date(endMs).toISOString(),
  };
}

export function metricsCacheKey(opts: MetricsQueryOpts): string {
  if (opts.start || opts.end) return `abs:${opts.start ?? ""}:${opts.end ?? ""}`;
  return `win:${opts.window}`;
}

export function isLiveQuery(
  opts: MetricsQueryOpts,
  nowMs: number = Date.now(),
): boolean {
  if (isRollingWindow(opts)) return true;
  const end = Date.parse(opts.end ?? "");
  if (!Number.isFinite(end)) return true;
  return nowMs - end < 120_000;
}

/** Lookback (preset / custom duration) — no pinned start/end. */
export function isRollingWindow(opts: MetricsQueryOpts): boolean {
  return !opts.start && !opts.end;
}
