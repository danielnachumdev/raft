import { useState } from "react";
import { Modal } from "../../../chrome/Modal";
import { cloneDraft, type TrendsGraphDraft } from "../model/index.ts";
import { GraphEditorForm } from "./GraphEditorForm";
import { TrendsGraph } from "./TrendsGraph";
import type { DashboardMetrics } from "./useDashboardMetrics";
import "./GraphEditor.css";

export type EditorTarget =
  | { mode: "add"; draft: TrendsGraphDraft }
  | { mode: "edit"; id: string; draft: TrendsGraphDraft };

/** Add / edit a graph with a live preview fed by the dashboard's shared data. */
export function GraphEditor(props: EditorProps & { target: EditorTarget | null }) {
  if (!props.target) return null;
  const key = props.target.mode === "edit" ? props.target.id : "add";
  return <EditorModal key={key} {...props} target={props.target} />;
}

type EditorProps = {
  data: DashboardMetrics;
  palette: Map<string, number>;
  onCancel: () => void;
  onSave: (draft: TrendsGraphDraft) => void;
};

function EditorModal(props: EditorProps & { target: EditorTarget }) {
  const [draft, setDraft] = useState(() => cloneDraft(props.target.draft));
  const adding = props.target.mode === "add";
  const blocker = saveBlocker(draft);

  return (
    <Modal
      open
      onClose={props.onCancel}
      title={adding ? "Add graph" : "Edit graph"}
      size="wide"
      closeOnOverlay={false}
      footer={
        <div className="modal-actions graph-editor-actions">
          {blocker ? <p className="muted graph-editor-blocker">{blocker}</p> : null}
          <button type="button" className="action-btn" onClick={props.onCancel}>
            Cancel
          </button>
          <button
            type="button"
            className="action-btn btn-primary"
            disabled={blocker !== null}
            onClick={() => props.onSave(draft)}
          >
            {adding ? "Add graph" : "Save changes"}
          </button>
        </div>
      }
    >
      <div className="graph-editor">
        <GraphEditorForm
          draft={draft}
          available={props.data.available}
          showPresets={adding}
          onChange={setDraft}
        />
        <div className="graph-editor-preview" aria-label="Preview">
          <span className="trends-services-title">Preview</span>
          <TrendsGraph
            config={draft}
            data={props.data}
            palette={props.palette}
            height={260}
          />
        </div>
      </div>
    </Modal>
  );
}

function saveBlocker(draft: TrendsGraphDraft): string | null {
  if (draft.metricIds.length === 0) return "Pick at least one metric.";
  if (draft.selected !== null && draft.selected.length === 0) {
    return "Pick at least one service or group, or Show all.";
  }
  return null;
}
