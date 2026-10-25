import { lazy, Suspense, useEffect, useState } from "react";
import { ChartFrameSkeleton } from "../chrome/skeleton";
import { trendsDeferDelayMs, trendsDeferPhase } from "./trendsDefer";

const TrendsDashboard = lazy(() =>
  import("../trends/dashboard/ui/TrendsDashboard").then((mod) => ({
    default: mod.TrendsDashboard,
  })),
);

/** Mount Trends only after first status paint (lazy + macrotask deferral). */
export function DeferredTrends(props: { hasStatusData: boolean }) {
  const [idleElapsed, setIdleElapsed] = useState(false);
  const delayMs = trendsDeferDelayMs(props.hasStatusData);

  useEffect(() => {
    if (delayMs === null) {
      setIdleElapsed(false);
      return;
    }
    const id = window.setTimeout(() => setIdleElapsed(true), delayMs);
    return () => window.clearTimeout(id);
  }, [delayMs]);

  const phase = trendsDeferPhase(props.hasStatusData, idleElapsed);
  if (phase === "blocked") return null;
  if (phase === "scheduled") {
    return (
      <ChartFrameSkeleton label="Loading trends…" id="trends-deferred" />
    );
  }
  return (
    <Suspense
      fallback={
        <ChartFrameSkeleton label="Loading trends…" id="trends-deferred" />
      }
    >
      <TrendsDashboard />
    </Suspense>
  );
}
