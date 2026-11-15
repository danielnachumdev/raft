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

const indexCache = new WeakMap<object, Map<string, ReadonlySet<number>>>();

/**
 * Row indices of isolated samples for one series. Memoized per ``rows``
 * array so hover re-renders do not rescan every series.
 */
export function isolatedPointIndices(
  rows: ReadonlyArray<Record<string, unknown>>,
  dataKey: string,
): ReadonlySet<number> {
  let byKey = indexCache.get(rows);
  if (!byKey) {
    byKey = new Map();
    indexCache.set(rows, byKey);
  }
  let found = byKey.get(dataKey);
  if (!found) {
    found = scanIsolated(rows, dataKey);
    byKey.set(dataKey, found);
  }
  return found;
}

function scanIsolated(
  rows: ReadonlyArray<Record<string, unknown>>,
  dataKey: string,
): ReadonlySet<number> {
  const out = new Set<number>();
  for (let i = 0; i < rows.length; i++) {
    if (isIsolatedSeriesPoint(rows, dataKey, i)) out.add(i);
  }
  return out;
}
