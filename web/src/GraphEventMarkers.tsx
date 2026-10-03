import { ReferenceLine } from "recharts";
import type { GraphEvent } from "./api";
import { eventMarkerLabel } from "./graphEvents";

/** Dashed vertical markers for GraphEvents (deployments today). */
export function GraphEventMarkers(props: { events: GraphEvent[] }) {
  if (!props.events.length) return null;
  return (
    <>
      {props.events.map((event) => (
        <ReferenceLine
          key={eventKey(event)}
          x={event.ts}
          stroke="var(--muted)"
          strokeDasharray="4 4"
          strokeWidth={1}
          ifOverflow="extendDomain"
          label={{
            value: eventMarkerLabel(event),
            position: "insideTopRight",
            fill: "var(--muted)",
            fontSize: 10,
          }}
        />
      ))}
    </>
  );
}

function eventKey(event: GraphEvent): string {
  if (event.id) return event.id;
  return `${event.kind}:${event.ts}:${event.service ?? ""}`;
}
