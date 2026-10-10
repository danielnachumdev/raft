import type { MetricsAvailable, MetricsPoint, MetricsSeries } from "../../shared/api.ts";
import { RUNTIME_METRICS, type RuntimeMetricId } from "../runtimeMetrics.ts";

export type SeriesViewMode =
  | "per_service"
  | "per_group"
  | "avg_all"
  | "avg_group";

export const UNGROUPED_ID = "__ungrouped__";
export const UNGROUPED_LABEL = "Ungrouped";

export type GroupOption = { id: string; label: string };

export function usesGroupPicker(mode: SeriesViewMode): boolean {
  return mode === "per_group" || mode === "avg_group";
}

/** Chart-level single average line — only ``avg_all`` (not per-group means). */
export function isSingleLineAvg(mode: SeriesViewMode): boolean {
  return mode === "avg_all";
}

/** Resolve plotted series for the Trends view mode + sidebar selection. */
export function resolveVisibleSeries(args: {
  series: MetricsSeries[];
  viewMode: SeriesViewMode;
  selected: string[] | null;
  activeIds: string[];
}): MetricsSeries[] {
  if (args.viewMode === "per_group" || args.viewMode === "avg_group") {
    return buildPerGroupSeries(args.series, args.activeIds);
  }
  if (args.selected === null) return args.series;
  return args.series.filter((s) => args.selected!.includes(s.id));
}

export function groupKey(group: string | null | undefined): string {
  return group && group.trim() ? group.trim() : UNGROUPED_ID;
}

export function groupLabel(group: string | null | undefined): string {
  return group && group.trim() ? group.trim() : UNGROUPED_LABEL;
}

/** Distinct groups from container (non-host) available entries. */
export function groupOptions(available: MetricsAvailable[]): GroupOption[] {
  const map = new Map<string, string>();
  for (const a of available) {
    if (a.kind === "host" || a.id === "host") continue;
    const id = groupKey(a.group);
    if (!map.has(id)) map.set(id, groupLabel(a.group));
  }
  return [...map.entries()]
    .map(([id, label]) => ({ id, label }))
    .sort((a, b) => a.label.localeCompare(b.label));
}

/** Service series belonging to the selected group ids. */
export function seriesInGroups(
  series: MetricsSeries[],
  groupIds: string[],
): MetricsSeries[] {
  const want = new Set(groupIds);
  return series.filter((s) => {
    if (s.kind === "host" || s.id === "host") return false;
    return want.has(groupKey(s.group));
  });
}

/** One synthetic series per group (mean of members at each timestamp). */
export function buildPerGroupSeries(
  series: MetricsSeries[],
  groupIds: string[],
): MetricsSeries[] {
  const want = new Set(groupIds);
  const buckets = new Map<string, MetricsSeries[]>();
  for (const s of series) {
    if (s.kind === "host" || s.id === "host") continue;
    const gid = groupKey(s.group);
    if (!want.has(gid)) continue;
    const list = buckets.get(gid) ?? [];
    list.push(s);
    buckets.set(gid, list);
  }
  return [...buckets.entries()]
    .sort((a, b) =>
      groupLabel(a[0] === UNGROUPED_ID ? null : a[0]).localeCompare(
        groupLabel(b[0] === UNGROUPED_ID ? null : b[0]),
      ),
    )
    .map(([gid, members]) => averageSeriesAsOne(members, gid));
}

function averageSeriesAsOne(
  members: MetricsSeries[],
  groupId: string,
): MetricsSeries {
  const byTime = new Map<string, MetricsPoint[]>();
  for (const s of members) {
    for (const p of s.points) {
      const list = byTime.get(p.t) ?? [];
      list.push(p);
      byTime.set(p.t, list);
    }
  }
  const points: MetricsPoint[] = [...byTime.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([t, pts]) => meanPoint(t, pts));
  return {
    id: `group:${groupId}`,
    label: groupLabel(groupId === UNGROUPED_ID ? null : groupId),
    kind: "group",
    role: "group",
    group: groupId === UNGROUPED_ID ? null : groupId,
    points,
  };
}

function meanPoint(t: string, pts: MetricsPoint[]): MetricsPoint {
  const out: MetricsPoint = { t };
  for (const m of RUNTIME_METRICS) {
    const vals = pts
      .map((p) => numericField(p, m.id))
      .filter((v): v is number => v !== null);
    if (vals.length) out[m.id] = mean(vals);
  }
  return out;
}

function numericField(
  point: MetricsPoint,
  id: RuntimeMetricId,
): number | null {
  const raw: unknown = point[id];
  if (typeof raw === "number" && Number.isFinite(raw)) return raw;
  return null;
}

function mean(vals: number[]): number {
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}
