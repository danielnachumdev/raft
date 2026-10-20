/** Pure presentation helpers for the ops event timeline. */

import type { OpsEventRow } from "./eventsApi";

export type EventsQuery = { hours: number; kind: string; service: string };

export const DEFAULT_EVENTS_QUERY: EventsQuery = { hours: 24, kind: "", service: "" };

export type EventTone = "ok" | "warn" | "bad" | "idle" | "neutral";

export type EventKindGroup = { label: string; kinds: string[] };

/** Known ``host/events/ops.jsonl`` kinds, grouped for the filter picker. */
export const EVENT_KIND_GROUPS: EventKindGroup[] = [
  { label: "Deploy", kinds: ["deploy.apply", "deploy.redeploy"] },
  { label: "Services", kinds: ["service.start", "service.stop"] },
  { label: "Scaling", kinds: ["scale.wake", "scale.idle_stop"] },
  { label: "Alerts", kinds: ["alert.fired", "alert.resolved"] },
  { label: "Edge", kinds: ["firewall.apply", "gate.reload", "gate.recreate"] },
  {
    label: "Stack",
    kinds: ["stack.up", "stack.down", "stack.purge", "raft.update"],
  },
];

const TONES: Record<string, EventTone> = {
  "alert.fired": "bad",
  "alert.resolved": "ok",
  "deploy.apply": "ok",
  "deploy.redeploy": "ok",
  "service.start": "ok",
  "stack.up": "ok",
  "service.stop": "warn",
  "stack.down": "warn",
  "gate.recreate": "warn",
  "scale.wake": "idle",
  "scale.idle_stop": "idle",
};

export function eventTone(kind: string): EventTone {
  return TONES[kind] ?? "neutral";
}

export type EventDayGroup = { key: string; label: string; rows: OpsEventRow[] };

/** Bucket newest-first rows by local calendar day ("Today", "Yesterday", date). */
export function groupEventsByDay(rows: OpsEventRow[], now: number): EventDayGroup[] {
  const groups: EventDayGroup[] = [];
  for (const row of sortNewestFirst(rows)) {
    const key = localDayKey(row.ts);
    const last = groups[groups.length - 1];
    if (last && last.key === key) last.rows.push(row);
    else groups.push({ key, label: dayLabel(key, now), rows: [row] });
  }
  return groups;
}

/** Local wall-clock ``HH:MM:SS`` for a row timestamp. */
export function formatClock(iso: string): string {
  const ms = Date.parse(iso);
  if (Number.isNaN(ms)) return iso;
  return new Date(ms).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function formatFull(iso: string): string {
  const ms = Date.parse(iso);
  return Number.isNaN(ms) ? iso : new Date(ms).toLocaleString();
}

function sortNewestFirst(rows: OpsEventRow[]): OpsEventRow[] {
  return rows.slice().sort((a, b) => (Date.parse(b.ts) || 0) - (Date.parse(a.ts) || 0));
}

function localDayKey(iso: string): string {
  const ms = Date.parse(iso);
  if (Number.isNaN(ms)) return "unknown";
  const d = new Date(ms);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function dayLabel(key: string, now: number): string {
  if (key === "unknown") return "Unknown date";
  if (key === localDayKey(new Date(now).toISOString())) return "Today";
  if (key === localDayKey(new Date(now - 86_400_000).toISOString())) return "Yesterday";
  const [y, m, d] = key.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

function pad(n: number): string {
  return String(n).padStart(2, "0");
}
