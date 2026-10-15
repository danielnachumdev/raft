import type { ReactNode } from "react";
import { FlashValue } from "../chrome/FlashValue";
import { directionalFlash } from "../chrome/flashValue";
import type { ServiceDetailPayload } from "../shared/api";
import { formatBytes, formatPercent } from "../shared/format";
import "./ServiceDetail.css";

type Row = { label: string; value: ReactNode };

const PCT_FLASH = directionalFlash({ buckets: [0.5, 2, 8] });
const BYTES_FLASH = directionalFlash({
  buckets: [64 * 1024, 1024 * 1024, 16 * 1024 * 1024],
});

/** Identity, allocation, and raw counters grouped in one panel. */
export function ServiceDetailsPanel(props: { data: ServiceDetailPayload }) {
  const { container: c, presentation: p, host } = props.data;
  const groups: { title: string; rows: Row[] }[] = [
    {
      title: "Identity",
      rows: [
        { label: "Compose service", value: c.service },
        { label: "Display name", value: p.name },
        { label: "Role", value: c.role },
        { label: "Group", value: c.group ?? "-" },
        { label: "App", value: c.app ?? "-" },
        { label: "Host", value: String(host.hostname ?? "-") },
      ],
    },
    {
      title: "Allocated",
      rows: [
        { label: "CPU limit", value: c.allocated.cpus_limit },
        { label: "CPU reservation", value: c.allocated.cpus_reservation },
        { label: "Memory limit", value: c.allocated.memory_limit },
        { label: "Memory reservation", value: c.allocated.memory_reservation },
      ],
    },
    {
      title: "Counters",
      rows: [
        {
          label: "CPU",
          value: (
            <FlashValue value={c.cpu_percent} mode={PCT_FLASH}>
              {formatPercent(c.cpu_percent)}
            </FlashValue>
          ),
        },
        {
          label: "Memory used",
          value: (
            <FlashValue value={c.memory.used_bytes} mode={BYTES_FLASH}>
              {formatBytes(c.memory.used_bytes)}
            </FlashValue>
          ),
        },
        { label: "Memory limit", value: formatBytes(c.memory.limit_bytes) },
        {
          label: "Block read",
          value: (
            <FlashValue value={c.block_io.read_bytes} mode={BYTES_FLASH}>
              {formatBytes(c.block_io.read_bytes)}
            </FlashValue>
          ),
        },
        {
          label: "Block write",
          value: (
            <FlashValue value={c.block_io.write_bytes} mode={BYTES_FLASH}>
              {formatBytes(c.block_io.write_bytes)}
            </FlashValue>
          ),
        },
        { label: "Started", value: p.started },
      ],
    },
  ];
  return (
    <section className="panel" aria-labelledby="service-details-title">
      <h2 id="service-details-title">Details</h2>
      <div className="detail-groups">
        {groups.map((group) => (
          <div key={group.title} className="detail-group">
            <h3>{group.title}</h3>
            <dl className="detail-grid">
              {group.rows.map((row) => (
                <Detail key={row.label} {...row} />
              ))}
            </dl>
          </div>
        ))}
      </div>
    </section>
  );
}

function Detail(props: Row) {
  return (
    <>
      <dt>{props.label}</dt>
      <dd>
        <code>{props.value}</code>
      </dd>
    </>
  );
}
