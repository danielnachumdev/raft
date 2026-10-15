import type { MetricsBounds } from "../../../shared/api";
import { TrendsRangeControls } from "../../TrendsRangeControls";
import type { TrendsRangeState } from "../../range/index.ts";
import { DashboardPicker } from "./DashboardPicker";
import type { DashboardStoreApi } from "./useDashboardStore";

/** Dashboard switcher, shared range for every graph, and Add graph. */
export function DashboardToolbar(props: {
  api: DashboardStoreApi;
  bounds: MetricsBounds | null;
  clampMessage: string | null;
  onRange: (next: TrendsRangeState) => void;
  onAdd: () => void;
}) {
  return (
    <div className="trends-toolbar" role="toolbar" aria-label="Dashboard controls">
      <DashboardPicker api={props.api} />
      <div className="trends-toolbar-range">
        <TrendsRangeControls
          range={props.api.dashboard.range}
          bounds={props.bounds}
          clampMessage={props.clampMessage}
          busy={false}
          onChange={props.onRange}
        />
      </div>
      <button
        type="button"
        className="action-btn btn-primary trends-add-graph"
        onClick={props.onAdd}
        id="trends-add-graph"
      >
        + Add graph
      </button>
    </div>
  );
}
