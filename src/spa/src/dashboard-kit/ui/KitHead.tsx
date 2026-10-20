import { DownloadMenu } from "../../export/DownloadMenu";
import { metricsDownloadUrl } from "../../export/urls";
import type { DashboardMetrics } from "../../trends/dashboard/ui/useDashboardMetrics";
import { DashboardStatus } from "./DashboardStatus";

/** Title, live status, and metrics download for a kit embed. */
export function KitHead(props: {
  title: string;
  subtitle: string;
  data: DashboardMetrics;
  downloadServices?: string[];
}) {
  const { data } = props;
  return (
    <div className="panel-head">
      <div className="trends-title">
        <h2>
          {props.title}
          <span className="panel-count">{props.subtitle}</span>
        </h2>
        <DashboardStatus data={data} />
      </div>
      <DownloadMenu
        kind="metrics"
        hrefFor={(formatId) =>
          metricsDownloadUrl({
            formatId,
            window: data.windowSec,
            services: props.downloadServices,
          })
        }
        disabled={data.busy && data.series.length === 0}
      />
    </div>
  );
}
