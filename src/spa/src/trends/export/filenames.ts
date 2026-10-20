/** PII-safe download basenames for graph exports (no hostnames). */

const FALLBACK = "graph";

/** Slug a graph title for ``raft-trends-<slug>.csv|png``. */
export function graphExportBasename(title: string): string {
  const slug = title
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
  return `raft-trends-${slug || FALLBACK}`;
}
