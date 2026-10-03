import { ReferenceLine } from "recharts";
import type { GraphEvent } from "./api";
import { toEpochMs } from "./chartTimeScale";
import { eventMarkerLabel, eventMarkerStroke } from "./graphEvents";

/** Dashed vertical markers for GraphEvents (deploy / stop / scale / …). */
export function GraphEventMarkers(props: {
  events: GraphEvent[];
  /** Must match a chart YAxis id when axes are named (Trends uses ``service``). */
  yAxisId?: string | number;
}) {
  if (!props.events.length) return null;
  return (
    <>
      {props.events.map((event) => {
        const x = toEpochMs(event.ts);
        if (x === null) return null;
        const stroke = eventMarkerStroke(event.kind);
        return (
          <ReferenceLine
            key={eventKey(event)}
            x={x}
            yAxisId={props.yAxisId}
            stroke={stroke}
            strokeDasharray="4 4"
            strokeWidth={1.5}
            ifOverflow="hidden"
            label={{
              value: eventMarkerLabel(event),
              position: "insideTopLeft",
              fill: stroke,
              fontSize: 10,
              fontWeight: 600,
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
