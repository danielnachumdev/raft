/** Eager public surface for named Trends views. */

export {
  createNamedView,
  deleteView,
  loadTrendsViewsStore,
  renameView,
  saveTrendsViewsStore,
  setActiveViewId,
  updateActiveConfig,
  upsertView,
} from "./storage.ts";
export {
  reconcileViewConfig,
  staleSelectionMessage,
  type ReconcileResult,
} from "./reconcile.ts";
export { TrendsViewsBar } from "./TrendsViewsBar.tsx";
export {
  useTrendsNamedViews,
  type TrendsNamedViewsApi,
} from "./useTrendsNamedViews.ts";
export type {
  NamedTrendsView,
  TrendsViewConfig,
  TrendsViewsStore,
} from "./types.ts";
export {
  EMPTY_VIEWS_STORE,
  TRENDS_VIEWS_STORAGE_KEY,
} from "./types.ts";
