import type { ReactElement } from "react";
import { ReferenceLine } from "recharts";
import type { GraphEvent } from "../../shared/api";
import { ChartHoverHighlight } from "./chartHover";
import { toEpochMs } from "./chartTimeScale";
import { eventMarkerLabel, eventMarkerStroke } from "./graphEvents";

export type GraphEventMarkerOptions = {
  yAxisId?: string | number;
  highlight?: ChartHoverHighlight;
  onHoverKind?: (kind: string) => void;
};

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
  options: GraphEventMarkerOptions = {},
): ReactElement[] {
  const highlight = options.highlight ?? new ChartHoverHighlight(null);
  return events.flatMap((event) => markerFor(event, options, highlight));
}

function markerFor(
  event: GraphEvent,
  options: GraphEventMarkerOptions,
  highlight: ChartHoverHighlight,
): ReactElement[] {
  const x = toEpochMs(event.ts);
  if (x === null) return [];
  const shared = markerShared(event, options, highlight, x);
  return [hitMarker(shared), visibleMarker(event, shared)];
}

type MarkerShared = {
  x: number;
  stroke: string;
  opacity: number;
  axisProps: { yAxisId?: string | number };
  onEnter: () => void;
  highlight: ChartHoverHighlight;
  kind: string;
  key: string;
};

function markerShared(
  event: GraphEvent,
  options: GraphEventMarkerOptions,
  highlight: ChartHoverHighlight,
  x: number,
): MarkerShared {
  const axisProps =
    options.yAxisId === undefined ? {} : { yAxisId: options.yAxisId };
  return {
    x,
    stroke: eventMarkerStroke(event.kind),
    opacity: highlight.eventOpacity(event.kind),
    axisProps,
    onEnter: () => options.onHoverKind?.(event.kind),
    highlight,
    kind: event.kind,
    key: eventKey(event),
  };
}

function hitMarker(shared: MarkerShared): ReactElement {
  const width = Math.max(12, shared.highlight.eventStrokeWidth(shared.kind));
  return (
    <ReferenceLine
      key={`${shared.key}-hit`}
      x={shared.x}
      {...shared.axisProps}
      stroke={shared.stroke}
      strokeWidth={width}
      strokeOpacity={0.001}
      ifOverflow="extendDomain"
      isFront
      onMouseEnter={shared.onEnter}
    />
  );
}

function visibleMarker(event: GraphEvent, shared: MarkerShared): ReactElement {
  return (
    <ReferenceLine
      key={shared.key}
      x={shared.x}
      {...shared.axisProps}
      stroke={shared.stroke}
      strokeDasharray="5 3"
      strokeWidth={shared.highlight.eventStrokeWidth(shared.kind)}
      strokeOpacity={shared.opacity}
      ifOverflow="extendDomain"
      isFront
      onMouseEnter={shared.onEnter}
      label={{
        value: eventMarkerLabel(event),
        position: "insideTopLeft",
        fill: shared.stroke,
        fillOpacity: shared.opacity,
        fontSize: 11,
        fontWeight: 700,
        offset: 4,
      }}
    />
  );
}

function eventKey(event: GraphEvent): string {
  if (event.id) return event.id;
  return `${event.kind}:${event.ts}:${event.service ?? ""}`;
}
