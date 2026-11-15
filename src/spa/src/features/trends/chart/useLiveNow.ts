import { startTransition, useEffect, useState } from "react";
import { liveNowIntervalMs } from "./chartTimeScale";
import { liveClockRunning } from "./liveClock";

/**
 * Wall-clock ms that advances while ``enabled`` (live rolling charts) and
 * ``visible`` (charts near the viewport).
 * Ticks scale with ``windowSeconds`` so long windows do not re-render every
 * chart each second for sub-pixel axis movement; ticks are transitions so the
 * chart re-layout yields to pointer input.
 */
export function useLiveNow(
  enabled: boolean,
  windowSeconds: number,
  visible: boolean = true,
): number {
  const [nowMs, setNowMs] = useState(() => Date.now());
  const intervalMs = liveNowIntervalMs(windowSeconds);
  const running = liveClockRunning(enabled, visible);
  useEffect(() => {
    if (!running) return;
    const tick = () => startTransition(() => setNowMs(Date.now()));
    tick();
    const id = window.setInterval(tick, intervalMs);
    return () => window.clearInterval(id);
  }, [running, intervalMs]);
  return nowMs;
}
