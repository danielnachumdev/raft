import { useCallback, useMemo, useState } from "react";
import type { StatusRow } from "./api";
import { parseMemoryRatioPercent, parsePercent } from "./statusTone";

export type SortKey = keyof StatusRow;
export type SortDir = "asc" | "desc";
export type Density = "comfortable" | "compact";

export type StatusPanelPrefs = {
  query: string;
  status: string;
  sortKey: SortKey | null;
  sortDir: SortDir;
  density: Density;
};

const DEFAULT_PREFS: StatusPanelPrefs = {
  query: "",
  status: "",
  sortKey: null,
  sortDir: "asc",
  density: "comfortable",
};

const SORTABLE: ReadonlySet<string> = new Set([
  "name",
  "role",
  "group",
  "status",
  "cpu",
  "memory",
  "uptime",
  "started",
  "service",
]);

export function useStatusPanelView(storageKey: string, rows: StatusRow[]) {
  const [prefs, setPrefs] = useState(() => loadPrefs(storageKey));

  const setAndPersist = useCallback(
    (next: StatusPanelPrefs) => {
      setPrefs(next);
      savePrefs(storageKey, next);
    },
    [storageKey],
  );

  const setQuery = useCallback(
    (query: string) => setAndPersist({ ...prefs, query }),
    [prefs, setAndPersist],
  );

  const setStatus = useCallback(
    (status: string) => setAndPersist({ ...prefs, status }),
    [prefs, setAndPersist],
  );

  const setDensity = useCallback(
    (density: Density) => setAndPersist({ ...prefs, density }),
    [prefs, setAndPersist],
  );

  const toggleSort = useCallback(
    (key: SortKey) => {
      if (prefs.sortKey === key) {
        setAndPersist({
          ...prefs,
          sortDir: prefs.sortDir === "asc" ? "desc" : "asc",
        });
        return;
      }
      setAndPersist({ ...prefs, sortKey: key, sortDir: "asc" });
    },
    [prefs, setAndPersist],
  );

  const clearFilters = useCallback(() => {
    setAndPersist({
      ...prefs,
      query: "",
      status: "",
      sortKey: null,
      sortDir: "asc",
    });
  }, [prefs, setAndPersist]);

  const statusOptions = useMemo(() => uniqueStatuses(rows), [rows]);

  const visible = useMemo(
    () => applyView(rows, prefs),
    [rows, prefs],
  );

  const filtersActive =
    prefs.query.trim() !== "" ||
    prefs.status !== "" ||
    prefs.sortKey !== null;

  return {
    prefs,
    visible,
    statusOptions,
    filtersActive,
    setQuery,
    setStatus,
    setDensity,
    toggleSort,
    clearFilters,
  };
}

export function applyView(
  rows: StatusRow[],
  prefs: StatusPanelPrefs,
): StatusRow[] {
  const filtered = rows.filter((row) => matchesFilters(row, prefs));
  if (!prefs.sortKey) {
    return filtered;
  }
  return sortRows(filtered, prefs.sortKey, prefs.sortDir);
}

function matchesFilters(row: StatusRow, prefs: StatusPanelPrefs): boolean {
  if (prefs.status && row.status.trim().toLowerCase() !== prefs.status) {
    return false;
  }
  const q = prefs.query.trim().toLowerCase();
  if (!q) {
    return true;
  }
  const hay = [row.name, row.service, row.group, row.role]
    .join(" ")
    .toLowerCase();
  return hay.includes(q);
}

function sortRows(
  rows: StatusRow[],
  key: SortKey,
  dir: SortDir,
): StatusRow[] {
  const mul = dir === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => mul * compareCells(a, b, key));
}

function compareCells(a: StatusRow, b: StatusRow, key: SortKey): number {
  const left = a[key];
  const right = b[key];
  if (key === "cpu") {
    return compareNullable(parsePercent(left), parsePercent(right));
  }
  if (key === "memory") {
    return compareNullable(
      parseMemoryRatioPercent(left),
      parseMemoryRatioPercent(right),
    );
  }
  if (key === "uptime") {
    return compareNullable(parseUptimeSeconds(left), parseUptimeSeconds(right));
  }
  return left.localeCompare(right, undefined, { sensitivity: "base" });
}

function compareNullable(a: number | null, b: number | null): number {
  if (a === null && b === null) return 0;
  if (a === null) return 1;
  if (b === null) return -1;
  return a - b;
}

/** Parse ``45s`` / ``1h 1m`` / ``1d 1h 1m`` display strings. */
export function parseUptimeSeconds(text: string): number | null {
  const raw = text.trim().toLowerCase();
  if (!raw || raw === "-") {
    return null;
  }
  if (/^\d+(\.\d+)?s$/.test(raw)) {
    return Number(raw.slice(0, -1));
  }
  let total = 0;
  let matched = false;
  for (const part of raw.matchAll(/(\d+)\s*([dhm])/g)) {
    matched = true;
    const n = Number(part[1]);
    const unit = part[2];
    if (unit === "d") total += n * 86400;
    else if (unit === "h") total += n * 3600;
    else total += n * 60;
  }
  return matched ? total : null;
}

function uniqueStatuses(rows: StatusRow[]): string[] {
  const set = new Set<string>();
  for (const row of rows) {
    const s = row.status.trim().toLowerCase();
    if (s) set.add(s);
  }
  return [...set].sort((a, b) => a.localeCompare(b));
}

function loadPrefs(key: string): StatusPanelPrefs {
  try {
    const raw = sessionStorage.getItem(key);
    if (!raw) return { ...DEFAULT_PREFS };
    return normalizePrefs(JSON.parse(raw) as Partial<StatusPanelPrefs>);
  } catch {
    return { ...DEFAULT_PREFS };
  }
}

function savePrefs(key: string, prefs: StatusPanelPrefs): void {
  try {
    sessionStorage.setItem(key, JSON.stringify(prefs));
  } catch {
    /* private mode / quota — ignore */
  }
}

function normalizePrefs(raw: Partial<StatusPanelPrefs>): StatusPanelPrefs {
  const density =
    raw.density === "compact" || raw.density === "comfortable"
      ? raw.density
      : DEFAULT_PREFS.density;
  const sortKey =
    raw.sortKey && SORTABLE.has(raw.sortKey) ? raw.sortKey : null;
  const sortDir = raw.sortDir === "desc" ? "desc" : "asc";
  return {
    query: typeof raw.query === "string" ? raw.query : "",
    status: typeof raw.status === "string" ? raw.status : "",
    sortKey,
    sortDir,
    density,
  };
}
