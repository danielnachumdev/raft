import type { TrendsRangeState } from "../../range/types.ts";
import { defaultPanels } from "./defaults.ts";
import type {
  GraphSize,
  TrendsDashboard,
  TrendsGraphConfig,
  TrendsGraphDraft,
} from "./types.ts";

/** Pure graph-list reducers; every change bumps ``updatedAt``. */

export function addPanel(
  d: TrendsDashboard,
  draft: TrendsGraphDraft,
  id: string,
): TrendsDashboard {
  return touch(d, [...d.panels, { ...cloneDraft(draft), id }]);
}

export function updatePanel(
  d: TrendsDashboard,
  id: string,
  draft: TrendsGraphDraft,
): TrendsDashboard {
  return touch(
    d,
    d.panels.map((p) => (p.id === id ? { ...cloneDraft(draft), id } : p)),
  );
}

export function removePanel(d: TrendsDashboard, id: string): TrendsDashboard {
  return touch(d, d.panels.filter((p) => p.id !== id));
}

/** Put a removed graph back at its old position (undo). */
export function insertPanel(
  d: TrendsDashboard,
  panel: TrendsGraphConfig,
  index: number,
): TrendsDashboard {
  if (d.panels.some((p) => p.id === panel.id)) return d;
  const at = Math.max(0, Math.min(index, d.panels.length));
  const panels = [...d.panels];
  panels.splice(at, 0, panel);
  return touch(d, panels);
}

export function duplicatePanel(
  d: TrendsDashboard,
  id: string,
  newId: string,
): TrendsDashboard {
  const idx = d.panels.findIndex((p) => p.id === id);
  if (idx < 0) return d;
  const src = d.panels[idx];
  const copy = { ...cloneDraft(src), title: copyTitle(src.title), id: newId };
  return insertPanel(d, copy, idx + 1);
}

/** Move by ``delta`` slots (clamped); no-op at the edges. */
export function movePanel(
  d: TrendsDashboard,
  id: string,
  delta: number,
): TrendsDashboard {
  const from = d.panels.findIndex((p) => p.id === id);
  if (from < 0) return d;
  const to = Math.max(0, Math.min(d.panels.length - 1, from + delta));
  return reorder(d, from, to);
}

/** Drag-and-drop: place ``fromId`` where ``toId`` currently sits. */
export function movePanelTo(
  d: TrendsDashboard,
  fromId: string,
  toId: string,
): TrendsDashboard {
  const from = d.panels.findIndex((p) => p.id === fromId);
  const to = d.panels.findIndex((p) => p.id === toId);
  if (from < 0 || to < 0) return d;
  return reorder(d, from, to);
}

export function resizePanel(
  d: TrendsDashboard,
  id: string,
  size: GraphSize,
): TrendsDashboard {
  return touch(d, d.panels.map((p) => (p.id === id ? { ...p, size } : p)));
}

export function restoreDefaultPanels(d: TrendsDashboard): TrendsDashboard {
  return touch(d, defaultPanels());
}

export function setDashboardRange(
  d: TrendsDashboard,
  range: TrendsRangeState,
): TrendsDashboard {
  return { ...d, range: { ...range }, updatedAt: nowIso() };
}

export function cloneDraft(src: TrendsGraphDraft): TrendsGraphDraft {
  return {
    title: src.title,
    metricIds: [...src.metricIds],
    viewMode: src.viewMode,
    selected: src.selected === null ? null : [...src.selected],
    size: src.size,
  };
}

function reorder(d: TrendsDashboard, from: number, to: number): TrendsDashboard {
  if (from === to) return d;
  const panels = [...d.panels];
  const [moved] = panels.splice(from, 1);
  panels.splice(to, 0, moved);
  return touch(d, panels);
}

function copyTitle(title: string): string {
  return title ? `${title} (copy)` : "";
}

function touch(d: TrendsDashboard, panels: TrendsGraphConfig[]): TrendsDashboard {
  return { ...d, panels, updatedAt: nowIso() };
}

function nowIso(): string {
  return new Date().toISOString();
}
