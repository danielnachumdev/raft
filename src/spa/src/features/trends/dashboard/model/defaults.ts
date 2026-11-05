import { defaultRangeState } from "../../range/index.ts";
import type { RuntimeMetricId } from "../../runtimeMetrics.ts";
import {
  DEFAULT_DASHBOARD_ID,
  type TrendsDashboard,
  type TrendsGraphConfig,
  type TrendsGraphDraft,
} from "./types.ts";

export type GraphPreset = {
  id: string;
  title: string;
  hint: string;
  metricIds: RuntimeMetricId[];
};

/** Quick-start graphs; the first six form the default Overview layout. */
export const GRAPH_PRESETS: GraphPreset[] = [
  preset("cpu", "CPU", "Container CPU %", ["cpu_percent"]),
  preset("memory", "Memory", "Used % of limit", ["memory_used_percent"]),
  preset("requests", "Request rate", "Requests / sec at the gate", ["rps"]),
  preset("latency", "Latency p95", "Slowest 5% of requests", ["duration_p95_ms"]),
  preset("errors", "Errors", "4xx and 5xx responses", ["status_4xx", "status_5xx"]),
  preset("network", "Network", "Bytes received / sent", [
    "network_rx_bytes",
    "network_tx_bytes",
  ]),
  preset("disk", "Disk I/O", "Block read / write", [
    "block_read_bytes",
    "block_write_bytes",
  ]),
  preset("in-flight", "In-flight", "Requests being written", ["in_flight"]),
  preset("latency-spread", "Latency spread", "p50 vs p99", [
    "duration_p50_ms",
    "duration_p99_ms",
  ]),
  preset("pids", "Processes", "PIDs per container", ["pids"]),
];

const DEFAULT_PRESET_COUNT = 6;

export const DEFAULT_DASHBOARD_NAME = "Overview";

export function draftFromPreset(p: GraphPreset): TrendsGraphDraft {
  return {
    title: p.title,
    metricIds: [...p.metricIds],
    viewMode: "per_service",
    selected: null,
    size: "half",
  };
}

/** Fresh copy of the default Overview graphs (stable ids). */
export function defaultPanels(): TrendsGraphConfig[] {
  return GRAPH_PRESETS.slice(0, DEFAULT_PRESET_COUNT).map((p) => ({
    id: p.id,
    ...draftFromPreset(p),
  }));
}

export function defaultDashboard(nowMs: number = Date.now()): TrendsDashboard {
  return {
    id: DEFAULT_DASHBOARD_ID,
    name: DEFAULT_DASHBOARD_NAME,
    updatedAt: new Date(nowMs).toISOString(),
    range: defaultRangeState(),
    panels: defaultPanels(),
  };
}

export function blankDraft(): TrendsGraphDraft {
  return draftFromPreset(GRAPH_PRESETS[0]);
}

function preset(
  id: string,
  title: string,
  hint: string,
  metricIds: RuntimeMetricId[],
): GraphPreset {
  return { id, title, hint, metricIds };
}
