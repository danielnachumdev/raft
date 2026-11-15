import { useMemo, useState } from "react";
import { clipRowsStable, windowDomain } from "./chartTimeScale";

/**
 * Rows visible in ``windowSeconds`` ending at ``endMs``; keeps the previous
 * array identity while the slice is unchanged so Recharts can skip work.
 */
export function useStableClip<T extends { ts: number }>(
  rows: T[],
  windowSeconds: number,
  endMs: number,
): T[] {
  const [kept, setKept] = useState<T[] | null>(null);
  const next = useMemo(
    () => clipRowsStable(rows, windowDomain(windowSeconds, endMs), kept),
    [rows, windowSeconds, endMs, kept],
  );
  if (next !== kept) setKept(next);
  return next;
}
