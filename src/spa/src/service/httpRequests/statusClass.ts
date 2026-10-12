/** Map HTTP status codes to table tone classes. */

export type RequestStatusTone = "ok" | "warn" | "bad" | "muted";

export function statusToneForCode(status: number): RequestStatusTone {
  if (status >= 200 && status < 300) return "ok";
  if (status >= 300 && status < 400) return "warn";
  if (status >= 400) return "bad";
  return "muted";
}

export function formatRequestTime(ts: string | null): string {
  if (!ts) return "—";
  const parsed = Date.parse(ts);
  if (Number.isNaN(parsed)) return ts;
  return new Date(parsed).toLocaleString();
}

export function formatLatencyMs(ms: number): string {
  if (!Number.isFinite(ms)) return "—";
  if (ms < 10) return `${ms.toFixed(1)} ms`;
  return `${Math.round(ms)} ms`;
}
