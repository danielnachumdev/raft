import { graphTitle } from "../model/index.ts";
import type { RemovedGraph } from "./useDashboardStore";

/** Inline "Removed … Undo" strip after deleting a graph. */
export function UndoBar(props: {
  removed: RemovedGraph | null;
  onUndo: () => void;
  onDismiss: () => void;
}) {
  if (!props.removed) return null;
  return (
    <div className="trends-undo" role="status">
      <span>
        Removed <strong>{graphTitle(props.removed.panel)}</strong>.
      </span>
      <button type="button" className="trends-undo-btn" onClick={props.onUndo}>
        Undo
      </button>
      <button
        type="button"
        className="trends-undo-close"
        aria-label="Dismiss"
        onClick={props.onDismiss}
      >
        ×
      </button>
    </div>
  );
}
