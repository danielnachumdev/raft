/** Map HTTP status codes to table tone classes. */

export type RequestStatusTone = "ok" | "warn" | "bad" | "muted";

export function statusToneForCode(status: number): RequestStatusTone {
  if (status >= 200 && status < 300) return "ok";
  if (status >= 300 && status < 400) return "warn";
  if (status >= 400) return "bad";
  return "muted";
}

/** Compact cell time: ``HH:MM:SS`` today, ``Oct 18 15:10`` on earlier days. */
export function formatRequestTime(ts: string | null, now: number = Date.now()): string {
  if (!ts) return "—";
  const parsed = Date.parse(ts);
  if (Number.isNaN(parsed)) return ts;
  const at = new Date(parsed);
  if (at.toDateString() === new Date(now).toDateString()) {
    return at.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
  }
  return at.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false });
}

/** Full local timestamp for tooltips. */
export function formatRequestTimeFull(ts: string | null): string {
  if (!ts) return "";
  const parsed = Date.parse(ts);
  return Number.isNaN(parsed) ? ts : new Date(parsed).toLocaleString();
}

export function formatLatencyMs(ms: number): string {
  if (!Number.isFinite(ms)) return "—";
  if (ms < 10) return `${ms.toFixed(1)} ms`;
  return `${Math.round(ms)} ms`;
}
