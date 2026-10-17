/** Eager public surface for per-service Trends layouts (pure, testable). */

export { asDashboard, fromDashboard } from "./asDashboard.ts";
export {
  blankServiceDraft,
  defaultServiceLayout,
  defaultServicePanels,
} from "./defaults.ts";
export { parseServiceLayout, parseServiceTrendsStore } from "./parse.ts";
export { pinDraftToService, pinLayoutToService } from "./pin.ts";
export {
  emptyServiceTrendsStore,
  layoutForService,
  loadServiceTrendsStore,
  putServiceLayout,
  saveServiceTrendsStore,
} from "./storage.ts";
export {
  SERVICE_TRENDS_STORAGE_KEY,
  type ServiceTrendsLayout,
  type ServiceTrendsStore,
} from "./types.ts";
