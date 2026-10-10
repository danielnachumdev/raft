import type { Dispatch, SetStateAction } from "react";
import {
  fetchHttpMetrics,
  fetchMetrics,
  type GraphEvent,
  type MetricsAvailable,
  type MetricsBounds,
  type MetricsPayload,
  type MetricsQuery,
  type MetricsSeries,
} from "../../shared/api";
import type { MetricPlane } from "../runtimeMetrics";
import type { MetricsQueryOpts } from "../trendsRange";

export type PlaneCursors = Partial<Record<MetricPlane, string | null>>;

export function metricsFetcher(plane: MetricPlane) {
  return plane === "http" ? fetchHttpMetrics : fetchMetrics;
}

/** Cache / effect key for one or more metric planes. */
export function planesCacheKey(
  planes: MetricPlane[],
  cacheKey: string,
): string {
  const key = planes.length ? [...planes].sort().join("+") : "resources";
  return `${key}:${cacheKey}`;
}

export function applyFull(
  payload: MetricsPayload,
  setSeries: (s: MetricsSeries[]) => void,
  setAvailable: (a: MetricsAvailable[]) => void,
  setEvents: (e: GraphEvent[]) => void,
) {
  setSeries(payload.series);
  setAvailable(payload.available);
  setEvents(payload.events ?? []);
}

export function applyPayloadMeta(
  payload: MetricsPayload,
  setBounds: (b: MetricsBounds | null) => void,
  setClampMessage: (m: string | null) => void,
  setRangeTo: (t: string | null) => void,
  setWindowSec: (n: number) => void,
) {
  setBounds(payload.bounds ?? null);
  setClampMessage(payload.clamped ? payload.clamp_message ?? null : null);
  setRangeTo(payload.to);
  setWindowSec(payload.window_seconds);
}

/** Full fetch for every selected plane; merges series fields by service + time. */
export async function fetchPlanes(
  planes: MetricPlane[],
  query: MetricsQueryOpts,
): Promise<{ payload: MetricsPayload; cursors: PlaneCursors }> {
  const list = planes.length ? planes : (["resources"] as MetricPlane[]);
  const pairs = await Promise.all(
    list.map(async (plane) => {
      const payload = await metricsFetcher(plane)(query as MetricsQuery);
      return [plane, payload] as const;
    }),
  );
  const cursors: PlaneCursors = {};
  for (const [plane, payload] of pairs) cursors[plane] = payload.cursor;
  return { payload: mergePayloads(pairs.map(([, p]) => p)), cursors };
}

export async function pollPlanes(
  query: MetricsQueryOpts,
  planes: MetricPlane[],
  cursors: PlaneCursors,
  setSeries: Dispatch<SetStateAction<MetricsSeries[]>>,
  setAvailable: (a: MetricsAvailable[]) => void,
  setCursors: (c: PlaneCursors) => void,
  setEvents: (e: GraphEvent[]) => void,
) {
  const list = planes.length ? planes : (["resources"] as MetricPlane[]);
  try {
    const pairs = await Promise.all(
      list.map(async (plane) => {
        const payload = await metricsFetcher(plane)({
          ...query,
          since: cursors[plane] ?? undefined,
        } as MetricsQuery);
        return [plane, payload] as const;
      }),
    );
    const nextCursors = { ...cursors };
    let available: MetricsAvailable[] = [];
    let events: GraphEvent[] = [];
    let delta: MetricsSeries[] = [];
    for (const [plane, payload] of pairs) {
      if (payload.cursor) nextCursors[plane] = payload.cursor;
      available = mergeAvailable(available, payload.available);
      events = [...events, ...(payload.events ?? [])];
      delta = mergeSeries(delta, payload.series);
    }
    if (available.length) setAvailable(available);
    setEvents(events);
    setCursors(nextCursors);
    if (delta.length) setSeries((prev) => mergeSeries(prev, delta));
  } catch {
    /* keep last good chart on transient poll errors */
  }
}

export function mergePayloads(payloads: MetricsPayload[]): MetricsPayload {
  if (payloads.length === 0) {
    return emptyPayload();
  }
  if (payloads.length === 1) return payloads[0];
  let series: MetricsSeries[] = [];
  let available: MetricsAvailable[] = [];
  let events: GraphEvent[] = [];
  for (const p of payloads) {
    series = mergeSeries(series, p.series);
    available = mergeAvailable(available, p.available);
    events = [...events, ...(p.events ?? [])];
  }
  const primary = payloads[0];
  return {
    ...primary,
    series,
    available,
    events,
    clamped: payloads.some((p) => p.clamped),
    clamp_message: payloads.map((p) => p.clamp_message).find(Boolean),
  };
}

export function mergeSeries(
  prev: MetricsSeries[],
  delta: MetricsSeries[],
): MetricsSeries[] {
  const map = new Map(
    prev.map((s) => [s.id, { ...s, points: s.points.map((p) => ({ ...p })) }]),
  );
  for (const s of delta) {
    const cur = map.get(s.id);
    if (!cur) {
      map.set(s.id, { ...s, points: s.points.map((p) => ({ ...p })) });
      continue;
    }
    const byT = new Map(cur.points.map((p) => [p.t, p]));
    for (const p of s.points) {
      const existing = byT.get(p.t);
      if (existing) Object.assign(existing, p);
      else {
        const copy = { ...p };
        cur.points.push(copy);
        byT.set(p.t, copy);
      }
    }
  }
  return [...map.values()];
}

export function toggleId(active: string[], id: string, order: string[]): string[] {
  if (active.includes(id)) {
    return active.filter((x) => x !== id);
  }
  const next = [...active, id];
  return order.filter((x) => next.includes(x));
}

function mergeAvailable(
  prev: MetricsAvailable[],
  extra: MetricsAvailable[],
): MetricsAvailable[] {
  const map = new Map(prev.map((a) => [a.id, a]));
  for (const a of extra) {
    if (!map.has(a.id)) map.set(a.id, a);
  }
  return [...map.values()];
}

function emptyPayload(): MetricsPayload {
  return {
    window_seconds: 0,
    from: "",
    to: "",
    cursor: null,
    available: [],
    series: [],
  };
}
