/** Detached host Redeploy: poll after API returns ``started: true``. */

import type { ServiceActionResult } from "../../shared/api";

export const DASHBOARD_COMPOSE_ID = "raft-dashboard";

/** Rebuild + readiness can take several minutes on a cold image pull. */
export const DASHBOARD_REDEPLOY_TIMEOUT_MS = 600_000;
export const DASHBOARD_REDEPLOY_POLL_MS = 2_000;

export type DashboardRedeployOutcome = "ok" | "timeout";

export function isDashboardService(service: string): boolean {
  return service === DASHBOARD_COMPOSE_ID || service === "dashboard";
}

/** Detached oneshot from always-on dashboard (app or dashboard self-redeploy). */
export function isAsyncRedeploy(
  action: string,
  result: ServiceActionResult,
): boolean {
  return action === "redeploy" && result.started === true;
}

/** @deprecated Prefer ``isAsyncRedeploy``; kept for dashboard-only call sites. */
export function isAsyncDashboardRedeploy(
  service: string,
  action: string,
  result: ServiceActionResult,
): boolean {
  return (
    isAsyncRedeploy(action, result) && isDashboardService(service)
  );
}

export async function waitForDashboardReconnect(opts: {
  probe: () => Promise<boolean>;
  timeoutMs?: number;
  intervalMs?: number;
  sleep?: (ms: number) => Promise<void>;
  now?: () => number;
}): Promise<DashboardRedeployOutcome> {
  const timeoutMs = opts.timeoutMs ?? DASHBOARD_REDEPLOY_TIMEOUT_MS;
  const intervalMs = opts.intervalMs ?? DASHBOARD_REDEPLOY_POLL_MS;
  const sleep = opts.sleep ?? defaultSleep;
  const now = opts.now ?? Date.now;
  const deadline = now() + timeoutMs;
  while (now() < deadline) {
    try {
      if (await opts.probe()) return "ok";
    } catch {
      // API unreachable while the container rebuilds — keep polling.
    }
    await sleep(intervalMs);
  }
  return "timeout";
}

export function dashboardRedeployTimeoutMessage(): string {
  return (
    "Dashboard redeploy is taking longer than expected. Check Events."
  );
}

export function asyncRedeployTimeoutMessage(service: string): string {
  if (isDashboardService(service)) {
    return dashboardRedeployTimeoutMessage();
  }
  return `Redeploy of ${service} is taking longer than expected. Check Events.`;
}

function defaultSleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}
