import { Link } from "react-router-dom";
import { relativeTime } from "../shared/format";
import type { OpsEventRow } from "./eventsApi";
import { eventTone, formatClock, formatFull, groupEventsByDay } from "./eventsView";

/** Day-grouped event rows: clock + relative time, toned kind chip, service link. */
export function EventsTimeline(props: {
  rows: OpsEventRow[];
  now: number;
  knownServices: Set<string>;
}) {
  const groups = groupEventsByDay(props.rows, props.now);
  return (
    <div className="events-timeline" id="events-timeline">
      {groups.map((group) => (
        <section key={group.key} className="events-day" aria-label={group.label}>
          <h3 className="events-day-label">
            {group.label}
            <span className="panel-count">{group.rows.length}</span>
          </h3>
          <ol className="events-list">
            {group.rows.map((row) => (
              <EventRow
                key={row.id ?? `${row.ts}-${row.kind}`}
                row={row}
                now={props.now}
                linkService={!!row.service && props.knownServices.has(row.service)}
              />
            ))}
          </ol>
        </section>
      ))}
    </div>
  );
}

function EventRow(props: { row: OpsEventRow; now: number; linkService: boolean }) {
  const { row } = props;
  const tone = eventTone(row.kind);
  return (
    <li className={`events-row events-row--${tone}`} data-kind={row.kind}>
      <time className="events-ts" dateTime={row.ts} title={formatFull(row.ts)}>
        <span className="events-clock">{formatClock(row.ts)}</span>
        <span className="events-ago">{relativeTime(row.ts, props.now)}</span>
      </time>
      <span className="events-kind">
        <span className={tone === "neutral" ? "chip" : `chip chip-${tone}`}>{row.kind}</span>
      </span>
      <span className="events-summary">{row.summary}</span>
      <span className="events-service">
        {row.service ? (
          props.linkService ? (
            <Link to={`/service/${encodeURIComponent(row.service)}`}>{row.service}</Link>
          ) : (
            row.service
          )
        ) : (
          <span className="muted">host</span>
        )}
      </span>
    </li>
  );
}
