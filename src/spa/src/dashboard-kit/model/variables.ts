import type { TrendsGraphDraft } from "../../trends/dashboard/model/types.ts";
import type { DashboardVariables, MetricsPanelQuery } from "./types.ts";

const TOKEN = /\$\{(service|group)\}/g;

/** Replace `${service}` / `${group}` in titles; unbound tokens stay literal. */
export function interpolateTitle(
  title: string,
  variables: DashboardVariables | undefined,
): string {
  if (!title.includes("${")) return title;
  return title.replace(TOKEN, (_, key: keyof DashboardVariables) => {
    const value = variables?.[key];
    return value && value.trim() ? value.trim() : `\${${key}}`;
  });
}

/**
 * Bind embed variables into a panel query. A pinned `service` forces
 * per-service view and an explicit selection list.
 */
export function applyVariablesToQuery(
  query: MetricsPanelQuery,
  variables: DashboardVariables | undefined,
): MetricsPanelQuery {
  const service = variables?.service?.trim();
  if (!service) return query;
  return {
    ...query,
    viewMode: "per_service",
    selected: [service],
  };
}

/** Pin a Trends draft the same way service Trends does today. */
export function pinDraftToVariables(
  draft: TrendsGraphDraft,
  variables: DashboardVariables | undefined,
): TrendsGraphDraft {
  const bound = applyVariablesToQuery(panelQuery(draft), variables);
  return {
    ...draft,
    viewMode: bound.viewMode as TrendsGraphDraft["viewMode"],
    selected: bound.selected,
    title: interpolateTitle(draft.title, variables),
  };
}

function panelQuery(
  draft: Pick<TrendsGraphDraft, "metricIds" | "viewMode" | "selected">,
): MetricsPanelQuery {
  return {
    metricIds: [...draft.metricIds],
    viewMode: draft.viewMode,
    selected: draft.selected === null ? null : [...draft.selected],
  };
}

/** Fetch scope derived from variables (service inspection). */
export function scopeFromVariables(
  variables: DashboardVariables | undefined,
): { services?: string[] } {
  const service = variables?.service?.trim();
  return service ? { services: [service] } : {};
}
