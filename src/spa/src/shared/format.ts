/** Human-readable formatting for raw numeric status fields. */

const BYTE_UNITS = ["B", "KiB", "MiB", "GiB", "TiB"] as const;

const DURATION_UNITS: { label: string; seconds: number }[] = [
  { label: "d", seconds: 86400 },
  { label: "h", seconds: 3600 },
  { label: "m", seconds: 60 },
  { label: "s", seconds: 1 },
];

/** ``1536`` → ``1.5 KiB``; null / negative / non-finite → ``-``. */
export function formatBytes(value: number | null | undefined): string {
  if (!isCount(value)) return "-";
  let scaled = value;
  let unit = 0;
  while (scaled >= 1024 && unit < BYTE_UNITS.length - 1) {
    scaled /= 1024;
    unit += 1;
  }
  const digits = unit === 0 || scaled >= 100 ? 0 : 1;
  return `${scaled.toFixed(digits)} ${BYTE_UNITS[unit]}`;
}

/** ``93784`` → ``1d 2h``; keeps the two largest non-zero units. */
export function formatDuration(seconds: number | null | undefined): string {
  if (!isCount(seconds)) return "-";
  let rest = Math.floor(seconds);
  const parts: string[] = [];
  for (const unit of DURATION_UNITS) {
    const n = Math.floor(rest / unit.seconds);
    rest -= n * unit.seconds;
    if (n > 0 || (parts.length === 0 && unit.seconds === 1)) {
      parts.push(`${n}${unit.label}`);
    }
    if (parts.length === 2) break;
  }
  return parts.join(" ");
}

/** ``12.345`` → ``12.3%``; null → ``-``. */
export function formatPercent(value: number | null | undefined): string {
  if (!isCount(value)) return "-";
  return `${value.toFixed(1)}%`;
}

/** Plain integer with locale grouping; null → ``-``. */
export function formatCount(value: number | null | undefined): string {
  if (!isCount(value)) return "-";
  return Math.round(value).toLocaleString("en-US");
}

function isCount(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0;
}
