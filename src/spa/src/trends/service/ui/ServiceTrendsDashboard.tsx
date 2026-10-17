import { useMemo, useState } from "react";
import { LiveIndicator } from "../../../chrome/LiveIndicator";
import { DownloadMenu } from "../../../export/DownloadMenu";
import { metricsDownloadUrl } from "../../../export/urls";
import {
  addPanel,
  duplicatePanel,
  movePanel,
  movePanelTo,
  newId,
  planesForGraphs,
  resizePanel,
  seriesPalette,
  setDashboardRange,
  updatePanel,
  type TrendsGraphDraft,
} from "../../dashboard/model/index.ts";
import { DashboardEmpty } from "../../dashboard/ui/DashboardEmpty";
import { ExpandedGraph } from "../../dashboard/ui/ExpandedGraph";
import { GraphCell, type GraphActions } from "../../dashboard/ui/GraphCell";
import { GraphEditor, type EditorTarget } from "../../dashboard/ui/GraphEditor";
import { UndoBar } from "../../dashboard/ui/UndoBar";
import {
  useDashboardMetrics,
  type DashboardMetrics,
} from "../../dashboard/ui/useDashboardMetrics";
import { useGraphDrag } from "../../dashboard/ui/useGraphDrag";
import "../../dashboard/ui/TrendsDashboard.css";
import { blankServiceDraft, defaultServicePanels, pinDraftToService } from "../model/index.ts";
import { ServiceTrendsToolbar } from "./ServiceTrendsToolbar";
import { useServiceTrendsStore } from "./useServiceTrendsStore";

/**
 * Multi-graph Trends on a service page: same graphs as Overview by default,
 * scoped to this service, editable and persisted in localStorage.
 */
export function ServiceTrendsDashboard(props: { service: string }) {
  const { service } = props;
  const api = useServiceTrendsStore(service);
  const { dashboard, edit } = api;
  const planes = planesForGraphs(dashboard.panels);
  const services = useMemo(() => [service], [service]);
  const data = useDashboardMetrics(dashboard.range, planes, services);
  const palette = useMemo(() => seriesPalette(data.available), [data.available]);
  const [editor, setEditor] = useState<EditorTarget | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const drag = useGraphDrag((from, to) => edit((d) => movePanelTo(d, from, to)));
  const openAdd = () =>
    setEditor({ mode: "add", draft: blankServiceDraft(service) });
  const actions = graphActions({ api, service, setEditor, setExpandedId });
  const save = (draft: TrendsGraphDraft) => {
    const pinned = pinDraftToService(draft, service);
    if (editor?.mode === "edit") edit((d) => updatePanel(d, editor.id, pinned));
    else edit((d) => addPanel(d, pinned, newId("graph")));
    setEditor(null);
  };

  return (
    <section className="panel trends service-trends" id="trends">
      <div className="panel-head">
        <div className="trends-title">
          <h2>
            Trends
            <span className="panel-count">{service}</span>
          </h2>
          <TrendsStatus data={data} />
        </div>
        <DownloadMenu
          kind="metrics"
          hrefFor={(formatId) =>
            metricsDownloadUrl({
              formatId,
              window: data.windowSec,
              services: [service],
            })
          }
          disabled={data.busy && data.series.length === 0}
        />
      </div>
      <ServiceTrendsToolbar
        service={service}
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
          onRestoreDefaults={() =>
            edit((d) => ({
              ...d,
              panels: defaultServicePanels(service),
              updatedAt: new Date().toISOString(),
            }))
          }
        />
      ) : (
        <div className="trends-grid" key={service}>
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
        pinnedService={service}
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
  api: ReturnType<typeof useServiceTrendsStore>;
  service: string;
  setEditor: (t: EditorTarget | null) => void;
  setExpandedId: (id: string | null) => void;
}): GraphActions {
  const { api, service } = args;
  const find = (id: string) => api.dashboard.panels.find((p) => p.id === id);
  return {
    expand: (id) => args.setExpandedId(id),
    edit: (id) => {
      const panel = find(id);
      if (panel) {
        args.setEditor({
          mode: "edit",
          id,
          draft: pinDraftToService(panel, service),
        });
      }
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
