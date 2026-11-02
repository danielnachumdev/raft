/**
 * Skeleton loading framework.
 *
 * Prefer premade builders (StackStatusSkeleton, StatusTableSkeleton, …) when
 * the page shape is known. Use LoadingState / button spinners only when there
 * is no meaningful skeleton for that surface (unknown layout, one-shot
 * actions). Quiet refresh: if data is already on screen, keep last UI — see
 * showSkeleton / surfaceLoadState (same idea as Dashboard peekStatus quiet poll).
 */
export {
  alertsListSkeletonPlan,
  chartFrameSkeletonPlan,
  chartPlotSkeletonPlan,
  DEFAULT_CHART_FRAME_HEIGHT,
  DEFAULT_ITEM_LIST_ROWS,
  DEFAULT_STAT_TILE_COUNT,
  DEFAULT_STATUS_TABLE_ROWS,
  FIREWALL_TABLE_BONE_WIDTHS,
  FIREWALL_TABLE_SKELETON_COLUMNS,
  HTTP_REQUESTS_TABLE_BONE_WIDTHS,
  HTTP_REQUESTS_TABLE_SKELETON_COLUMNS,
  itemListSkeletonPlan,
  stackStatusSkeletonPlan,
  STATUS_TABLE_BONE_WIDTHS,
  STATUS_TABLE_SKELETON_COLUMNS,
  statusTableSkeletonPlan,
  statTilesSkeletonPlan,
} from "./buildersConfig";
export {
  ChartFrameSkeleton,
  ChartPlotSkeleton,
  ItemListSkeleton,
  SectionPanelSkeleton,
  StatTilesSkeleton,
  StatusTableSkeleton,
} from "./SkeletonBuilders";
export {
  AlertsListSkeleton,
  ItemPanelSkeleton,
  ServicePageSkeleton,
  SettingsFormSkeleton,
  StackStatusSkeleton,
} from "./SkeletonPremades";
export { SkeletonBone, SkeletonRoot } from "./Skeleton";
export {
  showSkeleton,
  surfaceLoadState,
  type SurfaceLoadState,
} from "./surfaceLoadState";
