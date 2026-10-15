import { parseStore } from "./parseStore.ts";
import {
  EMPTY_VIEWS_STORE,
  TRENDS_VIEWS_STORAGE_KEY,
  type NamedTrendsView,
  type TrendsViewConfig,
  type TrendsViewsStore,
} from "./types.ts";

/** Load views from localStorage; invalid / missing → empty store. */
export function loadTrendsViewsStore(): TrendsViewsStore {
  try {
    if (typeof localStorage === "undefined") return { ...EMPTY_VIEWS_STORE };
    const raw = localStorage.getItem(TRENDS_VIEWS_STORAGE_KEY);
    if (!raw) return { ...EMPTY_VIEWS_STORE };
    return parseStore(JSON.parse(raw));
  } catch {
    return { ...EMPTY_VIEWS_STORE };
  }
}

/** Persist store; ignores quota / private-mode failures. */
export function saveTrendsViewsStore(store: TrendsViewsStore): void {
  try {
    if (typeof localStorage === "undefined") return;
    localStorage.setItem(TRENDS_VIEWS_STORAGE_KEY, JSON.stringify(store));
  } catch {
    /* ignore */
  }
}

export function createNamedView(
  name: string,
  config: TrendsViewConfig,
  nowMs: number = Date.now(),
): NamedTrendsView {
  return {
    id: newViewId(nowMs),
    name: name.trim(),
    updatedAt: new Date(nowMs).toISOString(),
    config: cloneConfig(config),
  };
}

export function upsertView(
  store: TrendsViewsStore,
  view: NamedTrendsView,
): TrendsViewsStore {
  const idx = store.views.findIndex((v) => v.id === view.id);
  const views =
    idx < 0
      ? [...store.views, view]
      : store.views.map((v, i) => (i === idx ? view : v));
  return { ...store, views, activeId: view.id };
}

export function renameView(
  store: TrendsViewsStore,
  id: string,
  name: string,
): TrendsViewsStore {
  const trimmed = name.trim();
  if (!trimmed) return store;
  return {
    ...store,
    views: store.views.map((v) =>
      v.id === id
        ? { ...v, name: trimmed, updatedAt: new Date().toISOString() }
        : v,
    ),
  };
}

export function deleteView(
  store: TrendsViewsStore,
  id: string,
): TrendsViewsStore {
  const views = store.views.filter((v) => v.id !== id);
  const activeId = store.activeId === id ? null : store.activeId;
  return { ...store, views, activeId };
}

export function setActiveViewId(
  store: TrendsViewsStore,
  activeId: string | null,
): TrendsViewsStore {
  if (activeId !== null && !store.views.some((v) => v.id === activeId)) {
    return { ...store, activeId: null };
  }
  return { ...store, activeId };
}

export function updateActiveConfig(
  store: TrendsViewsStore,
  config: TrendsViewConfig,
  nowMs: number = Date.now(),
): TrendsViewsStore {
  if (!store.activeId) return store;
  const updatedAt = new Date(nowMs).toISOString();
  return {
    ...store,
    views: store.views.map((v) =>
      v.id === store.activeId
        ? { ...v, config: cloneConfig(config), updatedAt }
        : v,
    ),
  };
}

export function cloneConfig(config: TrendsViewConfig): TrendsViewConfig {
  return {
    metricIds: [...config.metricIds],
    viewMode: config.viewMode,
    selected: config.selected === null ? null : [...config.selected],
    range: { ...config.range },
  };
}

function newViewId(nowMs: number): string {
  return `view-${nowMs.toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}
