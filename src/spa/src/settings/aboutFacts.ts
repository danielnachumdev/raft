/** Pure About-section rows from a status host + version snapshot. */

import {
  type HostStatus,
  type RaftVersion,
  versionChromeText,
} from "../shared/api/index.ts";
import {
  formatBytes,
  formatDuration,
  formatPercent,
} from "../shared/format.ts";

export type AboutFactRow = { label: string; value: string; mono?: boolean };

/** Read-only facts for Settings → About (dummy-safe; no settings.yaml). */
export function aboutFactRows(
  host: HostStatus | undefined,
  version: RaftVersion | undefined,
): AboutFactRow[] {
  const mem = host?.memory;
  const disk = host?.disk;
  const load = host?.loadavg;
  const rows: AboutFactRow[] = [
    {
      label: "raft version",
      value: version ? version.line || versionChromeText(version) : "-",
      mono: true,
    },
    {
      label: "Hostname",
      value: stringOrDash(host?.hostname),
      mono: true,
    },
  ];
  const fqdn = typeof host?.fqdn === "string" ? host.fqdn.trim() : "";
  if (fqdn && fqdn !== host?.hostname) {
    rows.push({ label: "FQDN", value: fqdn, mono: true });
  }
  rows.push(
    {
      label: "CPUs",
      value: host?.cpus != null ? String(host.cpus) : "-",
    },
    {
      label: "Load average",
      value:
        Array.isArray(load) && load.length >= 3
          ? load
              .slice(0, 3)
              .map((n) => Number(n).toFixed(2))
              .join(" / ")
          : "-",
    },
    {
      label: "Memory",
      value:
        mem?.used_bytes != null || mem?.total_bytes != null
          ? `${formatBytes(mem?.used_bytes)} / ${formatBytes(mem?.total_bytes)}`
            + ` (${formatPercent(mem?.used_percent)})`
          : "-",
    },
    {
      label: "Disk",
      value:
        disk?.used_bytes != null || disk?.total_bytes != null
          ? `${formatBytes(disk?.used_bytes)} / ${formatBytes(disk?.total_bytes)}`
            + ` (${formatPercent(disk?.used_percent)})`
          : "-",
    },
    {
      label: "Uptime",
      value: formatDuration(
        typeof host?.uptime_seconds === "number" ? host.uptime_seconds : null,
      ),
    },
  );
  return rows;
}

function stringOrDash(value: unknown): string {
  return typeof value === "string" && value.trim() ? value.trim() : "-";
}
