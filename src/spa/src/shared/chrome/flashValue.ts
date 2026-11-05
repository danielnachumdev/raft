/** Pure helpers + declarative flash mode builders for {@link FlashValue}. */

export type FlashDirection = "up" | "down" | "none";

export type FlashSignal = {
  color: string;
  intensity: number;
  direction: FlashDirection;
};

/** Given previous/next comparable values, produce a wash signal (or skip). */
export type FlashMode = {
  signal: (prev: unknown, next: unknown) => FlashSignal | null;
};

const DEFAULT_SOLID = "var(--accent)";
const DEFAULT_UP = "var(--ok)";
const DEFAULT_DOWN = "var(--danger)";
const DEFAULT_NONE = "var(--idle)";

/** Sign of a numeric change: higher → up, lower → down, equal → none. */
export function compareDirection(prev: number, next: number): FlashDirection {
  if (!Number.isFinite(prev) || !Number.isFinite(next)) return "none";
  if (next > prev) return "up";
  if (next < prev) return "down";
  return "none";
}

/**
 * Map |delta| onto discrete intensity steps.
 * `buckets` are ascending |delta| thresholds; intensity is (index+1)/len, capped at 1.
 */
export function bucketIntensity(absDelta: number, buckets: number[]): number {
  if (!buckets.length || !(absDelta > 0)) return 0;
  let step = 0;
  for (let i = 0; i < buckets.length; i += 1) {
    if (absDelta >= buckets[i]!) step = i + 1;
  }
  if (step === 0) return 0;
  return Math.min(1, step / buckets.length);
}

/** Linear intensity from |delta| / maxAbsDelta, clamped to [0, 1]. */
export function magnitudeIntensity(absDelta: number, maxAbsDelta: number): number {
  if (!(absDelta > 0) || !(maxAbsDelta > 0)) return 0;
  return Math.min(1, absDelta / maxAbsDelta);
}

/** Coerce common SPA cell values (`12.3%`, plain numbers) to a finite number. */
export function parseFlashNumber(value: unknown): number | null {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (!trimmed || trimmed === "-") return null;
  const match = trimmed.match(/-?\d+(?:\.\d+)?/);
  if (!match) return null;
  const n = Number(match[0]);
  return Number.isFinite(n) ? n : null;
}

export type SolidFlashOptions = {
  color?: string;
  intensity?: number;
};

/** Brief single-color wash whenever the displayed value changes. */
export function solidFlash(options: SolidFlashOptions = {}): FlashMode {
  const color = options.color ?? DEFAULT_SOLID;
  const intensity = clamp01(options.intensity ?? 0.55);
  return {
    signal: (prev, next) => {
      if (Object.is(prev, next)) return null;
      return { color, intensity, direction: "none" };
    },
  };
}

export type DirectionalFlashOptions = {
  parse?: (value: unknown) => number | null;
  direction?: (prev: number, next: number) => FlashDirection;
  upColor?: string;
  downColor?: string;
  noneColor?: string;
  /** Custom 0..1 intensity from the numeric pair. */
  intensity?: (prev: number, next: number) => number;
  /** Ascending |delta| thresholds → stepped intensity. */
  buckets?: number[];
  /** |delta| that maps to full intensity when `buckets` is unset. */
  maxAbsDelta?: number;
};

/**
 * Gradient wash along up/down colors.
 * Prefer `buckets` for stepped strength, or `maxAbsDelta` / `intensity` for continuous.
 */
export function directionalFlash(options: DirectionalFlashOptions = {}): FlashMode {
  const parse = options.parse ?? parseFlashNumber;
  const directionFn = options.direction ?? compareDirection;
  const upColor = options.upColor ?? DEFAULT_UP;
  const downColor = options.downColor ?? DEFAULT_DOWN;
  const noneColor = options.noneColor ?? DEFAULT_NONE;
  const buckets = options.buckets;
  const maxAbsDelta = options.maxAbsDelta ?? 10;
  const intensityFn = options.intensity;

  return {
    signal: (prev, next) => {
      const a = parse(prev);
      const b = parse(next);
      if (a === null || b === null) {
        if (Object.is(prev, next)) return null;
        return { color: noneColor, intensity: 0.4, direction: "none" };
      }
      if (a === b) return null;
      const direction = directionFn(a, b);
      const absDelta = Math.abs(b - a);
      const intensity = resolveIntensity(absDelta, a, b, buckets, maxAbsDelta, intensityFn);
      if (intensity <= 0) return null;
      const color =
        direction === "up" ? upColor : direction === "down" ? downColor : noneColor;
      return { color, intensity, direction };
    },
  };
}

function resolveIntensity(
  absDelta: number,
  prev: number,
  next: number,
  buckets: number[] | undefined,
  maxAbsDelta: number,
  intensityFn: ((prev: number, next: number) => number) | undefined,
): number {
  if (intensityFn) return clamp01(intensityFn(prev, next));
  if (buckets?.length) return bucketIntensity(absDelta, buckets);
  return magnitudeIntensity(absDelta, maxAbsDelta);
}

function clamp01(n: number): number {
  if (!Number.isFinite(n)) return 0;
  return Math.min(1, Math.max(0, n));
}
