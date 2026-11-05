/** Eager public surface for the reusable dashboard kit model. */

export {
  createLocalStorageAdapter,
  type PersistenceAdapter,
} from "./persistence.ts";
export {
  clampSpan,
  GRID_COLUMNS,
  gridCellClass,
  sizeToSpan,
  SPAN_FULL,
  SPAN_HALF,
  spanToSize,
} from "./layout.ts";
export {
  defaultPanelKind,
  graphFromPanelQuery,
  isRenderableKind,
  panelQueryFromGraph,
  planesForQueries,
  resolvePanelView,
} from "./query.ts";
export {
  applyVariablesToQuery,
  interpolateTitle,
  pinDraftToVariables,
  scopeFromVariables,
} from "./variables.ts";
export type {
  DashboardKitChrome,
  DashboardKitContract,
  DashboardVariables,
  EmbedMode,
  MetricsPanelQuery,
  PanelKind,
  PanelSpan,
} from "./types.ts";
