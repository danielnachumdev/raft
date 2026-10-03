/** Nest status rows by App ``depends_on`` (Compose service ids). */

import type { StatusRow } from "./api";

export type StatusTreeRow = StatusRow & { treeDepth: number };

/** Parent = app that declares depends_on; children = those deps (under parent). */
export function orderByDependsTree(rows: StatusRow[]): StatusTreeRow[] {
  const byService = indexByService(rows);
  const children = childrenByParent(rows, byService);
  const claimed = claimedChildren(children);
  const depths = new Map<string, number>();
  const ordered: StatusRow[] = [];
  const visit = (service: string, depth: number) => {
    if (depths.has(service)) return;
    const row = byService.get(service);
    if (!row) return;
    depths.set(service, depth);
    ordered.push(row);
    for (const child of children.get(service) ?? []) {
      visit(child, depth + 1);
    }
  };
  for (const root of rootsInOrder(rows, claimed)) {
    visit(root.service, 0);
  }
  for (const row of rows) {
    visit(row.service, 0);
  }
  return ordered.map((row) => ({
    ...row,
    treeDepth: depths.get(row.service) ?? 0,
  }));
}

/** Keep caller order; still attach tree depths from depends_on edges. */
export function attachTreeDepths(rows: StatusRow[]): StatusTreeRow[] {
  const depths = depthIndex(rows);
  return rows.map((row) => ({
    ...row,
    treeDepth: depths.get(row.service) ?? 0,
  }));
}

function depthIndex(rows: StatusRow[]): Map<string, number> {
  return new Map(orderByDependsTree(rows).map((r) => [r.service, r.treeDepth]));
}

function indexByService(rows: StatusRow[]): Map<string, StatusRow> {
  const map = new Map<string, StatusRow>();
  for (const row of rows) {
    map.set(row.service, row);
  }
  return map;
}

function childrenByParent(
  rows: StatusRow[],
  byService: Map<string, StatusRow>,
): Map<string, string[]> {
  const children = new Map<string, string[]>();
  for (const row of rows) {
    const deps = (row.depends_on ?? []).filter((id) => byService.has(id));
    if (!deps.length) continue;
    children.set(row.service, [...deps].sort(compareService(byService)));
  }
  return children;
}

function claimedChildren(children: Map<string, string[]>): Set<string> {
  const claimed = new Set<string>();
  for (const list of children.values()) {
    for (const id of list) claimed.add(id);
  }
  return claimed;
}

function rootsInOrder(rows: StatusRow[], claimed: Set<string>): StatusRow[] {
  return rows
    .filter((row) => !claimed.has(row.service))
    .slice()
    .sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base" }));
}

function compareService(byService: Map<string, StatusRow>) {
  return (a: string, b: string) => {
    const left = byService.get(a)?.name ?? a;
    const right = byService.get(b)?.name ?? b;
    return left.localeCompare(right, undefined, { sensitivity: "base" });
  };
}
