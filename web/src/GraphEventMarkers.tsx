import { ReferenceLine } from "recharts";
import type { GraphEvent } from "./api";
import { toEpochMs } from "./chartTimeScale";
import { eventMarkerLabel, eventMarkerStroke } from "./graphEvents";

/** Dashed vertical markers for GraphEvents (deploy / stop / scaling). */
export function GraphEventMarkers(props: { events: GraphEvent[] }) {
  if (!props.events.length) return null;
  return (
    <>
      {props.events.map((event) => {
        const x = toEpochMs(event.ts);
        if (x === null) return null;
        return (
          <ReferenceLine
            key={eventKey(event)}
            x={x}
            stroke={eventMarkerStroke(event.kind)}
            strokeDasharray="4 4"
            strokeWidth={1}
            ifOverflow="extendDomain"
            label={{
              value: eventMarkerLabel(event),
              position: "insideTopRight",
              fill: eventMarkerStroke(event.kind),
              fontSize: 10,
            }}
          />
        );
      })}
    </>
  );
}

function eventKey(event: GraphEvent): string {
  if (event.id) return event.id;
  return `${event.kind}:${event.ts}:${event.service ?? ""}`;
}
