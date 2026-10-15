import {
  useCallback,
  useEffect,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";
import type { RuntimeMetricId } from "../runtimeMetrics.ts";
import type { TrendsRangeState } from "../range/types.ts";
import {
  usesGroupPicker,
  type SeriesViewMode,
} from "../panel/trendsView.ts";
import {
  createNamedView,
  deleteView,
  loadTrendsViewsStore,
  renameView,
  saveTrendsViewsStore,
  setActiveViewId,
  updateActiveConfig,
  upsertView,
} from "./storage.ts";
import {
  reconcileViewConfig,
  staleSelectionMessage,
} from "./reconcile.ts";
import type { TrendsViewConfig, TrendsViewsStore } from "./types.ts";

export type TrendsNamedViewsApi = {
  store: TrendsViewsStore;
  staleMessage: string | null;
  onSelect: (viewId: string | null) => void;
  onSave: (name: string) => void;
  onUpdate: () => void;
  onRename: (name: string) => void;
  onDelete: () => void;
};

type Setter<T> = Dispatch<SetStateAction<T>>;

/** localStorage-backed named views + apply/reconcile against the live catalog. */
export function useTrendsNamedViews(args: {
  metricIds: RuntimeMetricId[];
  viewMode: SeriesViewMode;
  selected: string[] | null;
  range: TrendsRangeState;
  pickerIds: string[];
  setMetricIds: Setter<RuntimeMetricId[]>;
  setViewMode: Setter<SeriesViewMode>;
  setSelected: Setter<string[] | null>;
  setRange: Setter<TrendsRangeState>;
}): TrendsNamedViewsApi {
  const [store, setStore] = useState(loadTrendsViewsStore);
  const [staleMessage, setStaleMessage] = useState<string | null>(null);
  const [bootstrapped, setBootstrapped] = useState(false);

  useEffect(() => {
    saveTrendsViewsStore(store);
  }, [store]);

  const snapshot = useCallback((): TrendsViewConfig => {
    return {
      metricIds: args.metricIds,
      viewMode: args.viewMode,
      selected: args.selected,
      range: args.range,
    };
  }, [args.metricIds, args.viewMode, args.selected, args.range]);

  const applyConfig = useCallback(
    (config: TrendsViewConfig) => {
      args.setMetricIds(config.metricIds);
      args.setViewMode(config.viewMode);
      args.setRange(config.range);
      if (args.pickerIds.length === 0) {
        args.setSelected(config.selected);
        setStaleMessage(null);
        return;
      }
      const { config: next, missingIds } = reconcileViewConfig(
        config,
        args.pickerIds,
      );
      args.setSelected(next.selected);
      setStaleMessage(
        staleSelectionMessage(missingIds, usesGroupPicker(next.viewMode)),
      );
    },
    [
      args.pickerIds,
      args.setMetricIds,
      args.setViewMode,
      args.setRange,
      args.setSelected,
    ],
  );

  useEffect(() => {
    if (bootstrapped) return;
    setBootstrapped(true);
    if (!store.activeId) return;
    const view = store.views.find((v) => v.id === store.activeId);
    if (!view) {
      setStore((s) => setActiveViewId(s, null));
      return;
    }
    applyConfig(view.config);
  }, [bootstrapped, store, applyConfig]);

  useEffect(() => {
    if (!bootstrapped || args.pickerIds.length === 0) return;
    if (!store.activeId) {
      setStaleMessage(null);
      return;
    }
    const view = store.views.find((v) => v.id === store.activeId);
    if (!view) return;
    refreshStale(view.config, args.pickerIds, args.setSelected, setStaleMessage);
  }, [
    args.pickerIds,
    args.setSelected,
    bootstrapped,
    store.activeId,
    store.views,
  ]);

  return {
    store,
    staleMessage,
    onSelect: (viewId) => {
      if (viewId === null) {
        setStore((s) => setActiveViewId(s, null));
        setStaleMessage(null);
        return;
      }
      const view = store.views.find((v) => v.id === viewId);
      if (!view) return;
      setStore((s) => setActiveViewId(s, viewId));
      applyConfig(view.config);
    },
    onSave: (name) => {
      const view = createNamedView(name, snapshot());
      setStore((s) => upsertView(s, view));
      setStaleMessage(null);
    },
    onUpdate: () => {
      setStore((s) => updateActiveConfig(s, snapshot()));
      setStaleMessage(null);
    },
    onRename: (name) => {
      if (!store.activeId) return;
      setStore((s) => renameView(s, store.activeId!, name));
    },
    onDelete: () => {
      if (!store.activeId) return;
      setStore((s) => deleteView(s, store.activeId!));
      setStaleMessage(null);
    },
  };
}

function refreshStale(
  config: TrendsViewConfig,
  pickerIds: string[],
  setSelected: Setter<string[] | null>,
  setStaleMessage: Setter<string | null>,
): void {
  if (config.selected === null) {
    setStaleMessage(null);
    return;
  }
  const { missingIds } = reconcileViewConfig(config, pickerIds);
  setStaleMessage(
    staleSelectionMessage(missingIds, usesGroupPicker(config.viewMode)),
  );
  const live = new Set(pickerIds);
  setSelected((cur) => {
    if (cur === null) return null;
    const next = cur.filter((id) => live.has(id));
    return next.length === cur.length ? cur : next;
  });
}
