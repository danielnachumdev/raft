/** Eager public surface for the Trends dashboard model (pure, testable). */

export {
  activeDashboard,
  createDashboard,
  deleteDashboard,
  renameDashboard,
  setActiveDashboard,
  suggestDashboardName,
  updateActive,
} from "./dashboards.ts";
export {
  graphSubtitle,
  HEADLINE_LABELS,
  VIEW_MODE_LABELS,
} from "./describe.ts";
export {
  blankDraft,
  DEFAULT_DASHBOARD_NAME,
  defaultDashboard,
  defaultPanels,
  draftFromPreset,
  GRAPH_PRESETS,
  type GraphPreset,
} from "./defaults.ts";
export {
  graphTitle,
  graphView,
  pickerIdsFor,
  planesForGraphs,
  seriesPalette,
  type DashboardData,
  type GraphView,
} from "./fanout.ts";
export { headlineStat, type Headline, type HeadlineHow } from "./headline.ts";
export { migrateLegacyViews } from "./migrate.ts";
export { capMetricTypes, parseDashboardStore, parseGraph } from "./parse.ts";
export {
  addPanel,
  cloneDraft,
  duplicatePanel,
  insertPanel,
  movePanel,
  movePanelTo,
  removePanel,
  resizePanel,
  restoreDefaultPanels,
  setDashboardRange,
  updatePanel,
} from "./panels.ts";
export {
  reconcileSelection,
  staleSelectionMessage,
  type ReconcileResult,
} from "./reconcile.ts";
export {
  defaultDashboardStore,
  loadDashboardStore,
  newId,
  saveDashboardStore,
} from "./storage.ts";
export {
  DEFAULT_DASHBOARD_ID,
  TRENDS_DASHBOARDS_STORAGE_KEY,
  type GraphSize,
  type TrendsDashboard,
  type TrendsDashboardStore,
  type TrendsGraphConfig,
  type TrendsGraphDraft,
} from "./types.ts";
