import { useEffect, useState } from "react";
import { Modal } from "../../../chrome/Modal";
import { graphTitle, type TrendsGraphConfig } from "../model/index.ts";
import { TrendsGraph } from "./TrendsGraph";
import type { DashboardMetrics } from "./useDashboardMetrics";

/** Near-fullscreen deep dive on one graph; ←/→ step through the dashboard. */
export function ExpandedGraph(props: {
  panels: TrendsGraphConfig[];
  id: string | null;
  data: DashboardMetrics;
  palette: Map<string, number>;
  onNavigate: (id: string) => void;
  /** Omitted in view-mode embeds (#249). */
  onEdit?: (id: string) => void;
  onClose: () => void;
}) {
  const index = props.panels.findIndex((p) => p.id === props.id);
  const panel = index >= 0 ? props.panels[index] : null;
  const height = useExpandedHeight();
  const step = (delta: number) => {
    const next = props.panels[index + delta];
    if (next) props.onNavigate(next.id);
  };
  useArrowKeys(panel !== null, step);

  return (
    <Modal
      open={panel !== null}
      onClose={props.onClose}
      title={panel ? graphTitle(panel) : ""}
      size="full"
      footer={
        <div className="modal-actions trends-expanded-actions">
          <span className="muted trends-expanded-pos">
            {index + 1} of {props.panels.length} · ←/→ to browse
          </span>
          <button
            type="button"
            className="action-btn"
            disabled={index <= 0}
            onClick={() => step(-1)}
          >
            ← Previous
          </button>
          <button
            type="button"
            className="action-btn"
            disabled={index >= props.panels.length - 1}
            onClick={() => step(1)}
          >
            Next →
          </button>
          {props.onEdit ? (
            <button
              type="button"
              className="action-btn"
              onClick={() => panel && props.onEdit?.(panel.id)}
            >
              Edit…
            </button>
          ) : null}
        </div>
      }
    >
      {panel ? (
        <TrendsGraph
          config={panel}
          data={props.data}
          palette={props.palette}
          height={height}
          className="is-expanded"
        />
      ) : null}
    </Modal>
  );
}

function useExpandedHeight(): number {
  const read = () => Math.max(320, Math.round(window.innerHeight * 0.58));
  const [h, setH] = useState(read);
  useEffect(() => {
    const onResize = () => setH(read());
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return h;
}

function useArrowKeys(enabled: boolean, step: (delta: number) => void): void {
  useEffect(() => {
    if (!enabled) return;
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
      if (e.key === "ArrowLeft") step(-1);
      if (e.key === "ArrowRight") step(1);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [enabled, step]);
}
