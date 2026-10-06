import { useEffect, useState } from "react";
import type { ExportCatalog, ExportKind, ExportOption } from "./items";

const EMPTY: ExportCatalog = { logs: [], metrics: [] };

let cached: ExportCatalog | null = null;
let inflight: Promise<ExportCatalog> | null = null;

export async function loadExportCatalog(): Promise<ExportCatalog> {
  if (cached) return cached;
  if (!inflight) {
    inflight = fetchCatalog().finally(() => {
      inflight = null;
    });
  }
  return inflight;
}

export function useExportOptions(kind: ExportKind): ExportOption[] {
  const [options, setOptions] = useState<ExportOption[]>(
    () => cached?.[kind] ?? [],
  );
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

async function fetchCatalog(): Promise<ExportCatalog> {
  const res = await fetch("/api/exports");
  if (!res.ok) {
    throw new Error(`exports ${res.status}`);
  }
  const body = (await res.json()) as ExportCatalog;
  cached = normalizeCatalog(body);
  return cached;
}

function normalizeCatalog(body: ExportCatalog): ExportCatalog {
  return {
    logs: Array.isArray(body.logs) ? body.logs : EMPTY.logs,
    metrics: Array.isArray(body.metrics) ? body.metrics : EMPTY.metrics,
  };
}
