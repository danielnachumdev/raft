import {
  duplicatePanel,
  movePanel,
  newId,
  resizePanel,
  type TrendsGraphDraft,
} from "../../trends/dashboard/model/index.ts";
import type { GraphActions } from "../../trends/dashboard/ui/GraphCell";
import type { EditorTarget } from "../../trends/dashboard/ui/GraphEditor";
import type { DashboardStoreApi } from "../../trends/dashboard/ui/useDashboardStore";
import type { GraphDrag } from "../../trends/dashboard/ui/useGraphDrag";
import type { DashboardVariables } from "../model/types.ts";
import { pinDraftToVariables } from "../model/variables.ts";

export function kitGraphActions(args: {
  api: DashboardStoreApi;
  editable: boolean;
  variables: DashboardVariables | undefined;
  setEditor: (t: EditorTarget | null) => void;
  setExpandedId: (id: string | null) => void;
}): GraphActions {
  const { api, editable, variables } = args;
  const find = (id: string) => api.dashboard.panels.find((p) => p.id === id);
  const noop = () => undefined;
  return {
    expand: (id) => args.setExpandedId(id),
    edit: (id) => {
      if (!editable) return;
      const panel = find(id);
      if (panel) {
        args.setEditor({
          mode: "edit",
          id,
          draft: pinDraftToVariables(panel, variables),
        });
      }
    },
    duplicate: editable
      ? (id) => api.edit((d) => duplicatePanel(d, id, newId("graph")))
      : noop,
    toggleSize: (id) => {
      if (!editable) return;
      const panel = find(id);
      if (!panel) return;
      const size = panel.size === "full" ? "half" : "full";
      api.edit((d) => resizePanel(d, id, size));
    },
    move: editable
      ? (id, delta) => api.edit((d) => movePanel(d, id, delta))
      : noop,
    remove: editable ? (id) => api.remove(id) : noop,
  };
}

export function pinSaveDraft(
  draft: TrendsGraphDraft,
  variables: DashboardVariables | undefined,
): TrendsGraphDraft {
  return pinDraftToVariables(draft, variables);
}

/** No-op drag surface for view-mode embeds. */
export const noopDrag: GraphDrag = {
  dragId: null,
  overId: null,
  handleProps: () => ({
    draggable: true,
    onDragStart: () => undefined,
    onDragEnd: () => undefined,
  }),
  cellProps: () => ({
    onDragOver: () => undefined,
    onDragLeave: () => undefined,
    onDrop: () => undefined,
  }),
};
