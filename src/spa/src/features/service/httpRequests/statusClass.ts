/** Map HTTP status codes to table tone classes. */

import { localeFormats } from "../../../shared/localeFormats.ts";

export type RequestStatusTone = "ok" | "warn" | "bad" | "muted";

export function statusToneForCode(status: number): RequestStatusTone {
  if (status >= 200 && status < 300) return "ok";
  if (status >= 300 && status < 400) return "warn";
  if (status >= 400) return "bad";
  return "muted";
}

/** Shared ``.chip`` classes for an HTTP status cell. */
export function httpStatusChipClass(tone: RequestStatusTone): string {
  const toneClass =
    tone === "ok"
      ? "chip-ok"
      : tone === "warn"
        ? "chip-warn"
        : tone === "bad"
          ? "chip-bad"
          : "";
  return ["chip", "http-requests-status", toneClass].filter(Boolean).join(" ");
}

/** Compact cell time: ``HH:MM:SS`` today, ``Oct 18 15:10`` on earlier days. */
export function formatRequestTime(ts: string | null, now: number = Date.now()): string {
  if (!ts) return "—";
  const parsed = Date.parse(ts);
  if (Number.isNaN(parsed)) return ts;
  const at = new Date(parsed);
  if (at.toDateString() === new Date(now).toDateString()) {
    return localeFormats.clock24.format(at);
  }
  return localeFormats.monthDayTime24.format(at);
}

/** Full local timestamp for tooltips. */
export function formatRequestTimeFull(ts: string | null): string {
  if (!ts) return "";
  const parsed = Date.parse(ts);
  return Number.isNaN(parsed) ? ts : localeFormats.dateTime.format(parsed);
}

export function formatLatencyMs(ms: number): string {
  if (!Number.isFinite(ms)) return "—";
  if (ms < 10) return `${ms.toFixed(1)} ms`;
  return `${Math.round(ms)} ms`;
}
