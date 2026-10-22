/** Which lifecycle actions make sense for a status string, with tooltips. */

import type { ServiceAction } from "../shared/api/index.ts";

export type ActionAvailability = Record<
  ServiceAction,
  { enabled: boolean; hint: string }
>;

const STOPPED = new Set(["exited", "not running", "dead", "created"]);

const HINTS: Record<ServiceAction, string> = {
  up: "Bring this service up with Compose (clears scale-to-zero idle).",
  down: "Bring this service down with Compose (scale-to-zero apps are marked idle).",
  redeploy:
    "Refresh generation: cut over a running app, recreate the router/gate, or rebuild the dashboard. Controller redeploy is refused. Gate redeploy briefly drops the public edge.",
};

export function actionAvailability(
  status: string | null | undefined,
): ActionAvailability {
  const key = (status ?? "").trim().toLowerCase();
  const running = key === "running";
  const stopped = STOPPED.has(key);
  return {
    up: running
      ? { enabled: false, hint: "Already running." }
      : { enabled: true, hint: HINTS.up },
    down: stopped
      ? { enabled: false, hint: "Already down." }
      : { enabled: true, hint: HINTS.down },
    redeploy: { enabled: true, hint: HINTS.redeploy },
  };
}
