/** Lookback presets, custom duration, and absolute history range. */

import type { MetricsBounds } from "../shared/api.ts";
import { DEFAULT_RUNTIME_WINDOW, RUNTIME_WINDOWS } from "./runtimeMetrics.ts";

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

const FALLBACK_MAX_DAYS = 30;
const MIN_WINDOW_SEC = 60;

export function defaultRangeState(): TrendsRangeState {
  return {
    mode: "preset",
    windowSec: DEFAULT_RUNTIME_WINDOW,
    customAmount: 1,
    customUnit: "hours",
    startLocal: "",
    endLocal: "",
  };
}

export function customSeconds(amount: number, unit: DurationUnit): number {
  const n = Number.isFinite(amount) ? Math.max(0, amount) : 0;
  if (unit === "minutes") return Math.round(n * 60);
  if (unit === "hours") return Math.round(n * 3600);
  return Math.round(n * 86400);
}

export function maxWindowSec(bounds: MetricsBounds | null): number {
  if (bounds && bounds.max_window_seconds >= MIN_WINDOW_SEC) {
    return bounds.max_window_seconds;
  }
  return FALLBACK_MAX_DAYS * 86400;
}

export function availableFromMs(
  bounds: MetricsBounds | null,
  nowMs: number = Date.now(),
): number {
  const retention = nowMs - maxWindowSec(bounds) * 1000;
  if (!bounds?.available_from) return retention;
  const parsed = Date.parse(bounds.available_from);
  if (!Number.isFinite(parsed)) return retention;
  return Math.max(retention, parsed);
}

export function clampWindowSec(
  windowSec: number,
  bounds: MetricsBounds | null,
): { windowSec: number; message: string | null } {
  const maxW = maxWindowSec(bounds);
  if (windowSec < 1) return { windowSec: DEFAULT_RUNTIME_WINDOW, message: null };
  if (windowSec < MIN_WINDOW_SEC) {
    return { windowSec: MIN_WINDOW_SEC, message: null };
  }
  if (windowSec > maxW) {
    return { windowSec: maxW, message: tooOldMessage(bounds) };
  }
  return { windowSec, message: null };
}

export function tooOldMessage(bounds: MetricsBounds | null): string {
  const days = bounds?.retention_max_age_days ?? FALLBACK_MAX_DAYS;
  const from = bounds?.available_from
    ? new Date(bounds.available_from).toLocaleString()
    : `${days}-day retention`;
  return `That time is older than retained metrics (${days} days; available from ${from}).`;
}

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

export function toDatetimeLocal(ms: number): string {
  const d = new Date(ms);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function fromDatetimeLocal(value: string): number | null {
  if (!value.trim()) return null;
  const ms = new Date(value).getTime();
  return Number.isFinite(ms) ? ms : null;
}

export function selectRangeKind(
  state: TrendsRangeState,
  value: string,
  bounds: MetricsBounds | null,
  nowMs: number = Date.now(),
): TrendsRangeState {
  if (value === "custom") return enterCustom(state, bounds);
  if (value === "absolute") return enterAbsolute(state, bounds, nowMs);
  const { windowSec } = clampWindowSec(Number(value), bounds);
  return { ...state, mode: "preset", windowSec };
}

export function applyCustomDuration(
  state: TrendsRangeState,
  amount: number,
  unit: DurationUnit,
  bounds: MetricsBounds | null,
): TrendsRangeState {
  const { windowSec } = clampWindowSec(customSeconds(amount, unit), bounds);
  return {
    ...state,
    mode: "custom",
    customAmount: amount,
    customUnit: unit,
    windowSec,
  };
}

export function applyAbsoluteTimes(
  state: TrendsRangeState,
  startLocal: string,
  endLocal: string,
  bounds: MetricsBounds | null,
  nowMs: number = Date.now(),
): TrendsRangeState {
  const clamped = clampAbsolute(startLocal, endLocal, bounds, nowMs);
  const windowSec = Math.max(
    MIN_WINDOW_SEC,
    Math.round((clamped.endMs - clamped.startMs) / 1000),
  );
  return {
    ...state,
    mode: "absolute",
    startLocal: toDatetimeLocal(clamped.startMs),
    endLocal: toDatetimeLocal(clamped.endMs),
    windowSec,
  };
}

export function presetSelectValue(state: TrendsRangeState): string {
  if (state.mode === "custom" || state.mode === "absolute") return state.mode;
  const match = RUNTIME_WINDOWS.some((w) => w.seconds === state.windowSec);
  return match ? String(state.windowSec) : "custom";
}

function enterCustom(
  state: TrendsRangeState,
  bounds: MetricsBounds | null,
): TrendsRangeState {
  const { windowSec } = clampWindowSec(state.windowSec, bounds);
  const unit: DurationUnit =
    windowSec >= 86400 ? "days" : windowSec >= 3600 ? "hours" : "minutes";
  const amount =
    unit === "days"
      ? windowSec / 86400
      : unit === "hours"
        ? windowSec / 3600
        : windowSec / 60;
  return { ...state, mode: "custom", windowSec, customUnit: unit, customAmount: amount };
}

function enterAbsolute(
  state: TrendsRangeState,
  bounds: MetricsBounds | null,
  nowMs: number,
): TrendsRangeState {
  const endMs = nowMs;
  const startMs = endMs - state.windowSec * 1000;
  return applyAbsoluteTimes(
    { ...state, mode: "absolute" },
    toDatetimeLocal(startMs),
    toDatetimeLocal(endMs),
    bounds,
    nowMs,
  );
}

function clampAbsolute(
  startLocal: string,
  endLocal: string,
  bounds: MetricsBounds | null,
  nowMs: number,
): { startMs: number; endMs: number } {
  const minMs = availableFromMs(bounds, nowMs);
  let endMs = fromDatetimeLocal(endLocal) ?? nowMs;
  let startMs =
    fromDatetimeLocal(startLocal) ?? endMs - DEFAULT_RUNTIME_WINDOW * 1000;
  if (endMs > nowMs) endMs = nowMs;
  if (endMs < minMs) endMs = minMs;
  if (startMs < minMs) startMs = minMs;
  if (startMs >= endMs) startMs = Math.max(minMs, endMs - MIN_WINDOW_SEC * 1000);
  return { startMs, endMs };
}

function pad(n: number): string {
  return String(n).padStart(2, "0");
}
