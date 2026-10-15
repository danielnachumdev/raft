import { useMemo, useState } from "react";
import { LiveIndicator } from "../../../chrome/LiveIndicator";
import { DownloadMenu } from "../../../export/DownloadMenu";
import { metricsDownloadUrl } from "../../../export/urls";
import {
  addPanel,
  blankDraft,
  duplicatePanel,
  movePanel,
  movePanelTo,
  newId,
  planesForGraphs,
  resizePanel,
  restoreDefaultPanels,
  seriesPalette,
  setDashboardRange,
  updatePanel,
  type TrendsGraphDraft,
} from "../model/index.ts";
import { DashboardEmpty } from "./DashboardEmpty";
import { DashboardToolbar } from "./DashboardToolbar";
import { ExpandedGraph } from "./ExpandedGraph";
import { GraphCell, type GraphActions } from "./GraphCell";
import { GraphEditor, type EditorTarget } from "./GraphEditor";
import { UndoBar } from "./UndoBar";
import { useDashboardMetrics, type DashboardMetrics } from "./useDashboardMetrics";
import { useDashboardStore } from "./useDashboardStore";
import { useGraphDrag } from "./useGraphDrag";
import "./TrendsDashboard.css";

/** Multi-graph Trends dashboard: shared range + fetch, many configurable graphs. */
export function TrendsDashboard() {
  const api = useDashboardStore();
  const { dashboard, edit } = api;
  const planes = planesForGraphs(dashboard.panels);
  const data = useDashboardMetrics(dashboard.range, planes);
  const palette = useMemo(() => seriesPalette(data.available), [data.available]);
  const [editor, setEditor] = useState<EditorTarget | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const drag = useGraphDrag((from, to) => edit((d) => movePanelTo(d, from, to)));
  const openAdd = () => setEditor({ mode: "add", draft: blankDraft() });
  const actions = graphActions({ api, setEditor, setExpandedId });
  const save = (draft: TrendsGraphDraft) => {
    if (editor?.mode === "edit") edit((d) => updatePanel(d, editor.id, draft));
    else edit((d) => addPanel(d, draft, newId("graph")));
    setEditor(null);
  };

  return (
    <section className="panel trends" id="trends">
      <div className="panel-head">
        <div className="trends-title">
          <h2>
            Trends
            <span className="panel-count">{dashboard.name}</span>
          </h2>
          <TrendsStatus data={data} />
        </div>
        <DownloadMenu
          kind="metrics"
          hrefFor={(formatId) =>
            metricsDownloadUrl({ formatId, window: data.windowSec })
          }
          disabled={data.busy && data.series.length === 0}
        />
      </div>
      <DashboardToolbar
        api={api}
        bounds={data.bounds}
        clampMessage={data.clampMessage}
        onRange={(range) => edit((d) => setDashboardRange(d, range))}
        onAdd={openAdd}
      />
      <UndoBar removed={api.removed} onUndo={api.undoRemove} onDismiss={api.dismissUndo} />
      {dashboard.panels.length === 0 ? (
        <DashboardEmpty
          onAdd={openAdd}
          onRestoreDefaults={() => edit(restoreDefaultPanels)}
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
              drag={drag}
              actions={actions}
            />
          ))}
        </div>
      )}
      <GraphEditor
        target={editor}
        data={data}
        palette={palette}
        onCancel={() => setEditor(null)}
        onSave={save}
      />
      <ExpandedGraph
        panels={dashboard.panels}
        id={editor ? null : expandedId}
        data={data}
        palette={palette}
        onNavigate={setExpandedId}
        onEdit={actions.edit}
        onClose={() => setExpandedId(null)}
      />
    </section>
  );
}

function TrendsStatus(props: { data: DashboardMetrics }) {
  const { data } = props;
  if (data.busy && data.series.length === 0) {
    return <p className="muted panel-kind" aria-live="polite">Loading…</p>;
  }
  if (!data.live) {
    return <p className="muted panel-kind">Fixed range · recorded metrics</p>;
  }
  return <LiveIndicator isLive label={data.busy ? "Updating…" : "Live"} />;
}

function graphActions(args: {
  api: ReturnType<typeof useDashboardStore>;
  setEditor: (t: EditorTarget | null) => void;
  setExpandedId: (id: string | null) => void;
}): GraphActions {
  const { api } = args;
  const find = (id: string) => api.dashboard.panels.find((p) => p.id === id);
  return {
    expand: (id) => args.setExpandedId(id),
    edit: (id) => {
      const panel = find(id);
      if (panel) args.setEditor({ mode: "edit", id, draft: panel });
    },
    duplicate: (id) => api.edit((d) => duplicatePanel(d, id, newId("graph"))),
    toggleSize: (id) => {
      const panel = find(id);
      if (!panel) return;
      const size = panel.size === "full" ? "half" : "full";
      api.edit((d) => resizePanel(d, id, size));
    },
    move: (id, delta) => api.edit((d) => movePanel(d, id, delta)),
    remove: (id) => api.remove(id),
  };
}
