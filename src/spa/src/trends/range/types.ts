export type RangeMode = "preset" | "custom" | "absolute";
export type DurationUnit = "minutes" | "hours" | "days";

export type TrendsRangeState = {
  mode: RangeMode;
  windowSec: number;
  customAmount: number;
  customUnit: DurationUnit;
  startLocal: string;
  endLocal: string;
};

export type MetricsQueryOpts = {
  window: number;
  start?: string;
  end?: string;
};

export const FALLBACK_MAX_DAYS = 30;
export const MIN_WINDOW_SEC = 60;
