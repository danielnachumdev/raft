import { useRef, useState } from "react";
import type { ServiceAction } from "../shared/api";
import { fetchService, postServiceAction, servicePath } from "../shared/api";
import { toast } from "../chrome/toast";
import {
  dashboardRedeployTimeoutMessage,
  isAsyncDashboardRedeploy,
  isDashboardService,
  waitForDashboardReconnect,
} from "./dashboardRedeploy";

export type ServiceConfirmRequest = {
  action: ServiceAction;
  title: string;
  message: string;
  confirmLabel: string;
  danger: boolean;
};

export type ServiceActionRunner = {
  busy: ServiceAction | null;
  locked: boolean;
  confirm: ServiceConfirmRequest | null;
  run: (action: ServiceAction) => Promise<void>;
  acceptConfirm: () => void;
  cancelConfirm: () => void;
};

/** Shared up/down/redeploy: custom confirm modal + POST + toast feedback. */
export function useServiceActionRunner(
  service: string,
  onDone: () => void,
  disabled = false,
): ServiceActionRunner {
  const [busy, setBusy] = useState<ServiceAction | null>(null);
  const [confirm, setConfirm] = useState<ServiceConfirmRequest | null>(null);
  const resolveConfirm = useRef<((ok: boolean) => void) | null>(null);
  const locked = disabled || busy !== null || confirm !== null;

  const run = async (action: ServiceAction) => {
    if (!(await askConfirm(action, service))) return;
    setBusy(action);
    try {
      await runAction(service, action, onDone);
    } catch (err) {
      const detail =
        err instanceof Error ? err.message : `${labelFor(action)} failed.`;
      toast.bad(`${labelFor(action)} failed: ${detail}`);
    } finally {
      setBusy(null);
    }
  };

  return {
    busy,
    locked,
    confirm,
    run,
    acceptConfirm: () => finishConfirm(true),
    cancelConfirm: () => finishConfirm(false),
  };

  function askConfirm(
    action: ServiceAction,
    name: string,
  ): Promise<boolean> {
    const request = confirmRequestFor(action, name);
    if (!request) return Promise.resolve(true);
    return new Promise((resolve) => {
      resolveConfirm.current = resolve;
      setConfirm(request);
    });
  }

  function finishConfirm(ok: boolean) {
    const resolve = resolveConfirm.current;
    resolveConfirm.current = null;
    setConfirm(null);
    resolve?.(ok);
  }
}

async function runAction(
  service: string,
  action: ServiceAction,
  onDone: () => void,
): Promise<void> {
  const result = await postServiceAction(service, action);
  if (isAsyncDashboardRedeploy(service, action, result)) {
    await finishDashboardRedeploy(service, onDone);
    return;
  }
  toast.good({
    message: `${labelFor(action)} succeeded for ${service}.`,
    href: servicePath(service),
    linkLabel: "View service",
  });
  onDone();
}

async function finishDashboardRedeploy(
  service: string,
  onDone: () => void,
): Promise<void> {
  toast.good({ message: "Redeploying…" });
  const outcome = await waitForDashboardReconnect({
    probe: () => probeDashboardHealthy(service),
  });
  if (outcome === "timeout") {
    toast.bad(dashboardRedeployTimeoutMessage());
    return;
  }
  toast.good({
    message: `Redeploy succeeded for ${service}.`,
    href: servicePath(service),
    linkLabel: "View service",
  });
  onDone();
  window.location.reload();
}

async function probeDashboardHealthy(service: string): Promise<boolean> {
  const detail = await fetchService(service);
  const status = (detail.presentation?.status || "").toLowerCase();
  return status === "running" || status.startsWith("up");
}

function confirmRequestFor(
  action: ServiceAction,
  service: string,
): ServiceConfirmRequest | null {
  if (action === "start") return null;
  if (action === "stop") {
    return {
      action,
      title: `Down ${service}?`,
      message:
        "Traffic to this service will fail until it is brought up again.",
      confirmLabel: "Down",
      danger: true,
    };
  }
  return {
    action,
    title: `Redeploy ${service}?`,
    message: redeployMessage(service),
    confirmLabel: "Redeploy",
    danger: false,
  };
}

function redeployMessage(service: string): string {
  if (isDashboardService(service)) {
    return (
      "Rebuilds the dashboard image on the host. This UI disconnects " +
      "briefly, then reconnects when ready."
    );
  }
  if (isGateService(service)) {
    return (
      "Recreates the public edge container to pick up published ports " +
      "(brief edge downtime — typically 1–2s). Not a substitute for " +
      "sync or render alone."
    );
  }
  return (
    "Re-renders and updates the service (brief disruption). " +
    "Not a substitute for sync or render alone."
  );
}

function isGateService(service: string): boolean {
  const key = service.trim().toLowerCase();
  return key === "gate" || key === "raft-gate";
}

function labelFor(action: ServiceAction): string {
  if (action === "start") return "Up";
  if (action === "stop") return "Down";
  return "Redeploy";
}
