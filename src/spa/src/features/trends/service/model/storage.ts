import { defaultServiceLayout } from "./defaults.ts";
import { parseServiceTrendsStore } from "./parse.ts";
import {
  SERVICE_TRENDS_STORAGE_KEY,
  type ServiceTrendsLayout,
  type ServiceTrendsStore,
} from "./types.ts";

export function emptyServiceTrendsStore(): ServiceTrendsStore {
  return { version: 1, services: {} };
}

/**
 * Load the service-trends map from localStorage. Corrupt / missing payloads
 * become an empty store (never throws).
 */
export function loadServiceTrendsStore(): ServiceTrendsStore {
  try {
    if (typeof localStorage === "undefined") return emptyServiceTrendsStore();
    const raw = localStorage.getItem(SERVICE_TRENDS_STORAGE_KEY);
    if (raw === null) return emptyServiceTrendsStore();
    return parseServiceTrendsStore(JSON.parse(raw)) ?? emptyServiceTrendsStore();
  } catch {
    return emptyServiceTrendsStore();
  }
}

/** Persist store; ignores quota / private-mode failures. */
export function saveServiceTrendsStore(store: ServiceTrendsStore): void {
  try {
    if (typeof localStorage === "undefined") return;
    localStorage.setItem(SERVICE_TRENDS_STORAGE_KEY, JSON.stringify(store));
  } catch {
    /* ignore */
  }
}

/** Layout for ``service``, or the default six graphs when none is saved. */
export function layoutForService(
  store: ServiceTrendsStore,
  service: string,
  nowMs: number = Date.now(),
): ServiceTrendsLayout {
  const saved = store.services[service];
  if (!saved) return defaultServiceLayout(service, nowMs);
  return {
    ...saved,
    range: { ...saved.range },
    panels: saved.panels.map((p) => ({
      ...p,
      metricIds: [...p.metricIds],
      selected: p.selected === null ? null : [...p.selected],
    })),
  };
}

/** Write one service's layout into the store map. */
export function putServiceLayout(
  store: ServiceTrendsStore,
  service: string,
  layout: ServiceTrendsLayout,
): ServiceTrendsStore {
  return {
    version: 1,
    services: { ...store.services, [service]: layout },
  };
}
