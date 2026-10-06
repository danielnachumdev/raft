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

/** Merge per-key timed values into chart rows keyed by epoch ms. */
export function mergeTimedRows(
  seriesPoints: { key: string; points: TimedValue[] }[],
  gapMs: number = DEFAULT_SAMPLE_INTERVAL_MS * GAP_INTERVAL_MULTIPLIER,
): Record<string, string | number | null>[] {
  const byTs = new Map<number, Record<string, string | number | null>>();
  for (const { key, points } of seriesPoints) {
    for (const p of withGapBreaks(points, gapMs)) {
      const row = byTs.get(p.ts) ?? baseRow(p.ts, p.t);
      row[key] = p.value;
      byTs.set(p.ts, row);
    }
  }
  return [...byTs.values()].sort(
    (a, b) => Number(a.ts) - Number(b.ts),
  );
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
