import { useRef, useState } from "react";
import type { ServiceAction } from "./api";
import { postServiceAction } from "./api";

export type ServiceConfirmRequest = {
  action: ServiceAction;
  title: string;
  message: string;
  confirmLabel: string;
  danger: boolean;
};

export type ServiceActionRunner = {
  busy: ServiceAction | null;
  error: string | null;
  message: string | null;
  locked: boolean;
  confirm: ServiceConfirmRequest | null;
  run: (action: ServiceAction) => Promise<void>;
  acceptConfirm: () => void;
  cancelConfirm: () => void;
};

/** Shared start/stop/redeploy runner (custom confirm + POST + busy/error). */
export function useServiceActionRunner(
  service: string,
  onDone: () => void,
  disabled = false,
): ServiceActionRunner {
  const [busy, setBusy] = useState<ServiceAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<ServiceConfirmRequest | null>(null);
  const resolveConfirm = useRef<((ok: boolean) => void) | null>(null);
  const locked = disabled || busy !== null || confirm !== null;

  const run = async (action: ServiceAction) => {
    if (!(await askConfirm(action, service))) return;
    setBusy(action);
    setError(null);
    setMessage(null);
    try {
      await postServiceAction(service, action);
      setMessage(`${labelFor(action)} succeeded.`);
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : `${labelFor(action)} failed.`);
    } finally {
      setBusy(null);
    }
  };

  return {
    busy,
    error,
    message,
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
