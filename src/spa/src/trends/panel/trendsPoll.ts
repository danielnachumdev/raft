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

export function metricsFetcher(plane: MetricPlane) {
  return plane === "http" ? fetchHttpMetrics : fetchMetrics;
}

export function applyFull(
  payload: MetricsPayload,
  setSeries: (s: MetricsSeries[]) => void,
  setAvailable: (a: MetricsAvailable[]) => void,
  setCursor: (c: string | null) => void,
  setEvents: (e: GraphEvent[]) => void,
) {
  setSeries(payload.series);
  setAvailable(payload.available);
  setCursor(payload.cursor);
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

export async function pollIncremental(
  query: MetricsQueryOpts,
  cursor: string | null,
  setSeries: Dispatch<SetStateAction<MetricsSeries[]>>,
  setAvailable: (a: MetricsAvailable[]) => void,
  setCursor: (c: string | null) => void,
  setEvents: (e: GraphEvent[]) => void,
  plane: MetricPlane = "resources",
) {
  try {
    const fetchHistory = metricsFetcher(plane);
    const payload = await fetchHistory({
      ...query,
      since: cursor ?? undefined,
    } as MetricsQuery);
    if (payload.available.length) setAvailable(payload.available);
    setEvents(payload.events ?? []);
    if (!payload.series.length) return;
    setSeries((prev) => mergeSeries(prev, payload.series));
    if (payload.cursor) setCursor(payload.cursor);
  } catch {
    /* keep last good chart on transient poll errors */
  }
}

export function mergeSeries(
  prev: MetricsSeries[],
  delta: MetricsSeries[],
): MetricsSeries[] {
  const map = new Map(prev.map((s) => [s.id, { ...s, points: [...s.points] }]));
  for (const s of delta) {
    const cur = map.get(s.id);
    if (!cur) {
      map.set(s.id, { ...s, points: [...s.points] });
      continue;
    }
    const seen = new Set(cur.points.map((p) => p.t));
    for (const p of s.points) {
      if (!seen.has(p.t)) cur.points.push(p);
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
