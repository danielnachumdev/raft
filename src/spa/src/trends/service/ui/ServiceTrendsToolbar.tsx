import { useState } from "react";
import { ConfirmPopup } from "../../../chrome/ConfirmPopup";
import type { MetricsBounds } from "../../../shared/api";
import { TrendsRangeControls } from "../../TrendsRangeControls";
import type { TrendsRangeState } from "../../range/index.ts";
import { defaultServicePanels } from "../model/index.ts";
import { MenuButton } from "../../dashboard/ui/MenuButton";
import type { ServiceTrendsStoreApi } from "./useServiceTrendsStore";

/** Shared range, restore defaults, and Add graph for one service. */
export function ServiceTrendsToolbar(props: {
  service: string;
  api: ServiceTrendsStoreApi;
  bounds: MetricsBounds | null;
  clampMessage: string | null;
  onRange: (next: TrendsRangeState) => void;
  onAdd: () => void;
}) {
  const [restoreOpen, setRestoreOpen] = useState(false);
  const count = props.api.dashboard.panels.length;
  return (
    <div className="trends-toolbar" role="toolbar" aria-label="Service trends controls">
      <div className="trends-toolbar-range">
        <TrendsRangeControls
          range={props.api.dashboard.range}
          bounds={props.bounds}
          clampMessage={props.clampMessage}
          busy={false}
          onChange={props.onRange}
        />
      </div>
      <MenuButton
        label="Trends options"
        items={[
          {
            id: "restore",
            label: "Restore default graphs…",
            onSelect: () => setRestoreOpen(true),
          },
        ]}
      />
      <button
        type="button"
        className="action-btn btn-primary trends-add-graph"
        onClick={props.onAdd}
      >
        + Add graph
      </button>
      <ConfirmPopup
        open={restoreOpen}
        title="Restore default graphs"
        message={restoreMessage(props.service, count)}
        confirmLabel="Restore defaults"
        onCancel={() => setRestoreOpen(false)}
        onConfirm={() => {
          props.api.dismissUndo();
          props.api.edit((d) => ({
            ...d,
            panels: defaultServicePanels(props.service),
            updatedAt: new Date().toISOString(),
          }));
          setRestoreOpen(false);
        }}
      />
    </div>
  );
}

function restoreMessage(service: string, count: number): string {
  const defaults =
    "the default CPU, memory, request rate, latency, errors and network graphs";
  if (count === 0) return `Add ${defaults} for “${service}”?`;
  const graphs = count === 1 ? "1 graph" : `${count} graphs`;
  return `Replace the ${graphs} for “${service}” with ${defaults}?`;
}
