import type { TrendsDashboard } from "../../dashboard/model/types.ts";
import type { ServiceTrendsLayout } from "./types.ts";

/**
 * Adapt a service layout to the shared dashboard reducers (add/remove/move…).
 * ``id`` / ``name`` are the Compose service name.
 */
export function asDashboard(
  service: string,
  layout: ServiceTrendsLayout,
): TrendsDashboard {
  return {
    id: service,
    name: service,
    updatedAt: layout.updatedAt,
    range: layout.range,
    panels: layout.panels,
  };
}

export function fromDashboard(d: TrendsDashboard): ServiceTrendsLayout {
  return {
    updatedAt: d.updatedAt,
    range: d.range,
    panels: d.panels,
  };
}
