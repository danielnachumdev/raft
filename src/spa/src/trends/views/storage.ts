import { parseStore } from "./parseStore.ts";
import {
  EMPTY_VIEWS_STORE,
  TRENDS_VIEWS_STORAGE_KEY,
  type TrendsViewsStore,
} from "./types.ts";

/**
 * Read #202 named views (read-only; migrated into dashboards).
 * Invalid / missing → empty store.
 */
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
