import type {
  TrendsGraphConfig,
  TrendsGraphDraft,
} from "../../dashboard/model/types.ts";
import type { ServiceTrendsLayout } from "./types.ts";

/** Force a draft onto the open service (per-service page has no picker). */
export function pinDraftToService(
  draft: TrendsGraphDraft,
  service: string,
): TrendsGraphDraft {
  return {
    ...draft,
    viewMode: "per_service",
    selected: [service],
  };
}

/** Re-pin every graph so a renamed/imported layout stays on this service. */
export function pinLayoutToService(
  layout: ServiceTrendsLayout,
  service: string,
): ServiceTrendsLayout {
  return {
    ...layout,
    panels: layout.panels.map((p) => pinPanel(p, service)),
  };
}

function pinPanel(panel: TrendsGraphConfig, service: string): TrendsGraphConfig {
  return { ...pinDraftToService(panel, service), id: panel.id };
}
