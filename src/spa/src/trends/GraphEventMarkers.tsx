import type { ReactElement } from "react";
import { ReferenceLine } from "recharts";
import type { GraphEvent } from "../shared/api";
import { toEpochMs } from "./chartTimeScale";
import { eventMarkerLabel, eventMarkerStroke } from "./graphEvents";

/**
 * Build dashed vertical GraphEvent markers for a Recharts chart.
 *
 * Overlay only: ``x`` is epoch ms on the numeric time axis — do not insert
 * null sample rows for these timestamps (that breaks ``connectNulls={false}``).
 *
 * Must be inlined as ``{graphEventMarkers(...)}`` — Recharts only discovers
 * ``ReferenceLine`` among *direct* chart children (wrapper components are skipped).
 */
export function graphEventMarkers(
  events: GraphEvent[],
  yAxisId?: string | number,
): ReactElement[] {
  return events.flatMap((event) => {
    const x = toEpochMs(event.ts);
    if (x === null) return [];
    const stroke = eventMarkerStroke(event.kind);
    const axisProps = yAxisId === undefined ? {} : { yAxisId };
    return [
      <ReferenceLine
        key={eventKey(event)}
        x={x}
        {...axisProps}
        stroke={stroke}
        strokeDasharray="5 3"
        strokeWidth={2}
        ifOverflow="extendDomain"
        isFront
        label={{
          value: eventMarkerLabel(event),
          position: "insideTopLeft",
          fill: stroke,
          fontSize: 11,
          fontWeight: 700,
          offset: 4,
        }}
      />,
    ];
  });
}

function eventKey(event: GraphEvent): string {
  if (event.id) return event.id;
  return `${event.kind}:${event.ts}:${event.service ?? ""}`;
}
