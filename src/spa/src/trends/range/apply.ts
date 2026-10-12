import type { MetricsBounds } from "../../shared/api/index.ts";
import {
  DEFAULT_RUNTIME_WINDOW,
  RUNTIME_WINDOWS,
} from "../runtimeMetrics.ts";
import { availableFromMs, clampWindowSec } from "./clamp.ts";
import { fromDatetimeLocal, toDatetimeLocal } from "./datetime.ts";
import {
  MIN_WINDOW_SEC,
  type DurationUnit,
  type TrendsRangeState,
} from "./types.ts";

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
  return {
    ...state,
    mode: "custom",
    windowSec,
    customUnit: unit,
    customAmount: amount,
  };
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
