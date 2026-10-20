import { LiveIndicator } from "../../chrome/LiveIndicator";
import type { DashboardMetrics } from "../../trends/dashboard/ui/useDashboardMetrics";

/** Live / fixed / loading strip next to the dashboard title. */
export function DashboardStatus(props: { data: DashboardMetrics }) {
  const { data } = props;
  if (data.busy && data.series.length === 0) {
    return (
      <p className="muted panel-kind" aria-live="polite">
        Loading…
      </p>
    );
  }
  if (!data.live) {
    return <p className="muted panel-kind">Fixed range · recorded metrics</p>;
  }
  return <LiveIndicator isLive label={data.busy ? "Updating…" : "Live"} />;
}
