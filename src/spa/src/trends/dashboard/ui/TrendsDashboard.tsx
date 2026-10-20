import { DashboardKit } from "../../../dashboard-kit/index.ts";
import { blankDraft, restoreDefaultPanels } from "../model/index.ts";
import { useDashboardStore } from "./useDashboardStore";

/**
 * Trends overview embed of the reusable dashboard kit (#249).
 * Persistence remains `raft-serve-trends-dashboards` via useDashboardStore.
 */
export function TrendsDashboard() {
  const api = useDashboardStore();
  return (
    <DashboardKit
      embedId="trends"
      mode="edit"
      api={api}
      blankDraft={blankDraft}
      restoreDefaults={restoreDefaultPanels}
      chrome={{
        title: "Trends",
        showDashboardPicker: true,
      }}
    />
  );
}
