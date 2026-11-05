import { defaultRangeState } from "../../range/index.ts";
import {
  draftFromPreset,
  GRAPH_PRESETS,
  type TrendsGraphConfig,
} from "../../dashboard/model/index.ts";
import type { ServiceTrendsLayout } from "./types.ts";

const DEFAULT_PRESET_COUNT = 6;

/** Same six Overview graphs, pinned to one service. */
export function defaultServicePanels(service: string): TrendsGraphConfig[] {
  return GRAPH_PRESETS.slice(0, DEFAULT_PRESET_COUNT).map((p) => ({
    id: p.id,
    ...draftFromPreset(p),
    selected: [service],
  }));
}

/** Fresh layout every service gets until the operator customizes it. */
export function defaultServiceLayout(
  service: string,
  nowMs: number = Date.now(),
): ServiceTrendsLayout {
  return {
    updatedAt: new Date(nowMs).toISOString(),
    range: defaultRangeState(),
    panels: defaultServicePanels(service),
  };
}

/** Blank add-graph draft already scoped to the open service. */
export function blankServiceDraft(service: string) {
  return {
    ...draftFromPreset(GRAPH_PRESETS[0]),
    selected: [service] as string[],
  };
}
