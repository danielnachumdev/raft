import { FlashValue } from "../chrome/FlashValue";
import { directionalFlash, solidFlash } from "../chrome/flashValue";
import { StatTile, StatTiles } from "../chrome/StatTile";
import type { ServiceDetailPayload } from "../shared/api";
import { formatBytes, formatCount, formatDuration } from "../shared/format";
import {
  parseMemoryRatioPercent,
  parsePercent,
  utilTone,
  type UtilTone,
} from "../status/model/statusTone";

const PCT_FLASH = directionalFlash({ buckets: [0.5, 2, 8] });
const BYTES_FLASH = directionalFlash({
  buckets: [64 * 1024, 1024 * 1024, 16 * 1024 * 1024],
});
const COUNT_FLASH = solidFlash({ intensity: 0.45 });

/** Live headline numbers for one service (uptime, CPU, memory, I/O). */
export function ServiceOverview(props: { data: ServiceDetailPayload }) {
  const { container: c, presentation: p } = props.data;
  const uptime = c.uptime_seconds !== null ? formatDuration(c.uptime_seconds) : p.uptime;
  const memLabel = formatBytes(c.memory.used_bytes);
  const rxLabel = `↓ ${formatBytes(c.network.rx_bytes)}`;
  const pidLabel = formatCount(c.pids);
  return (
    <StatTiles label="Service overview" id="service-overview">
      <StatTile label="Uptime" value={uptime} hint={startedHint(p.started)} />
      <StatTile
        label="CPU"
        value={
          <FlashValue
            value={c.cpu_percent ?? p.cpu}
            mode={PCT_FLASH}
            className="flash-value--fill"
          >
            {p.cpu}
          </FlashValue>
        }
        tone={tileTone(utilTone(parsePercent(p.cpu)))}
        hint={limitHint(c.allocated.cpus_limit, "cores")}
      />
      <StatTile
        label="Memory"
        value={
          <FlashValue
            value={c.memory.used_bytes}
            mode={BYTES_FLASH}
            className="flash-value--fill"
          >
            {memLabel}
          </FlashValue>
        }
        tone={tileTone(utilTone(parseMemoryRatioPercent(p.memory)))}
        hint={memoryHint(c)}
      />
      <StatTile
        label="Network"
        value={
          <FlashValue
            value={c.network.rx_bytes}
            mode={BYTES_FLASH}
            className="flash-value--fill"
          >
            {rxLabel}
          </FlashValue>
        }
        hint={`↑ ${formatBytes(c.network.tx_bytes)} sent`}
      />
      <StatTile
        label="Processes"
        value={
          <FlashValue value={c.pids} mode={COUNT_FLASH} className="flash-value--fill">
            {pidLabel}
          </FlashValue>
        }
        hint="PIDs"
      />
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
