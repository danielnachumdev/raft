import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  insertPanel,
  removePanel,
  type TrendsDashboard,
  type TrendsGraphConfig,
} from "../../dashboard/model/index.ts";
import {
  asDashboard,
  fromDashboard,
  layoutForService,
  loadServiceTrendsStore,
  pinLayoutToService,
  putServiceLayout,
  saveServiceTrendsStore,
} from "../model/index.ts";

const UNDO_MS = 8000;

export type RemovedGraph = { panel: TrendsGraphConfig; index: number };

export type ServiceTrendsStoreApi = {
  dashboard: TrendsDashboard;
  edit: (fn: (d: TrendsDashboard) => TrendsDashboard) => void;
  remove: (id: string) => void;
  removed: RemovedGraph | null;
  undoRemove: () => void;
  dismissUndo: () => void;
};

/** localStorage-backed layout for one service + short-lived remove undo. */
export function useServiceTrendsStore(service: string): ServiceTrendsStoreApi {
  const [store, setStore] = useState(loadServiceTrendsStore);
  const [removed, setRemoved] = useState<RemovedGraph | null>(null);
  const timer = useRef<number | null>(null);

  useEffect(() => saveServiceTrendsStore(store), [store]);
  useEffect(() => () => clearTimer(timer), []);
  useEffect(() => {
    setRemoved(null);
    clearTimer(timer);
  }, [service]);

  const layout = useMemo(
    () => pinLayoutToService(layoutForService(store, service), service),
    [store, service],
  );
  const dashboard = useMemo(() => asDashboard(service, layout), [service, layout]);

  const edit = useCallback(
    (fn: (d: TrendsDashboard) => TrendsDashboard) => {
      setStore((s) => {
        const current = pinLayoutToService(layoutForService(s, service), service);
        const next = fromDashboard(fn(asDashboard(service, current)));
        return putServiceLayout(s, service, pinLayoutToService(next, service));
      });
    },
    [service],
  );

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
  return { dashboard, edit, remove, removed, undoRemove, dismissUndo };
}

function clearTimer(timer: { current: number | null }): void {
  if (timer.current !== null) window.clearTimeout(timer.current);
  timer.current = null;
}
