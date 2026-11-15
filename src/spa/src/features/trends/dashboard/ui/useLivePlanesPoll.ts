import {
  startTransition,
  useEffect,
  useRef,
  type Dispatch,
  type SetStateAction,
} from "react";
import {
  METRICS_POLL_MS,
  type GraphEvent,
  type MetricsAvailable,
  type MetricsSeries,
} from "../../../../shared/api";
import { livePollPlan } from "../../chart/liveClock";
import { pollPlanes, type PlaneCursors } from "../../panel/trendsPoll";
import type { MetricsQueryOpts } from "../../range/index.ts";
import type { MetricPlane } from "../../runtimeMetrics";

/** Stable ``useState`` dispatchers the poll writes into. */
export type LivePollSetters = {
  setSeries: Dispatch<SetStateAction<MetricsSeries[]>>;
  setAvailable: (a: MetricsAvailable[]) => void;
  setCursors: (c: PlaneCursors) => void;
  setEvents: (e: GraphEvent[]) => void;
};

/**
 * ``since``-cursor poll for live dashboards. Paused while charts are
 * off-screen; polls once immediately on scroll-back. Updates are transitions
 * so appending samples never blocks pointer input.
 */
export function useLivePlanesPoll(args: {
  query: MetricsQueryOpts;
  planes: MetricPlane[];
  cursors: PlaneCursors;
  busy: boolean;
  live: boolean;
  visible: boolean;
  setters: LivePollSetters;
}): void {
  const { query, planes, cursors, busy, live, visible } = args;
  const { setSeries, setAvailable, setCursors, setEvents } = args.setters;
  const resumed = useRef(false);
  useEffect(() => {
    if (!visible) resumed.current = true;
  }, [visible]);
  useEffect(() => {
    const plan = livePollPlan({ busy, live, visible, resumed: resumed.current });
    if (!plan.run) return;
    resumed.current = false;
    const s = transitionSetters({ setSeries, setAvailable, setCursors, setEvents });
    const poll = () => {
      void pollPlanes(query, planes, cursors, s.setSeries, s.setAvailable, s.setCursors, s.setEvents);
    };
    if (plan.pollNow) poll();
    const id = window.setInterval(poll, METRICS_POLL_MS);
    return () => window.clearInterval(id);
  }, [query, cursors, busy, planes, live, visible, setSeries, setAvailable, setCursors, setEvents]);
}

function transitionSetters(s: LivePollSetters): LivePollSetters {
  return {
    setSeries: (v) => startTransition(() => s.setSeries(v)),
    setAvailable: (v) => startTransition(() => s.setAvailable(v)),
    setCursors: (v) => startTransition(() => s.setCursors(v)),
    setEvents: (v) => startTransition(() => s.setEvents(v)),
  };
}
