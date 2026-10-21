/** Always-on dashboard self-Redeploy: reconnect poll after 202 started. */

import type { ServiceActionResult } from "../shared/api";

export const DASHBOARD_COMPOSE_ID = "raft-dashboard";

/** Rebuild + edge reload can take several minutes on a cold image pull. */
export const DASHBOARD_REDEPLOY_TIMEOUT_MS = 600_000;
export const DASHBOARD_REDEPLOY_POLL_MS = 2_000;

export type DashboardRedeployOutcome = "ok" | "timeout";

export function isDashboardService(service: string): boolean {
  return service === DASHBOARD_COMPOSE_ID || service === "dashboard";
}

export function isAsyncDashboardRedeploy(
  service: string,
  action: string,
  result: ServiceActionResult,
): boolean {
  return (
    action === "redeploy" &&
    isDashboardService(service) &&
    result.started === true
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
    "Dashboard redeploy is taking longer than expected. " +
    "Check Events, or on the host run `raft doctor` / `raft redeploy dashboard`."
  );
}

function defaultSleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}
