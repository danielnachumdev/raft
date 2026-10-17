import { useEffect, useState } from "react";
import {
  appResourceCache,
  CachedResourceProxy,
  resourceId,
} from "../shared/cache/index.ts";
import type { ExportCatalog, ExportKind, ExportOption } from "./items";

const EMPTY: ExportCatalog = { logs: [], metrics: [] };

const catalogId = resourceId("exports", "catalog");

const catalogProxy = new CachedResourceProxy(appResourceCache, catalogId, {
  read: async () => {
    const res = await fetch("/api/exports");
    if (!res.ok) {
      throw new Error(`exports ${res.status}`);
    }
    const body = (await res.json()) as ExportCatalog;
    return normalizeCatalog(body);
  },
});

export async function loadExportCatalog(): Promise<ExportCatalog> {
  return catalogProxy.read();
}

export function useExportOptions(kind: ExportKind): ExportOption[] {
  const [options, setOptions] = useState<ExportOption[]>(() => {
    const hit = appResourceCache.peek<ExportCatalog>(catalogId);
    return hit?.[kind] ?? [];
  });
  useEffect(() => {
    let cancelled = false;
    void loadExportCatalog()
      .then((catalog) => {
        if (!cancelled) setOptions(catalog[kind]);
      })
      .catch(() => {
        if (!cancelled) setOptions([]);
      });
    return () => {
      cancelled = true;
    };
  }, [kind]);
  return options;
}

function normalizeCatalog(body: ExportCatalog): ExportCatalog {
  return {
    logs: Array.isArray(body.logs) ? body.logs : EMPTY.logs,
    metrics: Array.isArray(body.metrics) ? body.metrics : EMPTY.metrics,
  };
}
