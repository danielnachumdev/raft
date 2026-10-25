/** Column labels for the Stack status table skeleton (matches StatusTable). */
export const STATUS_TABLE_SKELETON_COLUMNS = [
  "Name",
  "Role",
  "Group",
  "Status",
  "CPU",
  "Memory",
  "Started",
  "Uptime",
  "Actions",
] as const;

export const DEFAULT_STATUS_TABLE_ROWS = 5;
export const DEFAULT_STAT_TILE_COUNT = 4;
export const DEFAULT_ITEM_LIST_ROWS = 4;
export const DEFAULT_CHART_FRAME_HEIGHT = "12rem";

/** Relative bone widths (%) for status table body cells, left→right. */
export const STATUS_TABLE_BONE_WIDTHS = [
  72, 48, 40, 56, 36, 52, 44, 40, 28,
] as const;

export type StatusTableSkeletonPlan = {
  columns: string[];
  rows: number;
  boneWidths: number[];
};

export function statusTableSkeletonPlan(opts?: {
  rows?: number;
}): StatusTableSkeletonPlan {
  return {
    columns: [...STATUS_TABLE_SKELETON_COLUMNS],
    rows: opts?.rows ?? DEFAULT_STATUS_TABLE_ROWS,
    boneWidths: [...STATUS_TABLE_BONE_WIDTHS],
  };
}

export type StatTilesSkeletonPlan = { count: number };

export function statTilesSkeletonPlan(opts?: {
  count?: number;
}): StatTilesSkeletonPlan {
  return { count: opts?.count ?? DEFAULT_STAT_TILE_COUNT };
}

export type ItemListSkeletonPlan = { rows: number };

export function itemListSkeletonPlan(opts?: {
  rows?: number;
}): ItemListSkeletonPlan {
  return { rows: opts?.rows ?? DEFAULT_ITEM_LIST_ROWS };
}

export type ChartFrameSkeletonPlan = { height: string };

export function chartFrameSkeletonPlan(opts?: {
  height?: string;
}): ChartFrameSkeletonPlan {
  return { height: opts?.height ?? DEFAULT_CHART_FRAME_HEIGHT };
}

export type StackStatusSkeletonPlan = {
  tiles: StatTilesSkeletonPlan;
  appsRows: number;
  controlPlaneRows: number;
};

export function stackStatusSkeletonPlan(opts?: {
  tiles?: number;
  appsRows?: number;
  controlPlaneRows?: number;
}): StackStatusSkeletonPlan {
  return {
    tiles: statTilesSkeletonPlan({ count: opts?.tiles }),
    appsRows: opts?.appsRows ?? 4,
    controlPlaneRows: opts?.controlPlaneRows ?? 3,
  };
}

export type AlertsListSkeletonPlan = {
  rows: number;
};

export function alertsListSkeletonPlan(opts?: {
  rows?: number;
}): AlertsListSkeletonPlan {
  return { rows: opts?.rows ?? DEFAULT_ITEM_LIST_ROWS };
}
