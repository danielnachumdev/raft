/** Eager public surface for Trends lookback / absolute range helpers. */

export {
  applyAbsoluteTimes,
  applyCustomDuration,
  customSeconds,
  defaultRangeState,
  presetSelectValue,
  selectRangeKind,
} from "./apply.ts";
export {
  availableFromMs,
  clampWindowSec,
  maxWindowSec,
  tooOldMessage,
} from "./clamp.ts";
export { fromDatetimeLocal, toDatetimeLocal } from "./datetime.ts";
export {
  isLiveQuery,
  isRollingWindow,
  metricsCacheKey,
  toQuery,
} from "./query.ts";
export type {
  DurationUnit,
  MetricsQueryOpts,
  RangeMode,
  TrendsRangeState,
} from "./types.ts";
export { parseRange } from "./validate.ts";
