import {
  alertsListSkeletonPlan,
  stackStatusSkeletonPlan,
} from "./buildersConfig";
import {
  ChartFrameSkeleton,
  ItemListSkeleton,
  SectionPanelSkeleton,
  StatTilesSkeleton,
  StatusTableSkeleton,
} from "./SkeletonBuilders";
import { SkeletonBone, SkeletonRoot } from "./Skeleton";

/**
 * Premade Stack status cold-load layout: health tiles + Apps / Control plane
 * table panels. Prefer this over hand-assembled bones on the home path.
 */
export function StackStatusSkeleton(props?: {
  label?: string;
  id?: string;
  tiles?: number;
  appsRows?: number;
  controlPlaneRows?: number;
}) {
  const plan = stackStatusSkeletonPlan({
    tiles: props?.tiles,
    appsRows: props?.appsRows,
    controlPlaneRows: props?.controlPlaneRows,
  });
  return (
    <SkeletonRoot
      label={props?.label ?? "Loading status…"}
      id={props?.id ?? "status-loading"}
      className="skeleton-stack-status"
    >
      <StatTilesSkeleton count={plan.tiles.count} id="status-summary-skeleton" />
      <SectionPanelSkeleton titleWidth="3.5rem" id="status-apps-skeleton">
        <StatusTableSkeleton rows={plan.appsRows} />
      </SectionPanelSkeleton>
      <SectionPanelSkeleton
        titleWidth="7.5rem"
        id="status-control-plane-skeleton"
      >
        <StatusTableSkeleton rows={plan.controlPlaneRows} />
      </SectionPanelSkeleton>
    </SkeletonRoot>
  );
}

/** Premade panel + item-list cold load (alerts, notifications, inbox, …). */
export function ItemPanelSkeleton(props?: {
  label?: string;
  id?: string;
  rows?: number;
  titleWidth?: string | number;
  panelId?: string;
}) {
  const plan = alertsListSkeletonPlan({ rows: props?.rows });
  return (
    <SkeletonRoot
      label={props?.label ?? "Loading…"}
      id={props?.id}
      className="skeleton-item-panel"
    >
      <SectionPanelSkeleton
        titleWidth={props?.titleWidth ?? "4.5rem"}
        id={props?.panelId}
      >
        <ItemListSkeleton rows={plan.rows} />
      </SectionPanelSkeleton>
    </SkeletonRoot>
  );
}

/** Premade Alerts rules list cold-load panel. */
export function AlertsListSkeleton(props?: {
  label?: string;
  id?: string;
  rows?: number;
}) {
  return (
    <ItemPanelSkeleton
      label={props?.label ?? "Loading alerts…"}
      id={props?.id ?? "alerts-loading"}
      rows={props?.rows}
      titleWidth="3.25rem"
      panelId="alerts-rules-skeleton"
    />
  );
}

/** Settings form cold load: stacked section panels. */
export function SettingsFormSkeleton(props?: { label?: string; id?: string }) {
  return (
    <SkeletonRoot
      label={props?.label ?? "Loading settings…"}
      id={props?.id ?? "settings-loading"}
      className="skeleton-settings-form"
    >
      {[0, 1, 2].map((i) => (
        <SectionPanelSkeleton
          key={i}
          titleWidth={`${4.5 + (i % 3)}rem`}
          id={`settings-section-skeleton-${i}`}
        >
          <div className="skeleton-block-panel">
            <SkeletonBone size="block" />
          </div>
        </SectionPanelSkeleton>
      ))}
    </SkeletonRoot>
  );
}

/** Service inspection cold load: overview panel + trends chart frame. */
export function ServicePageSkeleton(props?: { label?: string; id?: string }) {
  return (
    <SkeletonRoot
      label={props?.label ?? "Loading service…"}
      id={props?.id ?? "service-loading"}
      className="skeleton-service-page"
    >
      <SectionPanelSkeleton titleWidth="4rem" id="service-overview-skeleton">
        <div className="skeleton-block-panel">
          <SkeletonBone size="block" />
        </div>
      </SectionPanelSkeleton>
      <ChartFrameSkeleton height="14rem" id="service-trends-skeleton" />
    </SkeletonRoot>
  );
}
