import type { GraphEvent, MetricsSeries } from "./api";
import { groupKey } from "./trendsView";

/** Keep events that apply to the plotted series (or global / no service). */
export function eventsForSeries(
  events: GraphEvent[] | undefined,
  series: MetricsSeries[],
): GraphEvent[] {
  if (!events || events.length === 0) return [];
  const ids = serviceIdsForEvents(series);
  return events.filter((e) => !e.service || ids.has(e.service));
}

/**
 * Resolve compose service ids from plotted series.
 * Per-group charts use synthetic ``group:…`` ids — map those back via ``group``.
 */
export function serviceIdsForEvents(series: MetricsSeries[]): Set<string> {
  const ids = new Set<string>();
  for (const s of series) {
    if (s.kind === "group" || s.id.startsWith("group:")) {
      continue;
    }
    if (s.kind !== "host" && s.id !== "host") {
      ids.add(s.id);
    }
  }
  return ids;
}

/** When the chart shows group aggregates, include members of those groups. */
export function seriesForEventFilter(
  all: MetricsSeries[],
  visible: MetricsSeries[],
): MetricsSeries[] {
  const groupIds = new Set(
    visible
      .filter((s) => s.kind === "group" || s.id.startsWith("group:"))
      .map((s) => (s.id.startsWith("group:") ? s.id.slice("group:".length) : groupKey(s.group))),
  );
  if (groupIds.size === 0) return visible;
  return all.filter((s) => {
    if (s.kind === "host" || s.id === "host") return false;
    return groupIds.has(groupKey(s.group));
  });
}

/** Merge event timestamps into chart rows so ReferenceLine x keys exist. */
export function withEventRows<T extends { t: string; label: string }>(
  rows: T[],
  events: GraphEvent[],
  emptyRow: (t: string, label: string) => T,
): T[] {
  if (!events.length) return rows;
  const byT = new Map(rows.map((r) => [r.t, r]));
  for (const event of events) {
    if (!byT.has(event.ts)) {
      byT.set(event.ts, emptyRow(event.ts, shortTime(event.ts)));
    }
  }
  return [...byT.values()].sort((a, b) => a.t.localeCompare(b.t));
}

export function eventMarkerLabel(event: GraphEvent): string {
  if (event.label && event.label.trim()) return event.label.trim();
  if (event.kind === "deployment") return "Deploy";
  return event.kind;
}

export function shortTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
