/** Time-domain X axis + gap breaks for Trends / Runtime charts. */

/** Default controller metrics interval (settings metrics.intervalSeconds). */
export const DEFAULT_SAMPLE_INTERVAL_MS = 60_000;

/** Break a line when consecutive samples exceed this × sample interval. */
export const GAP_INTERVAL_MULTIPLIER = 2;

export type TimedValue = { ts: number; t: string; value: number | null };

export type TimeDomain = { startMs: number; endMs: number };

/** Parse ISO (or epoch-like) timestamp to ms; null if invalid. */
export function toEpochMs(iso: string): number | null {
  const ms = Date.parse(iso);
  return Number.isFinite(ms) ? ms : null;
}

/** Window domain ending at ``endMs`` (default now). */
export function windowDomain(
  windowSeconds: number,
  endMs: number = Date.now(),
): TimeDomain {
  const span = Math.max(1, windowSeconds) * 1000;
  return { startMs: endMs - span, endMs };
}

/**
 * Rolling lookback follows ``nowMs`` so the axis crawls with wall time.
 * Point-in-time ranges stay on the payload/query end.
 */
export function chartEndMs(args: {
  rolling: boolean;
  nowMs: number;
  rangeEndIso?: string | null;
}): number {
  if (args.rolling) return args.nowMs;
  return toEpochMs(args.rangeEndIso ?? "") ?? args.nowMs;
}

/** Drop samples that have scrolled out of the visible window. */
export function clipRowsToDomain<T extends { ts: number }>(
  rows: T[],
  domain: TimeDomain,
): T[] {
  return rows.filter(
    (row) => row.ts >= domain.startMs && row.ts <= domain.endMs,
  );
}

/**
 * Gap threshold from actual inter-sample spacing (post-downsample cadence).
 * Falls back to ``2 × 60s`` when a series has fewer than two distinct times.
 * With only one or two gaps, cap the cadence estimate at the default scrape
 * interval so a lone multi-minute jump still breaks instead of redefining
 * "normal" spacing.
 */
export function inferGapMs(points: TimedValue[]): number {
  const gaps = positiveDeltas(points);
  if (!gaps.length) {
    return DEFAULT_SAMPLE_INTERVAL_MS * GAP_INTERVAL_MULTIPLIER;
  }
  gaps.sort((a, b) => a - b);
  const median = gaps[Math.floor(gaps.length / 2)];
  const cadence =
    gaps.length >= 3
      ? median
      : Math.min(median, DEFAULT_SAMPLE_INTERVAL_MS);
  return cadence * GAP_INTERVAL_MULTIPLIER;
}

/**
 * Insert null-valued breakpoints between sparse samples so Recharts
 * ``connectNulls={false}`` leaves a visual gap (time-proportional X).
 */
export function withGapBreaks(
  points: TimedValue[],
  gapMs: number = DEFAULT_SAMPLE_INTERVAL_MS * GAP_INTERVAL_MULTIPLIER,
): TimedValue[] {
  if (points.length < 2) return points;
  const sorted = [...points].sort((a, b) => a.ts - b.ts);
  const out: TimedValue[] = [sorted[0]];
  for (let i = 1; i < sorted.length; i++) {
    const prev = sorted[i - 1];
    const next = sorted[i];
    if (next.ts - prev.ts > gapMs) {
      out.push(gapSentinel(prev.ts));
    }
    out.push(next);
  }
  return out;
}

/**
 * Merge per-key timed values into chart rows keyed by epoch ms.
 *
 * Per-series gap sentinels use explicit ``null``. Missing keys on another
 * series' timestamps / sentinels are bridge-filled so ``connectNulls={false}``
 * does not break an unrelated continuous series.
 */
export function mergeTimedRows(
  seriesPoints: { key: string; points: TimedValue[] }[],
  gapMs?: number,
): Record<string, string | number | null>[] {
  const byTs = new Map<number, Record<string, string | number | null>>();
  const keys: string[] = [];
  for (const { key, points } of seriesPoints) {
    keys.push(key);
    const threshold = gapMs ?? inferGapMs(points);
    for (const p of withGapBreaks(points, threshold)) {
      const row = byTs.get(p.ts) ?? baseRow(p.ts, p.t);
      row[key] = p.value;
      byTs.set(p.ts, row);
    }
  }
  const rows = [...byTs.values()].sort(
    (a, b) => Number(a.ts) - Number(b.ts),
  );
  bridgeMissingSeriesValues(rows, keys);
  return rows;
}

/**
 * Hold/interpolate across rows where a key was never set (``undefined``),
 * but only between two numeric samples with no explicit ``null`` between.
 * Explicit nulls (scale-to-zero / gap sentinels) stay as line breaks.
 */
export function bridgeMissingSeriesValues(
  rows: Record<string, string | number | null>[],
  keys: string[],
): void {
  for (const key of keys) {
    bridgeKey(rows, key);
  }
}

/** Tick marks across a domain at a sensible step for the window length. */
export function timeAxisTicks(domain: TimeDomain): number[] {
  const step = tickStepMs(domain.endMs - domain.startMs);
  const first = Math.ceil(domain.startMs / step) * step;
  const ticks: number[] = [];
  for (let t = first; t <= domain.endMs; t += step) {
    ticks.push(t);
  }
  return ticks;
}

export function tickStepMs(spanMs: number): number {
  if (spanMs <= 15 * 60_000) return 60_000;
  if (spanMs <= 60 * 60_000) return 5 * 60_000;
  if (spanMs <= 6 * 60 * 60_000) return 30 * 60_000;
  if (spanMs <= 24 * 60 * 60_000) return 2 * 60 * 60_000;
  return 24 * 60 * 60_000;
}

export function formatTickTime(ms: number, spanMs?: number): string {
  const d = new Date(ms);
  if (Number.isNaN(d.getTime())) return String(ms);
  if (spanMs !== undefined && spanMs > 24 * 60 * 60_000) {
    return d.toLocaleDateString([], { month: "short", day: "numeric" });
  }
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function formatTooltipTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

function bridgeKey(
  rows: Record<string, string | number | null>[],
  key: string,
): void {
  let i = 0;
  while (i < rows.length) {
    if (!isFiniteNumber(rows[i][key])) {
      i += 1;
      continue;
    }
    let j = i + 1;
    while (j < rows.length && rows[j][key] === undefined) j += 1;
    if (j < rows.length && isFiniteNumber(rows[j][key])) {
      fillBridge(rows, key, i, j);
    }
    i = j > i + 1 ? j : i + 1;
  }
}

function fillBridge(
  rows: Record<string, string | number | null>[],
  key: string,
  left: number,
  right: number,
): void {
  const v0 = rows[left][key] as number;
  const v1 = rows[right][key] as number;
  const t0 = Number(rows[left].ts);
  const t1 = Number(rows[right].ts);
  const span = t1 - t0;
  for (let k = left + 1; k < right; k++) {
    const frac = span === 0 ? 0 : (Number(rows[k].ts) - t0) / span;
    rows[k][key] = v0 + (v1 - v0) * frac;
  }
}

function positiveDeltas(points: TimedValue[]): number[] {
  if (points.length < 2) return [];
  const sorted = [...points].sort((a, b) => a.ts - b.ts);
  const gaps: number[] = [];
  for (let i = 1; i < sorted.length; i++) {
    const d = sorted[i].ts - sorted[i - 1].ts;
    if (d > 0) gaps.push(d);
  }
  return gaps;
}

function isFiniteNumber(value: string | number | null | undefined): boolean {
  return typeof value === "number" && Number.isFinite(value);
}

function gapSentinel(afterTs: number): TimedValue {
  const ts = afterTs + 1;
  return { ts, t: new Date(ts).toISOString(), value: null };
}

function baseRow(
  ts: number,
  t: string,
): Record<string, string | number | null> {
  return { ts, t, label: formatTickTime(ts) };
}
