import { useState } from "react";
import { postServiceAction, type ServiceAction } from "./api";

export type ServiceActionRunner = {
  busy: ServiceAction | null;
  error: string | null;
  message: string | null;
  locked: boolean;
  run: (action: ServiceAction) => Promise<void>;
};

/** Shared start/stop/redeploy runner (confirm + POST + busy/error). */
export function useServiceActionRunner(
  service: string,
  onDone: () => void,
  disabled = false,
): ServiceActionRunner {
  const [busy, setBusy] = useState<ServiceAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const locked = disabled || busy !== null;

  const run = async (action: ServiceAction) => {
    if (!confirmAction(action, service)) return;
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

  return { busy, error, message, locked, run };
}

function confirmAction(action: ServiceAction, service: string): boolean {
  if (action === "start") return true;
  if (action === "stop") {
    return window.confirm(
      `Stop ${service}? Traffic to this service will fail until it is started again.`,
    );
  }
  return window.confirm(
    `Redeploy ${service}? This re-renders and updates the service (brief disruption).`,
  );
}

function labelFor(action: ServiceAction): string {
  if (action === "start") return "Start";
  if (action === "stop") return "Stop";
  return "Redeploy";
}
