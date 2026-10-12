import type { MetricsBounds } from "../../shared/api/index.ts";
import { DEFAULT_RUNTIME_WINDOW } from "../runtimeMetrics.ts";
import { FALLBACK_MAX_DAYS, MIN_WINDOW_SEC } from "./types.ts";

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
