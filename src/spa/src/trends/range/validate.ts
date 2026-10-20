import type { TrendsRangeState } from "./types.ts";

/** Validate a stored range payload; null when it is not usable. */
export function parseRange(raw: unknown): TrendsRangeState | null {
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;
  if (obj.mode !== "preset" && obj.mode !== "custom" && obj.mode !== "absolute") {
    return null;
  }
  if (typeof obj.windowSec !== "number" || !Number.isFinite(obj.windowSec)) {
    return null;
  }
  if (typeof obj.customAmount !== "number") return null;
  if (
    obj.customUnit !== "minutes" &&
    obj.customUnit !== "hours" &&
    obj.customUnit !== "days"
  ) {
    return null;
  }
  if (typeof obj.startLocal !== "string" || typeof obj.endLocal !== "string") {
    return null;
  }
  return {
    mode: obj.mode,
    windowSec: obj.windowSec,
    customAmount: obj.customAmount,
    customUnit: obj.customUnit,
    startLocal: obj.startLocal,
    endLocal: obj.endLocal,
  };
}
