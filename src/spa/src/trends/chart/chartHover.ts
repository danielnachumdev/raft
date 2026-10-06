/** Hover grouping for Trends / Runtime charts (gapped lines + GraphEvents). */

export type HoverTone = "rest" | "active" | "dim";

export type HoverGroup =
  | { layer: "series"; id: string }
  | { layer: "event"; kind: string };

const REST_WIDTH = 2;
const ACTIVE_WIDTH = 3.5;
const REST_LINE_OPACITY = 1;
const REST_EVENT_OPACITY = 0.95;
const ACTIVE_OPACITY = 1;
const DIM_OPACITY = 0.22;

/**
 * Map a hovered series id or event kind onto every mark of the same group.
 * One Line is many SVG segments when ``connectNulls={false}``; one kind is
 * many GraphEvent markers — hover any member, emphasize the whole group.
 */
export class ChartHoverHighlight {
  private readonly hover: HoverGroup | null;

  constructor(hover: HoverGroup | null) {
    this.hover = hover;
  }

  seriesTone(id: string): HoverTone {
    return this.tone("series", id);
  }

  eventTone(kind: string): HoverTone {
    return this.tone("event", kind);
  }

  lineStrokeWidth(id: string): number {
    return this.seriesTone(id) === "active" ? ACTIVE_WIDTH : REST_WIDTH;
  }

  lineOpacity(id: string): number {
    return opacityFor(this.seriesTone(id), REST_LINE_OPACITY);
  }

  eventStrokeWidth(kind: string): number {
    return this.eventTone(kind) === "active" ? ACTIVE_WIDTH : REST_WIDTH;
  }

  eventOpacity(kind: string): number {
    return opacityFor(this.eventTone(kind), REST_EVENT_OPACITY);
  }

  emphasizedSeriesIds(ids: readonly string[]): string[] {
    return ids.filter((id) => this.seriesTone(id) === "active");
  }

  emphasizedEventKinds(kinds: readonly string[]): string[] {
    return [...new Set(kinds)].filter((k) => this.eventTone(k) === "active");
  }

  private tone(layer: HoverGroup["layer"], id: string): HoverTone {
    if (this.hover === null) return "rest";
    if (this.hover.layer !== layer) return "dim";
    const hovered =
      this.hover.layer === "series" ? this.hover.id : this.hover.kind;
    return hovered === id ? "active" : "dim";
  }
}

export function seriesHover(id: string): HoverGroup {
  return { layer: "series", id };
}

export function eventKindHover(kind: string): HoverGroup {
  return { layer: "event", kind };
}

function opacityFor(tone: HoverTone, rest: number): number {
  if (tone === "active") return ACTIVE_OPACITY;
  if (tone === "dim") return DIM_OPACITY;
  return rest;
}
