import { useEffect, useState } from "react";
import { liveNowIntervalMs } from "./chartTimeScale";

/**
 * Wall-clock ms that advances while ``enabled`` (live rolling charts).
 * Ticks scale with ``windowSeconds`` so long windows do not re-render every
 * chart each second for sub-pixel axis movement.
 */
export function useLiveNow(enabled: boolean, windowSeconds: number): number {
  const [nowMs, setNowMs] = useState(() => Date.now());
  const intervalMs = liveNowIntervalMs(windowSeconds);
  useEffect(() => {
    if (!enabled) return;
    const tick = () => setNowMs(Date.now());
    tick();
    const id = window.setInterval(tick, intervalMs);
    return () => window.clearInterval(id);
  }, [enabled, intervalMs]);
  return nowMs;
}
