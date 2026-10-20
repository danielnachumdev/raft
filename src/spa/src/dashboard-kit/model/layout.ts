import type { GraphSize } from "../../trends/dashboard/model/types.ts";
import type { PanelSpan } from "./types.ts";

export const GRID_COLUMNS = 12;
export const SPAN_HALF = 6;
export const SPAN_FULL = 12;

/** Map legacy Trends size tokens onto the 12-col span model. */
export function sizeToSpan(size: GraphSize): PanelSpan {
  return size === "full" ? SPAN_FULL : SPAN_HALF;
}

/** Collapse a span back to the v1 CSS tokens (≤6 → half, else full). */
export function spanToSize(span: PanelSpan): GraphSize {
  const n = clampSpan(span);
  return n >= SPAN_FULL ? "full" : "half";
}

export function clampSpan(span: PanelSpan): PanelSpan {
  if (!Number.isFinite(span)) return SPAN_HALF;
  return Math.max(1, Math.min(GRID_COLUMNS, Math.round(span)));
}

/** CSS modifiers for the current 2-col Trends grid. */
export function gridCellClass(size: GraphSize): string {
  return size === "full" ? "is-full" : "is-half";
}
