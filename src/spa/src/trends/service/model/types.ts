import type { TrendsRangeState } from "../../range/types.ts";
import type { TrendsGraphConfig } from "../../dashboard/model/types.ts";

/** One service's Trends layout (range + graphs). */
export type ServiceTrendsLayout = {
  updatedAt: string;
  range: TrendsRangeState;
  panels: TrendsGraphConfig[];
};

/** Browser-local map of service name → layout. */
export type ServiceTrendsStore = {
  version: 1;
  services: Record<string, ServiceTrendsLayout>;
};

export const SERVICE_TRENDS_STORAGE_KEY = "raft-serve-service-trends";
