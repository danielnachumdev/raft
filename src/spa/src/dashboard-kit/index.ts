/** Reusable dashboard kit for Trends and embeddable ops surfaces (#249). */

export {
  applyVariablesToQuery,
  clampSpan,
  createLocalStorageAdapter,
  defaultPanelKind,
  graphFromPanelQuery,
  GRID_COLUMNS,
  gridCellClass,
  interpolateTitle,
  isRenderableKind,
  panelQueryFromGraph,
  pinDraftToVariables,
  planesForQueries,
  resolvePanelView,
  scopeFromVariables,
  sizeToSpan,
  SPAN_FULL,
  SPAN_HALF,
  spanToSize,
  type DashboardKitChrome,
  type DashboardKitContract,
  type DashboardVariables,
  type EmbedMode,
  type MetricsPanelQuery,
  type PanelKind,
  type PanelSpan,
  type PersistenceAdapter,
} from "./model/index.ts";
export {
  DashboardKit,
  type DashboardKitProps,
} from "./ui/DashboardKit.tsx";
export { DashboardStatus } from "./ui/DashboardStatus.tsx";
