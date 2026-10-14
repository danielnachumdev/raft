import type { ServiceDetailPayload } from "../shared/api";
import { formatBytes, formatPercent } from "../shared/format";
import "./ServiceDetail.css";

type Row = { label: string; value: string };

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
        { label: "CPU", value: formatPercent(c.cpu_percent) },
        { label: "Memory used", value: formatBytes(c.memory.used_bytes) },
        { label: "Memory limit", value: formatBytes(c.memory.limit_bytes) },
        { label: "Block read", value: formatBytes(c.block_io.read_bytes) },
        { label: "Block write", value: formatBytes(c.block_io.write_bytes) },
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
