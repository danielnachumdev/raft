/** Read-only #202 named views — input to the dashboard migration. */

export { parseStore } from "./parseStore.ts";
export { loadTrendsViewsStore } from "./storage.ts";
export type {
  NamedTrendsView,
  TrendsViewConfig,
  TrendsViewsStore,
} from "./types.ts";
export {
  EMPTY_VIEWS_STORE,
  TRENDS_VIEWS_STORAGE_KEY,
} from "./types.ts";
