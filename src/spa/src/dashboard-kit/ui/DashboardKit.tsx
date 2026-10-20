import { useMemo, useState, type ReactNode } from "react";
import {
  addPanel,
  movePanelTo,
  newId,
  planesForGraphs,
  seriesPalette,
  setDashboardRange,
  updatePanel,
  type TrendsDashboard,
  type TrendsGraphDraft,
} from "../../trends/dashboard/model/index.ts";
import { DashboardEmpty } from "../../trends/dashboard/ui/DashboardEmpty";
import { DashboardToolbar } from "../../trends/dashboard/ui/DashboardToolbar";
import { ExpandedGraph } from "../../trends/dashboard/ui/ExpandedGraph";
import { GraphCell } from "../../trends/dashboard/ui/GraphCell";
import { GraphEditor, type EditorTarget } from "../../trends/dashboard/ui/GraphEditor";
import { UndoBar } from "../../trends/dashboard/ui/UndoBar";
import { useDashboardMetrics } from "../../trends/dashboard/ui/useDashboardMetrics";
import type { DashboardStoreApi } from "../../trends/dashboard/ui/useDashboardStore";
import { useGraphDrag } from "../../trends/dashboard/ui/useGraphDrag";
import "../../trends/dashboard/ui/TrendsDashboard.css";
import type { DashboardKitContract } from "../model/types.ts";
import { KitHead } from "./KitHead";
import { kitGraphActions, noopDrag, pinSaveDraft } from "./kitActions";

export type DashboardKitProps = DashboardKitContract & {
  /** Multi-dashboard or single-layout store API (same shape as Trends). */
  api: DashboardStoreApi;
  /** Draft used when the operator clicks + Add graph. */
  blankDraft: () => TrendsGraphDraft;
  /** Restore-defaults reducer for the open dashboard. */
  restoreDefaults: (d: TrendsDashboard) => TrendsDashboard;
  /** Optional toolbar slot when the dashboard picker is hidden. */
  toolbar?: ReactNode;
};

/**
 * Reusable ops dashboard shell (#249): shared range + plane fetch, timeseries
 * panels, edit/view, expand, undo. Trends overview is the first in-tree embed.
 */
export function DashboardKit(props: DashboardKitProps) {
  const mode = props.mode ?? "edit";
  const editable = mode === "edit";
  const { api, variables } = props;
  const { dashboard, edit } = api;
  const chrome = props.chrome ?? {};
  const planes = planesForGraphs(dashboard.panels);
  const data = useDashboardMetrics(dashboard.range, planes, props.scope?.services);
  const palette = useMemo(() => seriesPalette(data.available), [data.available]);
  const [editor, setEditor] = useState<EditorTarget | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const drag = useGraphDrag((from, to) => {
    if (editable) edit((d) => movePanelTo(d, from, to));
  });
  const openAdd = () => {
    if (!editable) return;
    setEditor({ mode: "add", draft: props.blankDraft() });
  };
  const actions = kitGraphActions({
    api,
    editable,
    variables,
    setEditor,
    setExpandedId,
  });
  const save = (draft: TrendsGraphDraft) => {
    const pinned = pinSaveDraft(draft, variables);
    if (editor?.mode === "edit") edit((d) => updatePanel(d, editor.id, pinned));
    else edit((d) => addPanel(d, pinned, newId("graph")));
    setEditor(null);
  };
  const sectionClass = ["panel", "trends", chrome.sectionClassName]
    .filter(Boolean)
    .join(" ");

  return (
    <section
      className={sectionClass}
      id={props.embedId}
      data-dashboard-kit={props.embedId}
    >
      <KitHead
        title={chrome.title ?? "Trends"}
        subtitle={chrome.subtitle ?? dashboard.name}
        data={data}
        downloadServices={chrome.downloadServices}
      />
      {props.toolbar ?? (
        <DashboardToolbar
          api={api}
          bounds={data.bounds}
          clampMessage={data.clampMessage}
          onRange={(range) => edit((d) => setDashboardRange(d, range))}
          onAdd={openAdd}
          showPicker={chrome.showDashboardPicker !== false}
          showAdd={editable}
        />
      )}
      {editable ? (
        <UndoBar
          removed={api.removed}
          onUndo={api.undoRemove}
          onDismiss={api.dismissUndo}
        />
      ) : null}
      {dashboard.panels.length === 0 ? (
        <DashboardEmpty
          onAdd={openAdd}
          onRestoreDefaults={() => edit(props.restoreDefaults)}
        />
      ) : (
        <div className="trends-grid" key={dashboard.id}>
          {dashboard.panels.map((panel, i) => (
            <GraphCell
              key={panel.id}
              panel={panel}
              index={i}
              count={dashboard.panels.length}
              data={data}
              palette={palette}
              drag={editable ? drag : noopDrag}
              actions={actions}
            />
          ))}
        </div>
      )}
      {editable ? (
        <GraphEditor
          target={editor}
          data={data}
          palette={palette}
          pinnedService={variables?.service}
          onCancel={() => setEditor(null)}
          onSave={save}
        />
      ) : null}
      <ExpandedGraph
        panels={dashboard.panels}
        id={editor ? null : expandedId}
        data={data}
        palette={palette}
        onNavigate={setExpandedId}
        onEdit={editable ? actions.edit : undefined}
        onClose={() => setExpandedId(null)}
      />
    </section>
  );
}
