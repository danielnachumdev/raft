import type { MetricsSeries, ServiceDetailPayload } from "./api";
import { ExternalUrlLinks } from "./ExternalUrlLinks";
import { ServiceActions } from "./ServiceActions";
import { ServiceLogs } from "./ServiceLogs";

/** Render full status contract fields for one Compose service. */
export function ServiceDetail(props: {
  data: ServiceDetailPayload;
  metrics: MetricsSeries | null;
  onActionDone: () => void;
}) {
  const { container: c, presentation: p, host } = props.data;
  return (
    <>
      <ServiceActions service={c.service} onDone={props.onActionDone} />
      <ServiceLogs service={c.service} />

      <section className="panel">
        <h2>Overview</h2>
        <dl className="detail-grid">
          <Detail label="Compose service" value={c.service} />
          <Detail label="Display name" value={p.name} />
          <Detail label="Role" value={c.role} />
          <Detail label="Group" value={c.group ?? "-"} />
          <Detail label="App" value={c.app ?? "-"} />
          <Detail label="Status" value={c.status} />
          <dt>External URLs</dt>
          <dd>
            <ExternalUrlLinks urls={p.external_urls ?? []} />
          </dd>
          <Detail label="Started" value={p.started} />
          <Detail label="Uptime" value={p.uptime} />
          <Detail label="CPU (live)" value={p.cpu} />
          <Detail label="Memory (live)" value={p.memory} />
        </dl>
      </section>

      <section className="panel">
        <h2>Allocated limits</h2>
        <dl className="detail-grid">
          <Detail label="CPU limit" value={c.allocated.cpus_limit} />
          <Detail label="Memory limit" value={c.allocated.memory_limit} />
          <Detail label="CPU reservation" value={c.allocated.cpus_reservation} />
          <Detail
            label="Memory reservation"
            value={c.allocated.memory_reservation}
          />
        </dl>
      </section>

      <section className="panel">
        <h2>Runtime</h2>
        <dl className="detail-grid">
          <Detail label="CPU %" value={fmtNum(c.cpu_percent)} />
          <Detail label="Memory used %" value={fmtNum(c.memory.used_percent)} />
          <Detail label="Memory used bytes" value={fmtInt(c.memory.used_bytes)} />
          <Detail
            label="Memory limit bytes"
            value={fmtInt(c.memory.limit_bytes)}
          />
          <Detail label="Uptime seconds" value={fmtNum(c.uptime_seconds)} />
          <Detail label="PIDs" value={fmtInt(c.pids)} />
          <Detail label="Network RX" value={fmtInt(c.network.rx_bytes)} />
          <Detail label="Network TX" value={fmtInt(c.network.tx_bytes)} />
          <Detail label="Block read" value={fmtInt(c.block_io.read_bytes)} />
          <Detail label="Block write" value={fmtInt(c.block_io.write_bytes)} />
        </dl>
      </section>

      <section className="panel">
        <h2>Host context</h2>
        <dl className="detail-grid">
          <Detail label="Hostname" value={String(host.hostname ?? "-")} />
        </dl>
      </section>

      <MetricsSummary series={props.metrics} />
    </>
  );
}

function MetricsSummary(props: { series: MetricsSeries | null }) {
  const series = props.series;
  if (!series || series.points.length === 0) {
    return (
      <section className="panel">
        <h2>Recent metrics</h2>
        <p className="muted">No recent metrics samples for this service.</p>
      </section>
    );
  }
  const last = series.points[series.points.length - 1];
  return (
    <section className="panel">
      <h2>Recent metrics (1h)</h2>
      <dl className="detail-grid">
        <Detail label="Samples" value={String(series.points.length)} />
        <Detail label="Last sample" value={last.t} />
        <Detail label="Last CPU %" value={fmtNum(last.cpu_percent)} />
        <Detail
          label="Last memory %"
          value={fmtNum(last.memory_used_percent)}
        />
      </dl>
    </section>
  );
}

function Detail(props: { label: string; value: string }) {
  return (
    <>
      <dt>{props.label}</dt>
      <dd>
        <code>{props.value}</code>
      </dd>
    </>
  );
}

function fmtNum(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return String(value);
}

function fmtInt(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return String(value);
}
