/** Panel kinds the kit knows how to host. v1 renders timeseries only. */
export type PanelKind = "timeseries" | "stat";

/** Conceptual 12-column span; Trends half/full map to 6/12. */
export type PanelSpan = number;

export type DashboardVariables = {
  service?: string;
  group?: string;
};

export type EmbedMode = "edit" | "view";

/** First-class metrics query carried by a timeseries panel. */
export type MetricsPanelQuery = {
  metricIds: string[];
  viewMode: string;
  /** null = all; [] = none; string[] = explicit service or group ids. */
  selected: string[] | null;
};

export type DashboardKitChrome = {
  /** Visible H2 text (default "Trends"). */
  title?: string;
  /** Muted count / name next to the title. */
  subtitle?: string;
  /** Overview switcher; off for single-layout embeds (service page). */
  showDashboardPicker?: boolean;
  /** Extra class on the outer `<section>`. */
  sectionClassName?: string;
  /** Scopes the metrics download URL. */
  downloadServices?: string[];
};

/**
 * Embed contract for Status overview, service inspection, and future pages.
 * See issue #249 Phase 1 lock.
 */
export type DashboardKitContract = {
  embedId: string;
  mode?: EmbedMode;
  variables?: DashboardVariables;
  /** Scopes metrics fetch; usually derived from `variables.service`. */
  scope?: { services?: string[] };
  chrome?: DashboardKitChrome;
};
