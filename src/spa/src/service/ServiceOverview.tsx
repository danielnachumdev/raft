import { StatTile, StatTiles } from "../chrome/StatTile";
import type { ServiceDetailPayload } from "../shared/api";
import { formatBytes, formatCount, formatDuration } from "../shared/format";
import {
  parseMemoryRatioPercent,
  parsePercent,
  utilTone,
  type UtilTone,
} from "../status/model/statusTone";

/** Live headline numbers for one service (uptime, CPU, memory, I/O). */
export function ServiceOverview(props: { data: ServiceDetailPayload }) {
  const { container: c, presentation: p } = props.data;
  const uptime = c.uptime_seconds !== null ? formatDuration(c.uptime_seconds) : p.uptime;
  return (
    <StatTiles label="Service overview" id="service-overview">
      <StatTile label="Uptime" value={uptime} hint={startedHint(p.started)} />
      <StatTile
        label="CPU"
        value={p.cpu}
        tone={tileTone(utilTone(parsePercent(p.cpu)))}
        hint={limitHint(c.allocated.cpus_limit, "cores")}
      />
      <StatTile
        label="Memory"
        value={formatBytes(c.memory.used_bytes)}
        tone={tileTone(utilTone(parseMemoryRatioPercent(p.memory)))}
        hint={memoryHint(c)}
      />
      <StatTile
        label="Network"
        value={`↓ ${formatBytes(c.network.rx_bytes)}`}
        hint={`↑ ${formatBytes(c.network.tx_bytes)} sent`}
      />
      <StatTile label="Processes" value={formatCount(c.pids)} hint="PIDs" />
    </StatTiles>
  );
}

function tileTone(tone: UtilTone): "ok" | "warn" | "bad" | undefined {
  if (tone === "hot") return "bad";
  if (tone === "warn") return "warn";
  return undefined;
}

function startedHint(started: string): string | undefined {
  return started && started !== "-" ? `Started ${started}` : undefined;
}

function limitHint(limit: string, unit: string): string {
  return limit && limit !== "-" ? `Limit ${limit} ${unit}` : "No limit";
}

function memoryHint(c: ServiceDetailPayload["container"]): string {
  const limit = formatBytes(c.memory.limit_bytes);
  if (limit === "-") return "No limit";
  const pct = c.memory.used_percent;
  return pct === null ? `of ${limit}` : `${pct.toFixed(1)}% of ${limit}`;
}
