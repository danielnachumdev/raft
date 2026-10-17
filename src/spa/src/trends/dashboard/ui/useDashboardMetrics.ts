import { useEffect, useMemo, useState } from "react";
import {
  METRICS_POLL_MS,
  type GraphEvent,
  type MetricsAvailable,
  type MetricsBounds,
  type MetricsSeries,
} from "../../../shared/api";
import { peekMetrics, putMetrics } from "../../../shared/dashboardCache";
import { chartEndMs } from "../../chart/chartTimeScale";
import { useLiveNow } from "../../chart/useLiveNow";
import {
  applyFull,
  applyPayloadMeta,
  fetchPlanes,
  planesCacheKey,
  pollPlanes,
  type PlaneCursors,
} from "../../panel/trendsPoll";
import {
  isLiveQuery,
  isRollingWindow,
  metricsCacheKey,
  toQuery,
  type TrendsRangeState,
} from "../../range/index.ts";
import type { MetricPlane } from "../../runtimeMetrics";

export type DashboardMetrics = {
  series: MetricsSeries[];
  available: MetricsAvailable[];
  events: GraphEvent[];
  bounds: MetricsBounds | null;
  clampMessage: string | null;
  windowSec: number;
  rangeEndMs: number;
  live: boolean;
  busy: boolean;
  error: string | null;
};

/**
 * One full fetch + live poll per metric plane for the whole dashboard;
 * every graph filters the shared series client-side.
 * Optional ``services`` scopes the request (service inspection page).
 */
export function useDashboardMetrics(
  range: TrendsRangeState,
  planeList: MetricPlane[],
  services?: string[],
): DashboardMetrics {
  const planesKey = planeList.join("+");
  const planes = useMemo(() => planesKey.split("+") as MetricPlane[], [planesKey]);
  const servicesKey = services?.join(",") ?? "";
  const query = useMemo(() => {
    const base = toQuery(range);
    return servicesKey
      ? { ...base, services: servicesKey.split(",") }
      : base;
  }, [range, servicesKey]);
  const rolling = isRollingWindow(query);
  const nowMs = useLiveNow(rolling);
  const cacheKey = `${planesCacheKey(planes, metricsCacheKey(query))}:svc:${servicesKey}`;
  const seed = peekMetrics(cacheKey);
  const [series, setSeries] = useState<MetricsSeries[]>(seed?.series ?? []);
  const [available, setAvailable] = useState<MetricsAvailable[]>(seed?.available ?? []);
  const [events, setEvents] = useState<GraphEvent[]>(seed?.events ?? []);
  const [cursors, setCursors] = useState<PlaneCursors>({});
  const [bounds, setBounds] = useState<MetricsBounds | null>(seed?.bounds ?? null);
  const [clampMessage, setClampMessage] = useState<string | null>(null);
  const [rangeTo, setRangeTo] = useState<string | null>(seed?.to ?? null);
  const [windowSec, setWindowSec] = useState(query.window);
  const [busy, setBusy] = useState(seed === null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const setters: Setters = {
      setSeries,
      setAvailable,
      setEvents,
      setBounds,
      setClampMessage,
      setRangeTo,
      setWindowSec,
    };
    const cached = peekMetrics(cacheKey);
    // Keep prior samples on screen when the new key misses cache so graphs
    // can show a refresh overlay instead of flashing empty.
    if (cached) seedFromCache(cached, setters);
    setCursors({});
    setBusy(true);
    setError(null);
    void (async () => {
      try {
        const { payload, cursors: next } = await fetchPlanes(planes, query);
        if (cancelled) return;
        putMetrics(cacheKey, payload);
        seedFromCache(payload, setters);
        setCursors(next);
      } catch {
        if (!cancelled && !cached) setError("Failed to load metrics history.");
      } finally {
        if (!cancelled) setBusy(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [cacheKey, planes, query]);

  const live = isLiveQuery(query);
  useEffect(() => {
    if (busy || !live) return;
    const id = window.setInterval(() => {
      void pollPlanes(query, planes, cursors, setSeries, setAvailable, setCursors, setEvents);
    }, METRICS_POLL_MS);
    return () => window.clearInterval(id);
  }, [query, cursors, busy, planes, live]);

  const scopedAvailable = useMemo(
    () => scopeAvailable(available, servicesKey),
    [available, servicesKey],
  );

  return {
    series,
    available: scopedAvailable,
    events,
    bounds,
    clampMessage,
    windowSec,
    rangeEndMs: chartEndMs({ rolling, nowMs, rangeEndIso: rangeTo }),
    live,
    busy,
    error,
  };
}

/** When the fetch is service-scoped, hide unrelated catalog rows from graphs. */
function scopeAvailable(
  available: MetricsAvailable[],
  servicesKey: string,
): MetricsAvailable[] {
  if (!servicesKey) return available;
  const want = new Set(servicesKey.split(","));
  return available.filter((a) => want.has(a.id));
}

type Setters = {
  setSeries: (s: MetricsSeries[]) => void;
  setAvailable: (a: MetricsAvailable[]) => void;
  setEvents: (e: GraphEvent[]) => void;
  setBounds: (b: MetricsBounds | null) => void;
  setClampMessage: (m: string | null) => void;
  setRangeTo: (t: string | null) => void;
  setWindowSec: (n: number) => void;
};

function seedFromCache(
  payload: ReturnType<typeof peekMetrics>,
  s: Setters,
): void {
  if (!payload) {
    s.setSeries([]);
    s.setAvailable([]);
    s.setEvents([]);
    return;
  }
  applyFull(payload, s.setSeries, s.setAvailable, s.setEvents);
  applyPayloadMeta(payload, s.setBounds, s.setClampMessage, s.setRangeTo, s.setWindowSec);
}
