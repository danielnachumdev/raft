import { useCallback, useEffect, useRef, useState } from "react";
import {
  activeDashboard,
  insertPanel,
  loadDashboardStore,
  removePanel,
  saveDashboardStore,
  updateActive,
  type TrendsDashboard,
  type TrendsDashboardStore,
  type TrendsGraphConfig,
} from "../model/index.ts";

const UNDO_MS = 8000;

export type RemovedGraph = { panel: TrendsGraphConfig; index: number };

export type DashboardStoreApi = {
  store: TrendsDashboardStore;
  dashboard: TrendsDashboard;
  setStore: (fn: (s: TrendsDashboardStore) => TrendsDashboardStore) => void;
  edit: (fn: (d: TrendsDashboard) => TrendsDashboard) => void;
  remove: (id: string) => void;
  removed: RemovedGraph | null;
  undoRemove: () => void;
  dismissUndo: () => void;
};

/** localStorage-backed dashboards + a short-lived undo for graph removal. */
export function useDashboardStore(): DashboardStoreApi {
  const [store, setStoreState] = useState(loadDashboardStore);
  const [removed, setRemoved] = useState<RemovedGraph | null>(null);
  const timer = useRef<number | null>(null);

  useEffect(() => saveDashboardStore(store), [store]);
  useEffect(() => () => clearTimer(timer), []);

  const setStore = useCallback(
    (fn: (s: TrendsDashboardStore) => TrendsDashboardStore) => {
      setStoreState(fn);
    },
    [],
  );
  const edit = useCallback(
    (fn: (d: TrendsDashboard) => TrendsDashboard) => {
      setStoreState((s) => updateActive(s, fn));
    },
    [],
  );
  const dashboard = activeDashboard(store);

  const remove = (id: string) => {
    const index = dashboard.panels.findIndex((p) => p.id === id);
    if (index < 0) return;
    setRemoved({ panel: dashboard.panels[index], index });
    edit((d) => removePanel(d, id));
    clearTimer(timer);
    timer.current = window.setTimeout(() => setRemoved(null), UNDO_MS);
  };
  const undoRemove = () => {
    if (!removed) return;
    edit((d) => insertPanel(d, removed.panel, removed.index));
    setRemoved(null);
    clearTimer(timer);
  };
  const dismissUndo = () => {
    setRemoved(null);
    clearTimer(timer);
  };
  return { store, dashboard, setStore, edit, remove, removed, undoRemove, dismissUndo };
}

function clearTimer(timer: { current: number | null }): void {
  if (timer.current !== null) window.clearTimeout(timer.current);
  timer.current = null;
}
