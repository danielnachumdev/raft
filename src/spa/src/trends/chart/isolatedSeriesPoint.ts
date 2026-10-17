/** True when ``value`` is a finite number Recharts can plot. */
export function isNumericPoint(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

/**
 * A point with no adjacent numeric siblings cannot form a line segment
 * (``connectNulls={false}``), so charts must draw a visible dot instead.
 */
export function isIsolatedSeriesPoint(
  rows: ReadonlyArray<Record<string, unknown>>,
  dataKey: string,
  index: number,
): boolean {
  if (!isNumericPoint(rows[index]?.[dataKey])) return false;
  const prev = index > 0 ? rows[index - 1]?.[dataKey] : undefined;
  const next =
    index < rows.length - 1 ? rows[index + 1]?.[dataKey] : undefined;
  return !isNumericPoint(prev) && !isNumericPoint(next);
}
