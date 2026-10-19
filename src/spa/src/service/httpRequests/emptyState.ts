/** Copy for empty / idle HTTP request inspection (not eligibility). */

export function isIdleContainerStatus(status: string): boolean {
  const key = status.trim().toLowerCase();
  return (
    key === "scaled-to-zero" ||
    key === "not running" ||
    key === "exited" ||
    key === "dead"
  );
}

export function httpRequestsEmptyLabel(opts: {
  scaledToZero: boolean;
  idleContainer: boolean;
}): string {
  if (opts.scaledToZero || opts.idleContainer) {
    return "No retained HTTP requests for this service in the gate access log.";
  }
  return "No recent HTTP requests for this service.";
}

export function httpRequestsIdleHint(opts: {
  scaledToZero: boolean;
  idleContainer: boolean;
}): string | null {
  if (opts.scaledToZero) {
    return (
      "App is scaled to zero — past edge requests still appear when present; " +
      "new proxied traffic will wake it."
    );
  }
  if (opts.idleContainer) {
    return (
      "App is not running — showing recent edge rows if any remain in the " +
      "access log."
    );
  }
  return null;
}
