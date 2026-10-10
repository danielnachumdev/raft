import type { RuntimeMetricDef } from "../runtimeMetrics.ts";

/** Container / host resource series for Trends + Runtime charts. */
export const RESOURCE_METRICS: RuntimeMetricDef[] = [
  { id: "cpu_percent", label: "CPU %", typeId: "percent", plane: "resources" },
  {
    id: "memory_used_percent",
    label: "Memory used %",
    typeId: "percent",
    plane: "resources",
  },
  {
    id: "memory_used_bytes",
    label: "Memory used bytes",
    typeId: "bytes",
    plane: "resources",
  },
  {
    id: "memory_limit_bytes",
    label: "Memory limit bytes",
    typeId: "bytes",
    plane: "resources",
  },
  {
    id: "uptime_seconds",
    label: "Uptime seconds",
    typeId: "uptime",
    plane: "resources",
  },
  { id: "pids", label: "PIDs", typeId: "count", plane: "resources" },
  {
    id: "network_rx_bytes",
    label: "Network RX",
    typeId: "bytes",
    plane: "resources",
  },
  {
    id: "network_tx_bytes",
    label: "Network TX",
    typeId: "bytes",
    plane: "resources",
  },
  {
    id: "block_read_bytes",
    label: "Block read",
    typeId: "bytes",
    plane: "resources",
  },
  {
    id: "block_write_bytes",
    label: "Block write",
    typeId: "bytes",
    plane: "resources",
  },
];
