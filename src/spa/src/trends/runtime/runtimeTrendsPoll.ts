import type { Dispatch, SetStateAction } from "react";
import {
  fetchMetrics,
  type GraphEvent,
  type MetricsSeries,
} from "../../shared/api";
import {
  mergeTimedRows,
  toEpochMs,
} from "../chart/chartTimeScale";
import { runtimePointValue, type RuntimeMetricId } from "../runtimeMetrics";

export type ChartRow = {
  ts: number;
  t: string;
  label: string;
  value: number | null;
};

export function buildRows(
  series: MetricsSeries | null,
  metric: RuntimeMetricId,
): ChartRow[] {
  if (!series) return [];
  const points = series.points
    .map((p) => {
      const ts = toEpochMs(p.t);
      if (ts === null) return null;
      return { ts, t: p.t, value: runtimePointValue(p, metric) };
    })
    .filter((p): p is NonNullable<typeof p> => p !== null);
  return mergeTimedRows([{ key: "value", points }]) as ChartRow[];
}

export async function pollServiceMetrics(
  service: string,
  query: { window: number; start?: string; end?: string },
  cursor: string | null,
  setSeries: Dispatch<SetStateAction<MetricsSeries | null>>,
  setCursor: (c: string | null) => void,
  setEvents: (e: GraphEvent[]) => void,
) {
  try {
    const payload = await fetchMetrics({
      ...query,
      since: cursor ?? undefined,
      services: [service],
    });
    setEvents(payload.events ?? []);
    const delta = payload.series.find((s) => s.id === service);
    if (delta && delta.points.length) {
      setSeries((prev) => mergePoints(prev, delta));
    }
    if (payload.cursor) setCursor(payload.cursor);
  } catch {
    /* keep last good chart */
  }
}

export function mergePoints(
  prev: MetricsSeries | null,
  delta: MetricsSeries,
): MetricsSeries {
  if (!prev) return delta;
  const seen = new Set(prev.points.map((p) => p.t));
  const points = [...prev.points];
  for (const p of delta.points) {
    if (!seen.has(p.t)) points.push(p);
  }
  return { ...prev, points };
}
