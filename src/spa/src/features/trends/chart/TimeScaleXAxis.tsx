import type { ReactElement } from "react";
import { XAxis } from "recharts";
import {
  formatTickTime,
  timeAxisTicks,
  windowDomain,
} from "./chartTimeScale";

/**
 * Numeric epoch X axis over the selected metrics window.
 *
 * Must be inlined as ``{timeScaleXAxis(...)}`` — Recharts only discovers
 * ``XAxis`` among *direct* chart children (wrapper components are skipped).
 */
export function timeScaleXAxis(
  windowSeconds: number,
  endMs: number = Date.now(),
): ReactElement {
  const domain = windowDomain(windowSeconds, endMs);
  const ticks = timeAxisTicks(domain);
  const spanMs = domain.endMs - domain.startMs;
  return (
    <XAxis
      dataKey="ts"
      type="number"
      domain={[domain.startMs, domain.endMs]}
      ticks={ticks}
      allowDataOverflow
      tick={{ fill: "var(--muted)", fontSize: 11 }}
      minTickGap={28}
      tickFormatter={(ms: number) => formatTickTime(ms, spanMs)}
    />
  );
}
