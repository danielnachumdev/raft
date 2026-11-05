export function logsDownloadUrl(
  name: string,
  formatId: string,
  tail: number,
): string {
  const params = new URLSearchParams();
  params.set("format", formatId);
  params.set("tail", String(tail));
  return `/api/service/${encodeURIComponent(name)}/logs/download?${params.toString()}`;
}

export function metricsDownloadUrl(opts: {
  formatId: string;
  window: number;
  services?: string[];
}): string {
  const params = new URLSearchParams();
  params.set("format", opts.formatId);
  params.set("window", String(opts.window));
  if (opts.services && opts.services.length > 0) {
    params.set("services", opts.services.join(","));
  }
  return `/api/metrics/download?${params.toString()}`;
}
