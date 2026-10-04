import { useRef, useState } from "react";
import type { ServiceAction } from "./api";
import { postServiceAction, servicePath } from "./api";
import { toast } from "./toast";

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

/** Shared start/stop/redeploy: custom confirm modal + POST + toast feedback. */
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
      await postServiceAction(service, action);
      toast.good({
        message: `${labelFor(action)} succeeded for ${service}.`,
        href: servicePath(service),
        linkLabel: "View service",
      });
      onDone();
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

function confirmRequestFor(
  action: ServiceAction,
  service: string,
): ServiceConfirmRequest | null {
  if (action === "start") return null;
  if (action === "stop") {
    return {
      action,
      title: `Stop ${service}?`,
      message:
        "Traffic to this service will fail until it is started again.",
      confirmLabel: "Stop",
      danger: true,
    };
  }
  return {
    action,
    title: `Redeploy ${service}?`,
    message:
      "This re-renders and updates the service (brief disruption).",
    confirmLabel: "Redeploy",
    danger: false,
  };
}

function labelFor(action: ServiceAction): string {
  if (action === "start") return "Start";
  if (action === "stop") return "Stop";
  return "Redeploy";
}
