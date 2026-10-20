import { gridCellClass } from "../../../dashboard-kit/model/layout.ts";
import { exportGraphCsv } from "../../export/index.ts";
import type { TrendsGraphConfig } from "../model/index.ts";
import { GraphExportMenu } from "./GraphExportMenu";
import { MenuButton, type MenuItem } from "./MenuButton";
import { TrendsGraph } from "./TrendsGraph";
import type { GraphDrag } from "./useGraphDrag";
import type { DashboardMetrics } from "./useDashboardMetrics";

export type GraphActions = {
  expand: (id: string) => void;
  edit: (id: string) => void;
  duplicate: (id: string) => void;
  toggleSize: (id: string) => void;
  move: (id: string, delta: number) => void;
  remove: (id: string) => void;
};

/** One dashboard grid slot: drag handle + graph menu around a TrendsGraph. */
export function GraphCell(props: {
  panel: TrendsGraphConfig;
  index: number;
  count: number;
  data: DashboardMetrics;
  palette: Map<string, number>;
  drag: GraphDrag;
  actions: GraphActions;
}) {
  const { panel, drag, actions } = props;
  const classes = [
    "trends-grid-cell",
    gridCellClass(panel.size),
    drag.dragId === panel.id ? "is-dragging" : "",
    drag.overId === panel.id ? "is-drop-target" : "",
  ].filter(Boolean);
  return (
    <div className={classes.join(" ")} {...drag.cellProps(panel.id)}>
      <TrendsGraph
        config={panel}
        data={props.data}
        palette={props.palette}
        onOpen={() => actions.expand(panel.id)}
        leading={
          <span
            className="trends-graph-handle"
            title="Drag to reorder"
            aria-hidden="true"
            {...drag.handleProps(panel.id)}
          >
            ⠿
          </span>
        }
        actions={
          <div className="trends-graph-actions">
            <GraphExportMenu
              appearance="icon"
              onCsv={() => exportGraphCsv(panel, props.data)}
            />
            <MenuButton
              label="Graph options"
              className="trends-graph-menu"
              items={graphMenu(panel, props.index, props.count, actions)}
            />
          </div>
        }
      />
    </div>
  );
}

function graphMenu(
  panel: TrendsGraphConfig,
  index: number,
  count: number,
  a: GraphActions,
): MenuItem[] {
  const id = panel.id;
  return [
    { id: "expand", label: "Expand", onSelect: () => a.expand(id) },
    { id: "edit", label: "Edit…", onSelect: () => a.edit(id) },
    { id: "duplicate", label: "Duplicate", onSelect: () => a.duplicate(id) },
    {
      id: "size",
      label: panel.size === "full" ? "Make half width" : "Make full width",
      onSelect: () => a.toggleSize(id),
    },
    {
      id: "earlier",
      label: "Move earlier",
      disabled: index === 0,
      separatorBefore: true,
      onSelect: () => a.move(id, -1),
    },
    {
      id: "later",
      label: "Move later",
      disabled: index === count - 1,
      onSelect: () => a.move(id, 1),
    },
    {
      id: "remove",
      label: "Remove",
      danger: true,
      separatorBefore: true,
      onSelect: () => a.remove(id),
    },
  ];
}
