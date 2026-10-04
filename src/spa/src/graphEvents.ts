import type { GraphEvent, MetricsSeries } from "./api.ts";
import { formatTickTime, toEpochMs } from "./chartTimeScale.ts";

/** Match ``trendsView`` ungrouped bucket without importing that module (node tests). */
const UNGROUPED_ID = "__ungrouped__";

/** Edge / controller Compose ids — always relevant on Trends. */
const RAFT_LEVEL_SERVICES = new Set([
  "raft-gate",
  "raft-router",
  "raft-controller",
]);

/** Stack-wide kinds (may omit service or attach to gate). */
const RAFT_LEVEL_KINDS = new Set([
  "up",
  "down",
  "update",
  "gate_recreate",
]);

/** Hex strokes (SVG attrs do not always resolve CSS variables). */
const KIND_STROKE: Record<string, string> = {
  deployment: "#0f6b5c",
  start: "#1a6b45",
  stop: "#8b2e1f",
  scaling: "#3d5a6c",
  up: "#0e7490",
  down: "#9a3412",
  update: "#a16207",
  gate_recreate: "#1e3a5f",
};

/** Keep events that apply to the plotted series (or raft-level / global). */
export function eventsForSeries(
  events: GraphEvent[] | undefined,
  series: MetricsSeries[],
): GraphEvent[] {
  if (!events || events.length === 0) return [];
  const ids = serviceIdsForEvents(series);
  return events.filter(
    (e) => isRaftLevelEvent(e) || (e.service != null && ids.has(e.service)),
  );
}

/** Stack-wide / edge / controller markers — always show on Trends. */
export function isRaftLevelEvent(event: GraphEvent): boolean {
  if (!event.service) return true;
  if (RAFT_LEVEL_KINDS.has(event.kind)) return true;
  return RAFT_LEVEL_SERVICES.has(event.service);
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
      .map((s) =>
        s.id.startsWith("group:") ? s.id.slice("group:".length) : seriesGroupKey(s.group),
      ),
  );
  if (groupIds.size === 0) return visible;
  return all.filter((s) => {
    if (s.kind === "host" || s.id === "host") return false;
    return groupIds.has(seriesGroupKey(s.group));
  });
}

function seriesGroupKey(group: string | null | undefined): string {
  return group && group.trim() ? group.trim() : UNGROUPED_ID;
}

/** Merge event timestamps into chart rows so ReferenceLine x keys exist. */
export function withEventRows<
  T extends { t: string; ts: number; label: string },
>(
  rows: T[],
  events: GraphEvent[],
  emptyRow: (t: string, label: string) => T,
): T[] {
  if (!events.length) return rows;
  const byT = new Map(rows.map((r) => [r.t, r]));
  for (const event of events) {
    if (!byT.has(event.ts)) {
      const ms = toEpochMs(event.ts);
      const label = ms === null ? shortTime(event.ts) : formatTickTime(ms);
      byT.set(event.ts, emptyRow(event.ts, label));
    }
  }
  return [...byT.values()].sort((a, b) => a.ts - b.ts);
}

export function eventMarkerLabel(event: GraphEvent): string {
  if (event.label && event.label.trim()) return event.label.trim();
  if (event.kind === "deployment") return "Deploy";
  if (event.kind === "stop") return "Stop";
  if (event.kind === "start") return "Start";
  if (event.kind === "scaling") return scalingMarkerLabel(event);
  if (event.kind === "up") return "Stack up";
  if (event.kind === "down") return "Stack down";
  if (event.kind === "update") return "Raft update";
  if (event.kind === "gate_recreate") return "Gate recreate";
  return event.kind;
}

function scalingMarkerLabel(event: GraphEvent): string {
  const action = event.metadata?.action;
  if (action === "idle_stop") return "Idle stop";
  if (action === "wake") return "Wake";
  return "Scale";
}

/** Stroke color for a GraphEvent ReferenceLine by kind. */
export function eventMarkerStroke(kind: string): string {
  return KIND_STROKE[kind] ?? "#5c564c";
}

export function shortTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
