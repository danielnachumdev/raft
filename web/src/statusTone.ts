/** Semantic tone classes for status-table cells (CSS `tone-*` / `util-*`). */

export type StatusTone = "ok" | "warn" | "bad" | "idle" | "muted";
export type UtilTone = "ok" | "warn" | "hot" | null;

const STATUS_TONES: Record<string, StatusTone> = {
  running: "ok",
  starting: "warn",
  "scaled-to-zero": "idle",
  unhealthy: "bad",
  "not running": "bad",
  exited: "bad",
  dead: "bad",
  restarting: "bad",
  paused: "warn",
  created: "muted",
  unknown: "muted",
};

const BYTE_UNITS: Record<string, number> = {
  B: 1,
  KiB: 1024,
  MiB: 1024 ** 2,
  GiB: 1024 ** 3,
  TiB: 1024 ** 4,
};

export function statusTone(status: string): StatusTone {
  const key = status.trim().toLowerCase();
  return STATUS_TONES[key] ?? "muted";
}

/** Parse ``12.3%`` display strings; ``-`` / junk → null. */
export function parsePercent(text: string): number | null {
  const raw = text.trim();
  if (!raw || raw === "-") {
    return null;
  }
  const match = /^(-?\d+(?:\.\d+)?)\s*%$/.exec(raw);
  if (!match) {
    return null;
  }
  const value = Number(match[1]);
  return Number.isFinite(value) ? value : null;
}

/** Parse ``12.5MiB / 128.0MiB`` into used/limit ratio as percent. */
export function parseMemoryRatioPercent(text: string): number | null {
  const parts = text.split("/");
  if (parts.length !== 2) {
    return null;
  }
  const used = parseByteQuantity(parts[0]);
  const limit = parseByteQuantity(parts[1]);
  if (used === null || limit === null || limit <= 0) {
    return null;
  }
  return (used / limit) * 100;
}

export function utilTone(percent: number | null): UtilTone {
  if (percent === null || !Number.isFinite(percent)) {
    return null;
  }
  if (percent >= 85) {
    return "hot";
  }
  if (percent >= 60) {
    return "warn";
  }
  return "ok";
}

function parseByteQuantity(text: string): number | null {
  const match = /^([\d.]+)\s*(B|KiB|MiB|GiB|TiB)?$/i.exec(text.trim());
  if (!match) {
    return null;
  }
  const value = Number(match[1]);
  if (!Number.isFinite(value)) {
    return null;
  }
  const raw = (match[2] || "B").toLowerCase();
  const unit = Object.keys(BYTE_UNITS).find((key) => key.toLowerCase() === raw);
  if (!unit) {
    return null;
  }
  return value * BYTE_UNITS[unit]!;
}
