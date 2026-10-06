import { useEffect, useState } from "react";

/** Wall-clock ms that advances while ``enabled`` (live rolling charts). */
export function useLiveNow(enabled: boolean, intervalMs = 1000): number {
  const [nowMs, setNowMs] = useState(() => Date.now());
  useEffect(() => {
    if (!enabled) return;
    const tick = () => setNowMs(Date.now());
    tick();
    const id = window.setInterval(tick, intervalMs);
    return () => window.clearInterval(id);
  }, [enabled, intervalMs]);
  return nowMs;
}
