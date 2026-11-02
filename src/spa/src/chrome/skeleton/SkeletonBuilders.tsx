import type { ReactNode } from "react";
import {
  chartFrameSkeletonPlan,
  chartPlotSkeletonPlan,
  itemListSkeletonPlan,
  statusTableSkeletonPlan,
  statTilesSkeletonPlan,
} from "./buildersConfig";
import { SkeletonBone, SkeletonRoot } from "./Skeleton";

/** At-a-glance health tile placeholders (matches StatTiles). */
export function StatTilesSkeleton(props?: {
  count?: number;
  label?: string;
  id?: string;
}) {
  const { count } = statTilesSkeletonPlan({ count: props?.count });
  return (
    <ul
      className="stat-tiles skeleton-stat-tiles"
      id={props?.id}
      aria-hidden={props?.label ? undefined : true}
      aria-label={props?.label}
    >
      {Array.from({ length: count }, (_, i) => (
        <li className="stat-tile" key={i}>
          <span className="stat-tile-label">
            <SkeletonBone size="sm" width={55 + (i % 3) * 8} />
          </span>
          <span className="stat-tile-value">
            <SkeletonBone size="lg" width={38 + (i % 2) * 10} />
          </span>
          <span className="stat-tile-hint">
            <SkeletonBone size="sm" width={60} />
          </span>
        </li>
      ))}
    </ul>
  );
}

/** Table shape with real column headers + shimmer rows. */
export function StatusTableSkeleton(props?: {
  rows?: number;
  columns?: readonly string[];
  boneWidths?: readonly number[];
}) {
  const plan = statusTableSkeletonPlan({
    rows: props?.rows,
    columns: props?.columns,
    boneWidths: props?.boneWidths,
  });
  return (
    <div className="status-table-wrap">
      <table className="skeleton-status-table">
        <thead>
          <tr>
            {plan.columns.map((label) => (
              <th key={label}>{label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: plan.rows }, (_, row) => (
            <tr key={row}>
              {plan.boneWidths.map((width, col) => (
                <td key={col}>
                  <SkeletonBone
                    size="md"
                    width={Math.max(24, width - (row % 3) * 6)}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Panel chrome with optional title bone + body (table, list, chart…). */
export function SectionPanelSkeleton(props: {
  titleWidth?: string | number;
  id?: string;
  children: ReactNode;
}) {
  return (
    <section className="panel" id={props.id} aria-hidden="true">
      <div className="panel-head">
        <h2>
          <SkeletonBone size="md" width={props.titleWidth ?? "5.5rem"} />
        </h2>
      </div>
      {props.children}
    </section>
  );
}

/** Trends / embed chart frame placeholder (head + plot). */
export function ChartFrameSkeleton(props?: {
  height?: string;
  label?: string;
  id?: string;
}) {
  const { height } = chartFrameSkeletonPlan({ height: props?.height });
  const body = (
    <div className="skeleton-chart-frame" style={{ minHeight: height }}>
      <div className="skeleton-chart-frame-head">
        <SkeletonBone size="md" width="7rem" />
        <SkeletonBone size="sm" width="4.5rem" />
      </div>
      <div className="skeleton-chart-frame-plot" style={{ minHeight: height }}>
        <SkeletonBone size="block" />
      </div>
    </div>
  );
  if (!props?.label) return body;
  return (
    <SkeletonRoot label={props.label} id={props.id}>
      {body}
    </SkeletonRoot>
  );
}

/**
 * Plot-area shimmer for TrendsGraph / ChartLoadingOverlay cold load when the
 * card header is already real (config title), not a full frame.
 */
export function ChartPlotSkeleton(props?: {
  height?: string;
  label?: string;
  id?: string;
}) {
  const { height } = chartPlotSkeletonPlan({ height: props?.height });
  const body = (
    <div className="skeleton-chart-plot" style={{ minHeight: height }}>
      <SkeletonBone size="block" />
    </div>
  );
  if (!props?.label) return body;
  return (
    <SkeletonRoot label={props.label} id={props.id}>
      {body}
    </SkeletonRoot>
  );
}

/** Generic settings/item-list row placeholders. */
export function ItemListSkeleton(props?: { rows?: number }) {
  const { rows } = itemListSkeletonPlan({ rows: props?.rows });
  return (
    <ul className="item-list skeleton-item-list" aria-hidden="true">
      {Array.from({ length: rows }, (_, i) => (
        <li className="item-row" key={i}>
          <div className="skeleton-item-main">
            <div className="skeleton-item-title">
              <SkeletonBone size="md" width={42 + (i % 3) * 8} />
              <SkeletonBone size="sm" width="4rem" />
            </div>
            <div className="skeleton-item-meta">
              <SkeletonBone size="sm" width="18%" />
              <SkeletonBone size="sm" width="22%" />
              <SkeletonBone size="sm" width="28%" />
            </div>
          </div>
          <div className="skeleton-item-actions">
            <SkeletonBone />
            <SkeletonBone />
            <SkeletonBone />
          </div>
        </li>
      ))}
    </ul>
  );
}
