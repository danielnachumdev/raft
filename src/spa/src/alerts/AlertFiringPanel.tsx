import { relativeTime } from "../shared/format";
import type { AlertStatusPayload } from "./alertsApi";

/** "Currently firing" panel: last evaluation line + firing / pending instances. */
export function AlertFiringPanel(props: {
  status: AlertStatusPayload | null;
  interval: number;
  now: number;
}) {
  const instances = props.status?.instances ?? [];
  const firing = instances.filter((i) => i.state === "firing").length;
  const last = props.status?.lastEvaluation;
  return (
    <section className="panel" id="alerts-status">
      <div className="panel-head">
        <h2>
          Currently firing<span className="panel-count">{firing}</span>
        </h2>
        <span className="muted alerts-last-eval">
          {last?.finishedAt
            ? `Last evaluated ${relativeTime(String(last.finishedAt), props.now)}${
                typeof last.durationMs === "number" ? ` · ${last.durationMs} ms` : ""
              }`
            : `Waiting for the first evaluation (every ${props.interval}s)`}
        </span>
      </div>
      {instances.length === 0 ? (
        <div className="empty-state alerts-all-clear" id="alerts-none-firing">
          <p>
            <span className="chip chip-ok">all clear</span> Nothing is firing.
          </p>
        </div>
      ) : (
        <ul className="alert-instance-list">
          {instances.map((inst) => (
            <li key={inst.fingerprint} className="alert-instance">
              <span className={inst.state === "firing" ? "chip chip-bad" : "chip chip-warn"}>
                {inst.suppressed ? "suppressed" : inst.state}
              </span>
              <strong>{inst.ruleName}</strong>
              <code>{inst.subject}</code>
              {inst.since ? <span className="muted">since {relativeTime(inst.since, props.now)}</span> : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
